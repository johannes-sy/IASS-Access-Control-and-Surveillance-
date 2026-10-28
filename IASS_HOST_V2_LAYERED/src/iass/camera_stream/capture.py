import threading
import time

import cv2
import numpy as np


class CameraManager:
    def __init__(self, hub, settings, on_frame=None):
        self.hub = hub
        self.s = settings
        self.on_frame = on_frame
        self.stop = threading.Event()
        self.thread = None
        self.cap = None
        self.state = "WAITING" if settings.camera_source == "phone_browser" else "INITIALIZING"
        self.error = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop.clear()
        self.thread = threading.Thread(target=self._run, name="iass-camera", daemon=True)
        self.thread.start()

    def _run(self):
        try:
            if self.s.camera_source == "opencv":
                self._opencv(self.s.camera_url or 0)
            elif self.s.camera_source == "synthetic":
                self._synthetic()
            elif self.s.camera_source == "phone_browser":
                # The phone pushes frames through /ws/camera. No capture thread is needed.
                self.state = "WAITING"
            else:
                self.state = "ERROR"
                self.error = f"Unknown camera source: {self.s.camera_source}"
        except Exception as exc:
            self.state = "ERROR"
            self.error = str(exc)

    def _opencv(self, src):
        self.state = "INITIALIZING"
        while not self.stop.is_set():
            try:
                self.cap = cv2.VideoCapture(src)
                if not self.cap.isOpened():
                    self.state = "WAITING"
                    self.error = f"Unable to open camera source: {src}"
                    if self.cap:
                        self.cap.release()
                    self.cap = None
                    self.hub.clear("opencv")
                    self.stop.wait(2.0)
                    continue

                self.state = "LIVE"
                self.error = None
                while not self.stop.is_set():
                    ok, frame = self.cap.read()
                    if ok and self.hub.publish(frame, "opencv"):
                        self.state = "LIVE"
                        if self.on_frame is not None:
                            self.on_frame(frame)
                    else:
                        self.state = "DISCONNECTED"
                        self.hub.clear("opencv")
                        break
                if self.cap:
                    self.cap.release()
                self.cap = None
                if not self.stop.is_set():
                    self.stop.wait(1.0)
            except Exception as exc:
                self.state = "ERROR"
                self.error = str(exc)
                self.hub.clear("opencv")
                if self.cap:
                    self.cap.release()
                self.cap = None
                self.stop.wait(2.0)

    def _synthetic(self):
        self.state = "LIVE"
        self.error = None
        while not self.stop.is_set():
            frame = np.zeros((480, 640, 3), np.uint8)
            cv2.putText(
                frame,
                "IASS SYNTHETIC CAMERA",
                (125, 225),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (220, 220, 220),
                2,
            )
            self.hub.publish(frame, "synthetic")
            if self.on_frame is not None:
                self.on_frame(frame)
            self.stop.wait(0.1)

    def mark_phone_connected(self):
        self.state = "LIVE"
        self.error = None

    def mark_phone_disconnected(self):
        self.state = "DISCONNECTED"

    def status(self):
        return {"state": self.state, "error": self.error}

    def stop_now(self):
        self.stop.set()
        if self.cap:
            self.cap.release()
            self.cap = None
