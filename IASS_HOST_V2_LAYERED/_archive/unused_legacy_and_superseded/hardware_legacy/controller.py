from __future__ import annotations

import math
import threading
import time
from typing import Callable

from .commands import HardwareCommand
from .events import HardwareAudit
from .models import (
    AlarmMode, AlarmState, CameraMode, DeviceStatus, HardwareIntent, HardwareResult,
    DoorState,
)
from .policy import HardwarePolicy
from .registry import DeviceRegistry
from .state import HardwareStateManager


class HardwareController:
    """Single semantic gateway between IASS and physical/simulated hardware."""

    def __init__(self, settings, registry, state, driver, db=None, audit=None):
        self.settings = settings
        self.registry: DeviceRegistry = registry
        self.state: HardwareStateManager = state
        self.driver = driver
        self.audit = audit or (HardwareAudit(db) if db else None)
        self.policy = HardwarePolicy(registry, settings)
        self._lock = threading.RLock()
        self._alarm_timers = {}
        self._door_timers = {}
        self._command_listeners: list[Callable] = []
        self._init_state()

    def _init_state(self):
        for d in self.registry.all():
            status = DeviceStatus.SIMULATION.value if d.driver == "mock" else DeviceStatus.DISCONNECTED.value
            if d.device_type == "CAMERA_MOUNT":
                self.state.register_camera(d.device_id, status=status)
            elif d.device_type == "DOOR_LOCK":
                self.state.register_door(d.device_id, status=status, commanded_lock=True)
            elif d.device_type == "ALARM":
                self.state.register_alarm(d.device_id, status=status)

    def start(self):
        ok = self.driver.connect()
        status = DeviceStatus.SIMULATION.value if getattr(self.driver, "simulation", False) else (DeviceStatus.CONNECTED.value if ok else DeviceStatus.DISCONNECTED.value)
        for d in self.registry.all():
            self.state.set_device_status(d.device_id, status)
        return ok

    def stop(self):
        for timer in list(self._alarm_timers.values()) + list(self._door_timers.values()):
            try: timer.cancel()
            except Exception: pass
        self._alarm_timers.clear()
        self._door_timers.clear()
        self.driver.close()

    def _result(self, success, device_id, action, **kwargs):
        r = HardwareResult(success=success, device_id=device_id, action=action, **kwargs)
        if self.audit:
            self.audit.command(r)
        for listener in list(self._command_listeners):
            try: listener(r)
            except Exception: pass
        return r

    def add_command_listener(self, callback):
        self._command_listeners.append(callback)

    def _definition(self, device_id, expected=None):
        d = self.registry.get(device_id)
        if not d:
            raise ValueError(f"Unknown hardware device: {device_id}")
        if not d.enabled:
            raise ValueError(f"Hardware device is disabled: {device_id}")
        if expected and d.device_type != expected:
            raise ValueError(f"{device_id} is not a {expected} device")
        return d

    def rotate_camera(self, camera_id: str, pan_angle: float, tilt_angle: float = 0.0,
                      speed: float = 1.0, correlation_id=None):
        d = self._definition(camera_id, "CAMERA_MOUNT")
        lim = d.limits
        if not (float(lim.get("min_pan", -180)) <= pan_angle <= float(lim.get("max_pan", 180))):
            return self._result(False, camera_id, "ROTATE_CAMERA", result="ANGLE_LIMIT", error="Pan angle exceeds configured limits", requested_state="POSITION", details={"pan": pan_angle})
        if not (float(lim.get("min_tilt", -90)) <= tilt_angle <= float(lim.get("max_tilt", 90))):
            return self._result(False, camera_id, "ROTATE_CAMERA", result="ANGLE_LIMIT", error="Tilt angle exceeds configured limits", requested_state="POSITION", details={"tilt": tilt_angle})
        speed = max(0.01, min(float(lim.get("max_speed", 1.0)), float(speed)))
        current = self.state.cameras[camera_id]
        previous = current.pan
        # V1 physical protocol supports incremental pan. Convert requested absolute angle to a bounded step.
        delta = float(pan_angle) - float(current.pan)
        steps = int(round(delta))
        connected = self.driver.connected
        if not connected:
            return self._result(False, camera_id, "ROTATE_CAMERA", result="DISCONNECTED", error="Hardware driver is disconnected", requested_state="POSITION", actual_state=str(current.pan), correlation_id=correlation_id, details={"pan": pan_angle, "tilt": tilt_angle})
        if not self.driver.command(camera_id, "PAN_STEP", steps=steps):
            self.state.set_device_status(camera_id, DeviceStatus.DISCONNECTED.value)
            return self._result(False, camera_id, "ROTATE_CAMERA", result="DISCONNECTED", error="Hardware command failed", requested_state="POSITION", actual_state=str(current.pan), correlation_id=correlation_id)
        self.state.update_camera(camera_id, pan=pan_angle, target_pan=pan_angle, tilt=tilt_angle, target_tilt=tilt_angle, speed=speed, direction="RIGHT" if delta > 0 else "LEFT" if delta < 0 else "CENTER", mode=CameraMode.IDLE.value, last_command=time.time())
        self.state.set_device_status(camera_id, DeviceStatus.CONNECTED.value if d.driver != "mock" else DeviceStatus.SIMULATION.value)
        if self.audit:
            self.audit.event(camera_id, "CAMERA_POSITION_CHANGED", str(previous), str(pan_angle), correlation_id, {"tilt": tilt_angle})
        return self._result(True, camera_id, "ROTATE_CAMERA", result="SUCCESS", requested_state="POSITION", actual_state=str(pan_angle), correlation_id=correlation_id, details={"pan": pan_angle, "tilt": tilt_angle, "speed": speed})

    def track_camera(self, camera_id: str, target_x: float, target_y: float,
                     frame_width: int, frame_height: int, correlation_id=None):
        d = self._definition(camera_id, "CAMERA_MOUNT")
        x = float(target_x)
        center = float(frame_width) / 2.0
        error = x - center
        deadband = float(getattr(self.settings, "pan_deadband_px", 45))
        if abs(error) <= deadband:
            return self.stop_camera(camera_id, correlation_id=correlation_id)
        kp = float(getattr(self.settings, "pan_kp", 0.045))
        step = max(1, min(int(getattr(self.settings, "max_step_command", 8)), int(abs(error) * kp)))
        direction = 1 if error > 0 else -1
        current = self.state.cameras[camera_id].pan
        target = current + direction * step
        result = self.rotate_camera(camera_id, target, self.state.cameras[camera_id].tilt, correlation_id=correlation_id)
        if result.success:
            self.state.update_camera(camera_id, mode=CameraMode.TRACKING.value, direction="RIGHT" if direction > 0 else "LEFT", target_id=correlation_id)
        return result

    def stop_camera(self, camera_id: str, correlation_id=None):
        self._definition(camera_id, "CAMERA_MOUNT")
        if not self.driver.connected:
            return self._result(False, camera_id, "STOP_CAMERA", result="DISCONNECTED", error="Hardware driver is disconnected", correlation_id=correlation_id)
        ok = self.driver.command(camera_id, "STOP")
        if not ok:
            return self._result(False, camera_id, "STOP_CAMERA", result="DISCONNECTED", error="Hardware command failed", correlation_id=correlation_id)
        self.state.update_camera(camera_id, mode=CameraMode.STOPPED.value, direction="CENTER")
        return self._result(True, camera_id, "STOP_CAMERA", result="SUCCESS", actual_state=CameraMode.STOPPED.value, correlation_id=correlation_id)

    def emergency_stop(self, correlation_id=None):
        """Software emergency stop for movable hardware; physical E-stop remains authoritative."""
        results = []
        for camera_id in list(self.state.cameras):
            results.append(self.stop_camera(camera_id, correlation_id=correlation_id or "EMERGENCY-STOP"))
        return {"success": all(r.success for r in results) if results else True, "results": [r.to_dict() for r in results]}

    def home_camera(self, camera_id: str, correlation_id=None):
        return self.rotate_camera(camera_id, 0.0, 0.0, 0.5, correlation_id=correlation_id)

    def lock_door(self, door_id: str, duration: float | None = None, reason=None, correlation_id=None):
        self._definition(door_id, "DOOR_LOCK")
        if not self.driver.connected:
            return self._result(False, door_id, "LOCK_DOOR", result="DISCONNECTED", error="Hardware driver is disconnected", requested_state=DoorState.LOCKED.value, correlation_id=correlation_id)
        previous = self.state.doors[door_id].state
        if not self.driver.command(door_id, "LOCK"):
            self.state.update_door(door_id, state=DoorState.FAULT.value, fault="LOCK_COMMAND_FAILED")
            return self._result(False, door_id, "LOCK_DOOR", result="FAULT", error="Lock command failed", requested_state=DoorState.LOCKED.value, actual_state=previous, correlation_id=correlation_id)
        self.state.update_door(door_id, commanded_lock=True, actual_lock=True if self.registry.get(door_id).driver == "mock" else None, state=DoorState.LOCKED.value if self.registry.get(door_id).driver == "mock" else DoorState.UNKNOWN.value, unlock_until=None, fault=None)
        if self.audit:
            self.audit.event(door_id, "LOCK_CONFIRMED" if self.registry.get(door_id).driver == "mock" else "LOCK_COMMAND_SENT", previous, self.state.doors[door_id].state, correlation_id, {"reason": reason})
        return self._result(True, door_id, "LOCK_DOOR", requested_state=DoorState.LOCKED.value, actual_state=self.state.doors[door_id].state, correlation_id=correlation_id, details={"reason": reason})

    def unlock_door(self, door_id: str, duration: float | None = None, reason=None, correlation_id=None):
        self._definition(door_id, "DOOR_LOCK")
        max_duration = float(self.registry.get(door_id).limits.get("max_unlock_duration", 10))
        duration = max_duration if duration is None else max(0.1, min(float(duration), max_duration))
        if not self.driver.connected:
            return self._result(False, door_id, "UNLOCK_DOOR", result="DISCONNECTED", error="Hardware driver is disconnected", requested_state=DoorState.UNLOCKED.value, correlation_id=correlation_id)
        if not self.driver.command(door_id, "UNLOCK", duration=duration):
            return self._result(False, door_id, "UNLOCK_DOOR", result="FAULT", error="Unlock command failed", correlation_id=correlation_id)
        self.state.update_door(door_id, commanded_lock=False, actual_lock=False if self.registry.get(door_id).driver == "mock" else None, state=DoorState.UNLOCKED.value if self.registry.get(door_id).driver == "mock" else DoorState.UNKNOWN.value, unlock_until=time.time() + duration, fault=None)
        if door_id in self._door_timers:
            self._door_timers[door_id].cancel()
        timer = threading.Timer(duration, lambda: self.lock_door(door_id, reason="AUTO_RELOCK", correlation_id=correlation_id))
        timer.daemon = True
        self._door_timers[door_id] = timer
        timer.start()
        if self.audit:
            self.audit.event(door_id, "UNLOCK_COMMAND_SENT", None, self.state.doors[door_id].state, correlation_id, {"duration": duration, "reason": reason})
        return self._result(True, door_id, "UNLOCK_DOOR", requested_state=DoorState.UNLOCKED.value, actual_state=self.state.doors[door_id].state, correlation_id=correlation_id, details={"duration": duration, "reason": reason})

    def trigger_alarm(self, alarm_id: str, mode: str = AlarmMode.SIREN_STROBE.value, duration: float | None = None, reason=None, correlation_id=None):
        self._definition(alarm_id, "ALARM")
        d = self.registry.get(alarm_id)
        if mode not in {m.value for m in AlarmMode}:
            return self._result(False, alarm_id, "TRIGGER_ALARM", result="INVALID", error=f"Unsupported alarm mode: {mode}", correlation_id=correlation_id)
        duration = float(d.limits.get("max_duration", 120)) if duration is None else max(0.1, min(float(duration), float(d.limits.get("max_duration", 120))))
        if not self.driver.connected:
            return self._result(False, alarm_id, "TRIGGER_ALARM", result="DISCONNECTED", error="Hardware driver is disconnected", correlation_id=correlation_id)
        if not self.driver.command(alarm_id, "ALARM_TRIGGER", mode=mode, duration=duration):
            return self._result(False, alarm_id, "TRIGGER_ALARM", result="FAULT", error="Alarm command failed", correlation_id=correlation_id)
        self.state.update_alarm(alarm_id, state=AlarmState.TRIGGERED.value, mode=mode, triggered_by=reason, triggered_at=time.time(), remaining_seconds=duration, fault=None)
        timer = threading.Timer(duration, lambda: self.clear_alarm(alarm_id, reason="AUTO_CLEAR", correlation_id=correlation_id))
        timer.daemon = True
        old = self._alarm_timers.get(alarm_id)
        if old: old.cancel()
        self._alarm_timers[alarm_id] = timer
        timer.start()
        if self.audit:
            self.audit.event(alarm_id, "ALARM_TRIGGERED", None, AlarmState.TRIGGERED.value, correlation_id, {"mode": mode, "duration": duration, "reason": reason})
        return self._result(True, alarm_id, "TRIGGER_ALARM", requested_state=AlarmState.TRIGGERED.value, actual_state=AlarmState.TRIGGERED.value, correlation_id=correlation_id, details={"mode": mode, "duration": duration, "reason": reason})

    def clear_alarm(self, alarm_id: str, reason=None, correlation_id=None):
        self._definition(alarm_id, "ALARM")
        if not self.driver.connected:
            return self._result(False, alarm_id, "CLEAR_ALARM", result="DISCONNECTED", error="Hardware driver is disconnected", correlation_id=correlation_id)
        if not self.driver.command(alarm_id, "ALARM_CLEAR"):
            return self._result(False, alarm_id, "CLEAR_ALARM", result="FAULT", error="Alarm clear command failed", correlation_id=correlation_id)
        self.state.update_alarm(alarm_id, state=AlarmState.ARMED.value, remaining_seconds=None, triggered_by=None)
        if self.audit:
            self.audit.event(alarm_id, "ALARM_CLEARED", AlarmState.TRIGGERED.value, AlarmState.ARMED.value, correlation_id, {"reason": reason})
        return self._result(True, alarm_id, "CLEAR_ALARM", actual_state=AlarmState.ARMED.value, correlation_id=correlation_id)

    def apply_feedback(self, device_id: str, state: str | None = None, details: dict | None = None, correlation_id=None):
        """Apply MCU/sensor feedback without exposing transport details to upper layers."""
        d = self._definition(device_id)
        details = details or {}
        previous = self.state.device(device_id) or {}
        if d.device_type == "CAMERA_MOUNT":
            changes = {}
            for key in ("pan", "tilt", "target_pan", "target_tilt", "mode", "direction", "fault"):
                if key in details: changes[key] = details[key]
            if state: changes["mode"] = state
            self.state.update_camera(device_id, **changes)
        elif d.device_type == "DOOR_LOCK":
            changes = {}
            if state: changes["state"] = state
            for key in ("actual_lock", "sensor", "fault"):
                if key in details: changes[key] = details[key]
            self.state.update_door(device_id, **changes)
        elif d.device_type == "ALARM":
            changes = {}
            if state: changes["state"] = state
            for key in ("mode", "fault", "remaining_seconds"):
                if key in details: changes[key] = details[key]
            self.state.update_alarm(device_id, **changes)
        self.state.set_device_status(device_id, DeviceStatus.CONNECTED.value, details.get("fault"))
        if self.audit:
            self.audit.event(device_id, "TELEMETRY_FEEDBACK", previous.get("state"), state, correlation_id, details)
        return self.state.device(device_id)

    def process_access_request(self, reader_id: str, door_id: str, identity: str | None, authorized: bool,
                               person_id: int | None = None, credential_ref: str | None = None,
                               unlock_duration: float = 5.0, correlation_id=None):
        """Semantic RFID/access-control entry point. Credential values are never sent to drivers."""
        correlation_id = correlation_id or f"ACCESS-{int(time.time()*1000)}"
        decision = "ALLOW" if authorized else "DENY"
        if self.audit and getattr(self.audit, "db", None):
            self.audit.db.access_event(reader_id, door_id, identity, authorized, decision, person_id, credential_ref, correlation_id)
        if authorized:
            result = self.unlock_door(door_id, duration=unlock_duration, reason="AUTHORIZED_ACCESS", correlation_id=correlation_id)
        else:
            result = self.lock_door(door_id, reason="UNAUTHORIZED_ACCESS", correlation_id=correlation_id)
        if self.audit:
            self.audit.event(door_id, "ACCESS_ALLOWED" if authorized else "ACCESS_DENIED", None, result.actual_state, correlation_id, {"reader_id": reader_id, "identity": identity, "decision": decision})
        return {"decision": decision, "result": result.to_dict(), "correlation_id": correlation_id}

    def handle_intent(self, intent: HardwareIntent):
        results = []
        for action, device_id, params in self.policy.actions_for_intent(intent):
            if action == "TRACK_CAMERA":
                t = params.get("target", {})
                result = self.track_camera(device_id, t.get("x", 0), t.get("y", 0), t.get("frame_width", 640), t.get("frame_height", 480), intent.correlation_id)
            elif action == "STOP_CAMERA":
                result = self.stop_camera(device_id, intent.correlation_id)
            elif action == "LOCK_DOOR":
                result = self.lock_door(device_id, reason=intent.intent, correlation_id=intent.correlation_id)
            elif action == "TRIGGER_ALARM":
                result = self.trigger_alarm(device_id, correlation_id=intent.correlation_id, **{k: v for k, v in params.items() if k != "reason"}, reason=params.get("reason"))
            else:
                continue
            results.append(result)
        return results

    def snapshot(self):
        return self.state.snapshot()
