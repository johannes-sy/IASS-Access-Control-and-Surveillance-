from __future__ import annotations
class CameraController:
    """Task-level camera control; transport/protocol details stay below it."""

    def __init__(self, command_bus):
        self.bus = command_bus

    def home(self, camera_id: str) -> bool:
        return self.bus.command("CAMERA_HOME", camera_id)

    def stop(self, camera_id: str) -> bool:
        return self.bus.command("CAMERA_STOP", camera_id)

    def pan(self, camera_id: str, delta: int) -> bool:
        delta = max(-15, min(15, int(delta)))
        return self.bus.command("CAMERA_PAN", camera_id, delta)

    def tilt(self, camera_id: str, delta: int) -> bool:
        delta = max(-15, min(15, int(delta)))
        return self.bus.command("CAMERA_TILT", camera_id, delta)
