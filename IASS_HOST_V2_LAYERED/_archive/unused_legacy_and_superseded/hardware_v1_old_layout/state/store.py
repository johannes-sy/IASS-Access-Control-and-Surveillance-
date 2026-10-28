from __future__ import annotations

import threading
import time
from copy import deepcopy

from ..protocol.commands import DEVICE_SYSTEM, TEL_STATUS
from .models import HardwareSnapshot, CameraState, LockState, AlarmState


class HardwareStateStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._snapshot = HardwareSnapshot(
            connected=False, mode="OFFLINE", estop=False, heartbeat_age=0,
            cameras={f"CAM{i}": CameraState(f"CAM{i}") for i in range(1, 4)},
            locks={f"DOOR_{i}": LockState(f"DOOR_{i}") for i in range(1, 3)},
            alarms={f"ALARM_{i}": AlarmState(f"ALARM_{i}") for i in range(1, 3)},
        )

    def snapshot(self):
        with self._lock:
            return deepcopy(self._snapshot)

    def apply_frame(self, frame):
        with self._lock:
            if frame.device != DEVICE_SYSTEM or frame.command != TEL_STATUS:
                return
            t = frame.telemetry_state()
            self._snapshot.connected = True
            self._snapshot.mode = "FAILSAFE" if t["failsafe"] else "CONNECTED"
            self._snapshot.estop = t["failsafe"]
            self._snapshot.heartbeat_age = 0.0
            for i, locked in ((1, t["door1_locked"]), (2, t["door2_locked"])):
                d = self._snapshot.locks[f"DOOR_{i}"]
                d.locked = locked
                d.door_closed = not t[f"door{i}_open"]
            for a in self._snapshot.alarms.values():
                a.siren = t["siren"]
                a.strobe = t["strobe"]
                a.fault = t["failsafe"]
            self._snapshot.timestamp = time.time()
