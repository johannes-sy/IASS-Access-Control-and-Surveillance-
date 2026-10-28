import threading
import time

import cv2
import numpy as np


class FrameHub:
    """Thread-safe latest-frame buffer shared by camera, UI and AI subsystems."""

    def __init__(self, jpeg_quality=82, stale_after=2.5):
        self._lock = threading.Lock()
        self._frame = None
        self._jpeg = None
        self._ts = 0.0
        self._seq = 0
        self.jpeg_quality = int(jpeg_quality)
        self.stale_after = float(stale_after)
        self.source = "none"
        self.connected = False

    def publish(self, frame, source="camera"):
        if frame is None:
            return False
        ok, enc = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        )
        if not ok:
            return False
        with self._lock:
            self._frame = frame.copy()
            self._jpeg = enc.tobytes()
            self._ts = time.time()
            self._seq += 1
            self.source = source
            self.connected = True
        return True

    def _is_fresh_locked(self):
        return bool(self._ts and (time.time() - self._ts) <= self.stale_after)

    def jpeg(self):
        """Return the latest JPEG, or a visible waiting placeholder."""
        with self._lock:
            if self._jpeg is not None and self._is_fresh_locked():
                return self._jpeg
            self.connected = False
        return self._placeholder()

    def frame(self):
        with self._lock:
            if self._frame is None or not self._is_fresh_locked():
                return None
            return self._frame.copy()

    def status(self):
        with self._lock:
            fresh = self._is_fresh_locked()
            if not fresh:
                self.connected = False
            age = None if not self._ts else round((time.time() - self._ts) * 1000, 1)
            return {
                "connected": bool(self.connected and fresh),
                "source": self.source,
                "age_ms": age,
                "sequence": self._seq,
            }

    def clear(self, source="none"):
        with self._lock:
            self._frame = None
            self._jpeg = None
            self._ts = 0.0
            self.connected = False
            self.source = source

    def _placeholder(self):
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            image,
            "IASS CAMERA - WAITING FOR CONNECTION",
            (65, 220),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.78,
            (220, 220, 220),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            image,
            "Open /camera on the phone to start streaming",
            (74, 265),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (150, 150, 150),
            1,
            cv2.LINE_AA,
        )
        _, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        return jpeg.tobytes()
