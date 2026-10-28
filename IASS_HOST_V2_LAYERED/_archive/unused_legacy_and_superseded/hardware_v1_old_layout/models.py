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


@dataclass
class CameraState:
    device_id: str
    pan: float = 0.0
    tilt: float = 0.0
    target_pan: float = 0.0
    target_tilt: float = 0.0
    speed: float = 1.0
    direction: str = "CENTER"
    mode: str = CameraMode.IDLE.value
    status: str = DeviceStatus.DISCONNECTED.value
    fault: str | None = None
    last_command: float | None = None
    target_id: str | None = None


@dataclass
class DoorStateRecord:
    device_id: str
    commanded_lock: bool | None = True
    actual_lock: bool | None = None
    sensor: str = "UNKNOWN"
    state: str = DoorState.UNKNOWN.value
    status: str = DeviceStatus.DISCONNECTED.value
    last_access_rfid: str | None = None
    last_user: str | None = None
    last_access_authorized: bool | None = None
    fault: str | None = None
    unlock_until: float | None = None


@dataclass
class AlarmStateRecord:
    device_id: str
    state: str = AlarmState.DISARMED.value
    mode: str = AlarmMode.SILENT.value
    status: str = DeviceStatus.DISCONNECTED.value
    triggered_by: str | None = None
    triggered_at: float | None = None
    remaining_seconds: float | None = None
    fault: str | None = None


@dataclass
class HardwareIntent:
    intent: str
    zone: str = "MAIN_ENTRANCE"
    camera_id: str | None = None
    person_id: int | None = None
    identity: str | None = None
    authorized: bool | None = None
    confidence: float = 0.0
    target: dict[str, Any] = field(default_factory=dict)
    source: str = "AI"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)
