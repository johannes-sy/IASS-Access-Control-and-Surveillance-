"""Shared frame codec primitives.

This is where "the OpenCV core" lives: the one place that encodes/decodes
image bytes. camera_stream uses it to publish JPEG frames for the UI/MJPEG
stream; ai_perception can use it too (e.g. for stored face-preview crops)
instead of every layer calling cv2.imencode with its own quality constant.
"""
from __future__ import annotations

import cv2
import numpy as np


def encode_jpeg(frame: np.ndarray, quality: int = 82) -> bytes | None:
    """Encode a BGR frame to JPEG bytes. Returns None if encoding fails."""
    if frame is None:
        return None
    ok, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    if not ok:
        return None
    return enc.tobytes()


def decode_jpeg(data: bytes) -> np.ndarray | None:
    """Decode JPEG bytes back into a BGR frame. Returns None if decoding fails."""
    if not data:
        return None
    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return frame
