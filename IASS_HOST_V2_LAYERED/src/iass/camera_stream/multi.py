"""Thread-safe independent frame buffers for multiple live camera sources."""
from __future__ import annotations

import threading
from typing import Dict

from .framehub import FrameHub


class MultiCameraHub:
    def __init__(self, camera_ids, jpeg_quality=82, stale_after=2.5):
        self._hubs: Dict[str, FrameHub] = {
            str(cid): FrameHub(jpeg_quality, stale_after) for cid in camera_ids
        }
        self._lock = threading.RLock()

    def ensure(self, camera_id: str) -> FrameHub:
        with self._lock:
            if camera_id not in self._hubs:
                self._hubs[camera_id] = FrameHub()
            return self._hubs[camera_id]

    def publish(self, camera_id, frame, source="camera"):
        return self.ensure(str(camera_id)).publish(frame, source)

    def status(self, camera_id):
        return self.ensure(str(camera_id)).status()

    def jpeg(self, camera_id):
        return self.ensure(str(camera_id)).jpeg()

    def frame(self, camera_id):
        return self.ensure(str(camera_id)).frame()

    def clear(self, camera_id, source="none"):
        self.ensure(str(camera_id)).clear(source)

    def snapshot(self):
        with self._lock:
            return {cid: hub.status() for cid, hub in self._hubs.items()}
