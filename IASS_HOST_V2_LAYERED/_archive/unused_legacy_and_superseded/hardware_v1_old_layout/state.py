from __future__ import annotations

import threading
import time
from dataclasses import asdict
from copy import deepcopy

from .models import CameraState, DoorStateRecord, AlarmStateRecord, DeviceStatus


class HardwareStateManager:
    """Thread-safe latest-known state for every physical/simulated device."""

    def __init__(self):
        self._lock = threading.RLock()
        self.cameras: dict[str, CameraState] = {}
        self.doors: dict[str, DoorStateRecord] = {}
        self.alarms: dict[str, AlarmStateRecord] = {}
        self.devices: dict[str, dict] = {}

    def register_camera(self, device_id, **kwargs):
        with self._lock:
            self.cameras[device_id] = CameraState(device_id=device_id, **kwargs)
            self._register_device(device_id, "CAMERA_MOUNT", self.cameras[device_id].status)

    def register_door(self, device_id, **kwargs):
        with self._lock:
            self.doors[device_id] = DoorStateRecord(device_id=device_id, **kwargs)
            self._register_device(device_id, "DOOR_LOCK", self.doors[device_id].status)

    def register_alarm(self, device_id, **kwargs):
        with self._lock:
            self.alarms[device_id] = AlarmStateRecord(device_id=device_id, **kwargs)
            self._register_device(device_id, "ALARM", self.alarms[device_id].status)

    def _register_device(self, device_id, device_type, status):
        self.devices[device_id] = {
            "device_id": device_id,
            "device_type": device_type,
            "status": status,
            "last_seen": None,
            "fault": None,
        }

    def set_device_status(self, device_id, status, fault=None):
        with self._lock:
            if device_id in self.devices:
                self.devices[device_id]["status"] = status
                self.devices[device_id]["fault"] = fault
                if status in (DeviceStatus.CONNECTED.value, DeviceStatus.SIMULATION.value):
                    self.devices[device_id]["last_seen"] = time.time()
            for collection in (self.cameras, self.doors, self.alarms):
                record = collection.get(device_id)
                if record:
                    record.status = status
                    record.fault = fault

    def touch(self, device_id):
        with self._lock:
            if device_id in self.devices:
                self.devices[device_id]["last_seen"] = time.time()

    def update_camera(self, device_id, **changes):
        with self._lock:
            obj = self.cameras[device_id]
            for k, v in changes.items():
                if hasattr(obj, k):
                    setattr(obj, k, v)
            self.touch(device_id)

    def update_door(self, device_id, **changes):
        with self._lock:
            obj = self.doors[device_id]
            for k, v in changes.items():
                if hasattr(obj, k):
                    setattr(obj, k, v)
            self.touch(device_id)

    def update_alarm(self, device_id, **changes):
        with self._lock:
            obj = self.alarms[device_id]
            for k, v in changes.items():
                if hasattr(obj, k):
                    setattr(obj, k, v)
            self.touch(device_id)

    def snapshot(self):
        with self._lock:
            return {
                "cameras": {k: asdict(deepcopy(v)) for k, v in self.cameras.items()},
                "doors": {k: asdict(deepcopy(v)) for k, v in self.doors.items()},
                "alarms": {k: asdict(deepcopy(v)) for k, v in self.alarms.items()},
                "devices": deepcopy(self.devices),
                "timestamp": time.time(),
            }

    def device(self, device_id):
        snap = self.snapshot()
        for group in ("cameras", "doors", "alarms"):
            if device_id in snap[group]:
                return snap[group][device_id]
        return snap["devices"].get(device_id)
