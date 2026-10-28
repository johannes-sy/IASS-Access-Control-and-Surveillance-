"""Pluggable face embedding backends.

OpenCVFeatureEmbedder is a dependency-light handcrafted descriptor -- a
compatibility fallback, not a claim of neural-network-grade recognition.

ArcFaceEmbedder wraps a real ArcFace (ResNet50, WebFace600K) recognition
network via ONNX Runtime -- this is the same model InsightFace's "buffalo_l"
bundle uses, an industry-standard face recognition architecture, not a
toy descriptor. The weight file ships in this project at
models/arcface_w600k_r50.onnx (downloaded from InsightFace's official
GitHub release, github.com/deepinsight/insightface/releases/tag/v0.7 --
this one *is* bundled, unlike the SFace option below, because it's
distributed as a plain release asset rather than Git LFS). This is now the
default backend.

SFaceEmbedder wraps OpenCV's built-in FaceRecognizerSF as a second neural
option. It is NOT bundled: the weight file is distributed via Git LFS and
this sandbox's network egress can't reach media.githubusercontent.com to
fetch it, so it has to be pulled once on a machine with normal internet
access:

    curl -L -o models/face_recognition_sface_2021dec.onnx \\
      https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx

Then set `ai_embedding_backend = "sface"` in config/v1.toml.

build_embedder() tries arcface -> sface -> handcrafted, in that order,
falling through silently whenever a model file or onnxruntime isn't
available, so nothing ever crashes for lack of a model -- it just degrades.

Note on thresholds: each backend's cosine similarities live on a different
scale. ArcFace (the new default) typically separates same/different person
around ~0.36-0.42 cosine similarity for buffalo_l; this project's default
recognition_threshold is now tuned to that. SFace's own docs use ~0.363.
The old handcrafted descriptor was tuned around 0.78. If you switch
backends explicitly, re-tune recognition_threshold in config/v1.toml.

Caveat worth knowing: ArcFace's accuracy depends on the input crop being a
tightly, consistently framed face. This project currently feeds it plain
detector bounding-box crops (no landmark-based alignment), which is a real
step below InsightFace's own pipeline -- their detector (RetinaFace, also
bundled in the same release under a different filename) emits 5-point
landmarks used to warp each face into a canonical pose before embedding.
Unaligned crops still work meaningfully better than the handcrafted
descriptor, but landmark alignment is the next lever if you want to close
the rest of the gap -- flagged here rather than silently left out.
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

class FaceEmbedder:
    def embed(self, crop):
        raise NotImplementedError

class OpenCVFeatureEmbedder(FaceEmbedder):
    """Stable handcrafted descriptor used when no neural model is installed."""
    def embed(self, crop):
        if crop is None or crop.size == 0:
            raise ValueError("empty face")
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (64,64), interpolation=cv2.INTER_AREA)
        # Multi-scale normalized intensity + gradient orientation histogram.
        gray = cv2.equalizeHist(gray).astype(np.float32) / 255.0
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
        mag, ang = cv2.cartToPolar(gx, gy)
        hist = []
        for cell_y in range(0, 64, 8):
            for cell_x in range(0, 64, 8):
                m = mag[cell_y:cell_y+8, cell_x:cell_x+8].ravel()
                a = (ang[cell_y:cell_y+8, cell_x:cell_x+8].ravel() * 180.0 / np.pi) % 180.0
                h, _ = np.histogram(a, bins=9, range=(0,180), weights=m)
                hist.extend(h.tolist())
        vec = np.concatenate([gray[::4,::4].ravel(), np.asarray(hist, np.float32)])
        vec = vec.astype(np.float32)
        norm = float(np.linalg.norm(vec))
        return vec / max(norm, 1e-8)


class ArcFaceEmbedder(FaceEmbedder):
    """Real ArcFace (ResNet50 / WebFace600K) embedding via ONNX Runtime.
    Produces a 512-d L2-normalized identity vector. Default backend."""

    def __init__(self, model_path=None):
        if not _ORT_AVAILABLE:
            raise RuntimeError("onnxruntime not installed")
        path = Path(model_path) if model_path else MODELS_DIR / "arcface_w600k_r50.onnx"
        if not path.exists():
            raise FileNotFoundError(f"ArcFace model not found at {path}")
        self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def embed(self, crop):
        if crop is None or crop.size == 0:
            raise ValueError("empty face")
        face = cv2.resize(crop, (112, 112))
        face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB).astype(np.float32)
        face = (face - 127.5) / 127.5
        blob = np.transpose(face, (2, 0, 1))[None, ...]
        feat = self.session.run(None, {self.input_name: blob})[0][0]
        vec = feat.astype(np.float32)
        norm = float(np.linalg.norm(vec))
        return vec / max(norm, 1e-8)


class SFaceEmbedder(FaceEmbedder):
    """Neural embedding via OpenCV's FaceRecognizerSF. Produces a 128-d
    L2-normalized identity vector. Alternative to ArcFace; not bundled
    (see module docstring)."""

    def __init__(self, model_path=None):
        path = Path(model_path) if model_path else MODELS_DIR / "face_recognition_sface_2021dec.onnx"
        if not path.exists():
            raise FileNotFoundError(f"SFace model not found at {path}")
        self._recognizer = cv2.FaceRecognizerSF_create(str(path), "")

    def embed(self, crop):
        if crop is None or crop.size == 0:
            raise ValueError("empty face")
        face = cv2.resize(crop, (112, 112))
        feat = self._recognizer.feature(face)
        vec = feat.flatten().astype(np.float32)
        norm = float(np.linalg.norm(vec))
        return vec / max(norm, 1e-8)


def build_embedder(backend="arcface"):
    if backend == "arcface":
        try:
            return ArcFaceEmbedder()
        except Exception:
            pass  # onnxruntime missing or model not deployed -- fall through
    if backend in ("arcface", "sface"):
        try:
            return SFaceEmbedder()
        except Exception:
            pass
    return OpenCVFeatureEmbedder()
