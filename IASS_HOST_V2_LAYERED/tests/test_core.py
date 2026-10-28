import numpy as np
import cv2

from iass.camera_stream.framehub import FrameHub

def test_framehub_jpeg_status():
    h=FrameHub(); f=np.zeros((20,20,3),np.uint8); assert h.publish(f); assert h.jpeg(); assert h.status()["connected"]

def test_framehub_placeholder_without_camera():
    h=FrameHub(); data=h.jpeg(); assert data and data[:2] == b"\xff\xd8"; assert not h.status()["connected"]

def test_framehub_clear():
    h=FrameHub(); f=np.zeros((20,20,3),np.uint8); h.publish(f); h.clear(); assert not h.status()["connected"]; assert h.frame() is None


def test_camera_tracker_deadband_and_target_loss():
    from iass.hardware_control.camera_tracking import CameraTracker
    t = CameraTracker(frame_width=640, deadband_px=20, max_pan_step=15, kp=0.1, min_cmd_interval=0)
    assert "STOP" in t.compute_pan_command((300, 100, 340, 200))
    assert "PAN,+" in t.compute_pan_command((500, 100, 540, 200))
    assert "STOP" in t.compute_pan_command(None)
    assert t.compute_pan_command(None) == ""


def test_arduino_disabled_is_safe():
    from iass.hardware_interface.serial_link import ArduinoLink
    link = ArduinoLink(False, "/dev/does-not-exist", 115200)
    assert not link.connect()
    assert link.state == "DISABLED"
    link.send_pan(5)
    link.send_stop()
    link.stop()
