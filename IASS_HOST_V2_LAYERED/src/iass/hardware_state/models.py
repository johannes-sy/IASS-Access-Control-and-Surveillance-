"""Hardware state records -- the "Door 3 = UNLOCKED" layer.

These are the latest-known-state dataclasses that HardwareStateManager
(manager.py) keeps in memory and the rest of the app reads. They used to
live inside hardware/models.py mixed in with device enums and the command
result contract; moved here so hardware_state owns its own record types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from iass.hardware_interface.models import DeviceStatus, DoorState, AlarmState, CameraMode


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
    mode: str = "SILENT"
    status: str = DeviceStatus.DISCONNECTED.value
    triggered_by: str | None = None
    triggered_at: float | None = None
    remaining_seconds: float | None = None
    fault: str | None = None
