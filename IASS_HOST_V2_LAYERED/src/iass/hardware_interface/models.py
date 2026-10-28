"""Hardware-interface-layer vocabulary: the enums and result contract used
when a command actually gets dispatched to a physical (or simulated) device.

HardwareResult is the interface layer's acknowledgement contract -- it's what
"Door 3 actuator acknowledged" looks like as data, on its way back up to
hardware_control / decision_security / the UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any
import time
import uuid


class DeviceType(str, Enum):
    CAMERA_MOUNT = "CAMERA_MOUNT"
    DOOR_LOCK = "DOOR_LOCK"
    ALARM = "ALARM"
    RFID_READER = "RFID_READER"


class DeviceStatus(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"
    INITIALIZING = "INITIALIZING"
    FAULT = "FAULT"
    SIMULATION = "SIMULATION"
    UNKNOWN = "UNKNOWN"


class CameraMode(str, Enum):
    IDLE = "IDLE"
    TRACKING = "TRACKING"
    SCANNING = "SCANNING"
    STOPPED = "STOPPED"
    FAULT = "FAULT"


class DoorState(str, Enum):
    LOCKED = "LOCKED"
    UNLOCKED = "UNLOCKED"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LOCKING = "LOCKING"
    UNLOCKING = "UNLOCKING"
    UNKNOWN = "UNKNOWN"
    FAULT = "FAULT"


class AlarmState(str, Enum):
    DISARMED = "DISARMED"
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"
    FAULT = "FAULT"
    UNKNOWN = "UNKNOWN"


class AlarmMode(str, Enum):
    SILENT = "SILENT"
    STROBE_ONLY = "STROBE_ONLY"
    SIREN_STROBE = "SIREN_STROBE"


@dataclass
class HardwareResult:
    success: bool
    device_id: str
    action: str
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None
    requested_state: str | None = None
    actual_state: str | None = None
    result: str = "SUCCESS"
    timestamp: float = field(default_factory=time.time)
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
