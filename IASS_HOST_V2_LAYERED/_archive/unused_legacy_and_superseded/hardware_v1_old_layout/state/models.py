"""Hardware state models exposed to the application/UI."""
from dataclasses import dataclass, field
from typing import Dict
import time


@dataclass
class CameraState:
    camera_id: str
    pan: int = 90
    tilt: int = 90
    online: bool = False
    moving: bool = False


@dataclass
class LockState:
    lock_id: str
    locked: bool = True
    door_closed: bool = True
    fault: bool = False


@dataclass
class AlarmState:
    alarm_id: str
    siren: bool = False
    strobe: bool = False
    fault: bool = False


@dataclass
class HardwareSnapshot:
    connected: bool
    mode: str
    estop: bool
    heartbeat_age: float
    cameras: Dict[str, CameraState] = field(default_factory=dict)
    locks: Dict[str, LockState] = field(default_factory=dict)
    alarms: Dict[str, AlarmState] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
