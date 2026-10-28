"""Pluggable face embedding backends.

OpenCVFeatureEmbedder is a dependency-light handcrafted descriptor -- a
compatibility fallback, not a claim of neural-network-grade recognition.

SFaceEmbedder wraps OpenCV's built-in FaceRecognizerSF (an ONNX model from
the OpenCV Zoo) for real neural embeddings. It is NOT bundled here: the
weight file is distributed via Git LFS and this sandbox's network egress
can't reach media.githubusercontent.com to fetch it, so it has to be pulled
once on a machine with normal internet access:

    curl -L -o models/face_recognition_sface_2021dec.onnx \\
      https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx

Then set `ai_embedding_backend = "sface"` in config/v1.toml. build_embedder()
below activates it automatically the moment the file is present -- no other
code changes needed. If the file is missing, it silently falls back to the
handcrafted descriptor so nothing breaks in the meantime.

Note: SFace's cosine similarities live on a different scale than the
handcrafted descriptor's. OpenCV's own docs use ~0.363 as the match
threshold for SFace, vs. this project's default recognition_threshold of
0.78 tuned for the handcrafted descriptor -- lower it in config/v1.toml when
you switch backends, or matches will silently stop firing.
"""
from pathlib import Path

import cv2
import numpy as np

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

class SFaceEmbedder(FaceEmbedder):
    """Neural embedding via OpenCV's FaceRecognizerSF. Produces a 128-d
    L2-normalized identity vector -- far more robust than a handcrafted
    descriptor across lighting, pose and expression changes."""

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


def build_embedder(backend="opencv"):
    if backend == "sface":
        try:
            return SFaceEmbedder()
        except Exception:
            pass  # model not deployed yet -- fall back rather than crash
    return OpenCVFeatureEmbedder()
