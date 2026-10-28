"""Detectors: real neural nets (YOLO/ONNX Runtime) with automatic fallback to
classic OpenCV detectors when onnxruntime or the model weights aren't present.

Public interface is unchanged from V1 on purpose: FaceDetector(enabled, min_size)
and PersonDetector(enabled), both exposing .detect(frame) -> list[(x, y, w, h)].
Nothing upstream (pipeline.py, tracker.py) needs to change for this upgrade.

Models:
  models/yolov11n-face.onnx  - face detector, trained on WIDERFace
                                (github.com/akanametov/yolo-face, release 1.0.0)
  models/yolo11n.onnx        - general 80-class COCO detector, class 0 = person
                                (github.com/ultralytics/assets, release v8.3.0)
Both are small (~10MB), CPU-only, single-image inference typically <60ms on a
modern laptop CPU at 640x640 -- an order of magnitude more accurate than Haar
cascade / HOG, and comparable or faster in practice because they run one pass
instead of a multi-scale sliding window.
"""
from pathlib import Path

import cv2
import numpy as np

try:
    import onnxruntime as ort
    _ORT_AVAILABLE = True
except ImportError:
    _ORT_AVAILABLE = False

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"


def _letterbox(frame, size=640):
    h, w = frame.shape[:2]
    scale = min(size / h, size / w)
    nh, nw = max(1, int(round(h * scale))), max(1, int(round(w * scale)))
    resized = cv2.resize(frame, (nw, nh))
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    canvas[top:top + nh, left:left + nw] = resized
    return canvas, scale, left, top


def _nms(boxes, scores, iou_threshold=0.45):
    if not boxes:
        return []
    idxs = cv2.dnn.NMSBoxes(boxes, scores, score_threshold=0.0, nms_threshold=iou_threshold)
    if len(idxs) == 0:
        return []
    return [int(i) for i in np.array(idxs).flatten()]


class _YoloOnnxDetector:
    """Shared decode logic for Ultralytics-style ONNX exports (v8/v11)."""

    def __init__(self, model_path, input_size=640, conf_threshold=0.35, iou_threshold=0.45, class_filter=None):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = max(1, (__import__("os").cpu_count() or 4) // 2)
        self.session = ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = input_size
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.class_filter = class_filter  # None => single-class head (face); int => COCO class id to keep

    def infer(self, frame):
        canvas, scale, left, top = _letterbox(frame, self.input_size)
        blob = canvas[:, :, ::-1].astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))[None, ...]
        out = self.session.run(None, {self.input_name: blob})[0][0]  # (channels, anchors)
        out = out.T  # (anchors, channels)
        if self.class_filter is None:
            cx, cy, w, h, conf = out[:, 0], out[:, 1], out[:, 2], out[:, 3], out[:, 4]
        else:
            cx, cy, w, h = out[:, 0], out[:, 1], out[:, 2], out[:, 3]
            conf = out[:, 4 + self.class_filter]
        keep = conf >= self.conf_threshold
        if not np.any(keep):
            return []
        cx, cy, w, h, conf = cx[keep], cy[keep], w[keep], h[keep], conf[keep]
        x1 = (cx - w / 2 - left) / scale
        y1 = (cy - h / 2 - top) / scale
        bw, bh = w / scale, h / scale
        boxes = np.stack([x1, y1, bw, bh], axis=1)
        idxs = _nms(boxes.tolist(), conf.tolist(), self.iou_threshold)
        fh, fw = frame.shape[:2]
        results = []
        for i in idxs:
            x, y, bw_, bh_ = boxes[i]
            x, y = max(0, int(x)), max(0, int(y))
            bw_, bh_ = min(int(bw_), fw - x), min(int(bh_), fh - y)
            if bw_ > 0 and bh_ > 0:
                results.append((x, y, bw_, bh_))
        return results


class FaceDetector:
    """YOLOv11-face ONNX by default. Falls back to Haar cascade automatically
    if onnxruntime isn't installed or the model file is missing, so existing
    deployments don't break -- they just keep the old behaviour until the
    model is deployed alongside the app."""

    def __init__(self, enabled=True, min_size=45, model_path=None, conf_threshold=0.5):
        self.enabled = bool(enabled)
        self.min_size = int(min_size)
        self._backend = None
        path = Path(model_path) if model_path else MODELS_DIR / "yolov11n-face.onnx"
        if _ORT_AVAILABLE and path.exists():
            try:
                self._backend = _YoloOnnxDetector(path, conf_threshold=conf_threshold, class_filter=None)
                self.kind = "yolov11n-face (onnx)"
            except Exception:
                self._backend = None
        if self._backend is None:
            self.kind = "haar-cascade (fallback)"
            self.classifier = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )

    def detect(self, frame):
        if not self.enabled or frame is None:
            return []
        if self._backend is not None:
            boxes = self._backend.infer(frame)
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            boxes = [
                (int(x), int(y), int(w), int(h))
                for x, y, w, h in self.classifier.detectMultiScale(
                    gray, 1.10, 5, minSize=(self.min_size, self.min_size)
                )
            ]
        return [b for b in boxes if min(b[2], b[3]) >= self.min_size]


class PersonDetector:
    """YOLOv11n (COCO, class 0 = person) ONNX by default. Falls back to HOG
    if onnxruntime/model weights aren't available."""

    def __init__(self, enabled=True, model_path=None, conf_threshold=0.4):
        self.enabled = bool(enabled)
        self._backend = None
        path = Path(model_path) if model_path else MODELS_DIR / "yolo11n.onnx"
        if _ORT_AVAILABLE and path.exists():
            try:
                self._backend = _YoloOnnxDetector(path, conf_threshold=conf_threshold, class_filter=0)
                self.kind = "yolo11n-coco (onnx)"
            except Exception:
                self._backend = None
        if self._backend is None:
            self.kind = "hog (fallback)"
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, frame):
        if not self.enabled or frame is None:
            return []
        if self._backend is not None:
            return self._backend.infer(frame)
        boxes, _ = self.hog.detectMultiScale(frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
        return [(int(x), int(y), int(w), int(h)) for x, y, w, h in boxes]
