import time


class CameraTracker:
    """Resilient target-to-pan controller with deadband, rate limiting and target-loss stop."""

    def __init__(self, frame_width=640, deadband_px=25, max_pan_step=15, kp=0.1, min_cmd_interval=0.1):
        self.frame_width = int(frame_width)
        self.center_x = self.frame_width // 2
        self.deadband_px = int(deadband_px)
        self.max_pan_step = int(max_pan_step)
        self.kp = float(kp)
        self.last_command = ""
        self.last_cmd_time = 0.0
        self.min_cmd_interval = float(min_cmd_interval)

    def compute_pan_command(self, face_bbox=None) -> str:
        now = time.time()
        if face_bbox is None:
            return self._filter_command("$IASS,CAM1,STOP,CHK\n", now, suppress_duplicate=True)
        x1, y1, x2, y2 = face_bbox
        face_cx = (float(x1) + float(x2)) / 2.0
        error_x = face_cx - self.center_x
        if abs(error_x) <= self.deadband_px:
            return self._filter_command("$IASS,CAM1,STOP,CHK\n", now, suppress_duplicate=True)
        step_size = min(max(1, int(abs(error_x) * self.kp)), self.max_pan_step)
        direction = "+" if error_x > 0 else "-"
        return self._filter_command(f"$IASS,CAM1,PAN,{direction}{step_size:02d},CHK\n", now)

    def _filter_command(self, cmd: str, now: float, suppress_duplicate=False) -> str:
        if suppress_duplicate and cmd == self.last_command:
            return ""
        if now - self.last_cmd_time < self.min_cmd_interval:
            return ""
        self.last_command = cmd
        self.last_cmd_time = now
        return cmd


class TrackerController:
    """Existing tracking interface. Physical movement is delegated to HardwareController."""

    def __init__(self, settings, link=None, hardware=None, camera_id="camera_mount_1"):
        self.s = settings
        self.link = link
        self.hardware = hardware
        self.camera_id = camera_id
        self.enabled = settings.tracking_enabled
        self.controller = CameraTracker(
            frame_width=640,
            deadband_px=settings.pan_deadband_px,
            max_pan_step=settings.max_step_command,
            kp=settings.pan_kp,
            min_cmd_interval=max(0.0, settings.command_interval_ms / 1000.0),
        )
        self._last_bbox = None

    def update(self, bbox, frame_width, frame_height=480, correlation_id=None):
        if not self.enabled:
            return None
        self.controller.frame_width = int(frame_width)
        self.controller.center_x = int(frame_width) // 2
        self._last_bbox = bbox
        x, y, w, h = [float(v) for v in bbox]
        cx, cy = x + w / 2.0, y + h / 2.0
        if self.hardware is not None:
            return self.hardware.track_camera(
                self.camera_id,
                cx,
                cy,
                int(frame_width),
                int(frame_height),
                correlation_id=correlation_id,
            )
        # Compatibility fallback for callers from older V1 integrations.
        tracking_bbox = (x, y, x + w, y + h)
        cmd = self.controller.compute_pan_command(tracking_bbox)
        if not cmd or self.link is None:
            return None
        if "STOP" in cmd:
            self.link.send_stop(min_interval_ms=self.s.command_interval_ms)
        else:
            steps = int(cmd.split("PAN,")[1].split(",")[0])
            self.link.send_pan(steps, min_interval_ms=self.s.command_interval_ms)
        return None

    def target_lost(self, correlation_id=None):
        if not self.enabled:
            return None
        self._last_bbox = None
        if self.hardware is not None:
            return self.hardware.stop_camera(self.camera_id, correlation_id=correlation_id)
        cmd = self.controller.compute_pan_command(None)
        if cmd and self.link is not None:
            self.link.send_stop(min_interval_ms=self.s.command_interval_ms)
        return None

    def set_enabled(self, value):
        value = bool(value)
        if self.enabled and not value:
            self.target_lost()
        self.enabled = value
