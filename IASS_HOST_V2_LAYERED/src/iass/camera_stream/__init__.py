"""camera_stream layer.

Owns getting frames off physical/virtual sources -- USB webcam via OpenCV,
a phone acting as a camera over the local hotspot/Wi-Fi (browser push), or
a synthetic test source -- and republishing them for both the UI (MJPEG)
and ai_perception to consume. Nothing here knows about detection, tracking,
or hardware; it only knows about getting pixels in and JPEGs/frames out.

CameraManager  - drives a single capture source (usb/opencv, phone/browser
                 push, or synthetic).
FrameHub       - thread-safe latest-frame buffer for one camera, shared
                 between the UI stream and the AI worker.
MultiCameraHub - keyed collection of FrameHub instances so multiple cameras
                 (e.g. one USB + one phone-over-hotspot) can run at once
                 without the UI/AI needing to know how many there are.
"""
from .capture import CameraManager
from .framehub import FrameHub
from .multi import MultiCameraHub

__all__ = ["CameraManager", "FrameHub", "MultiCameraHub"]
