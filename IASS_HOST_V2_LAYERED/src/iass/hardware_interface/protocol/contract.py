"""Host-side hardware protocol contract.

The current ATmega V1 firmware still uses the legacy 7-byte wire frame.  This
module defines the richer semantic contract used by IASS above that transport.
It lets the host track command identity, priority, lifecycle, expiry and errors
without leaking serial details into security/AI code.  A future firmware
revision can serialize these fields on-wire without changing the upper layers.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum, IntEnum
import time
import uuid


class MessageType(str, Enum):
    COMMAND = "COMMAND"
    ACK = "ACK"
    NACK = "NACK"
    TELEMETRY = "TELEMETRY"
    HEARTBEAT = "HEARTBEAT"
    FAULT = "FAULT"
    EVENT = "EVENT"


class Priority(IntEnum):
    NORMAL = 10
    HIGH = 50
    SAFETY = 90
    EMERGENCY = 100


class Lifecycle(str, Enum):
    CREATED = "CREATED"
    SENT = "SENT"
    ACKED = "ACKED"
    EXECUTING = "EXECUTING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class ErrorCode(str, Enum):
    INVALID_COMMAND = "INVALID_COMMAND"
    INVALID_DEVICE = "INVALID_DEVICE"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    DEVICE_BUSY = "DEVICE_BUSY"
    DEVICE_FAULT = "DEVICE_FAULT"
    SAFETY_REJECTED = "SAFETY_REJECTED"
    TIMEOUT = "TIMEOUT"
    OFFLINE = "OFFLINE"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    STALE_COMMAND = "STALE_COMMAND"
    DUPLICATE = "DUPLICATE"


@dataclass(frozen=True)
class CommandEnvelope:
    device_id: str
    action: str
    parameters: dict = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: int = Priority.NORMAL
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    requires_confirmation: bool = True
    retryable: bool = False

    def expired(self, now: float | None = None) -> bool:
        return self.expires_at is not None and (now or time.time()) > self.expires_at

    def to_dict(self):
        return asdict(self)


@dataclass
class CommandLifecycle:
    command: CommandEnvelope
    state: str = Lifecycle.CREATED.value
    sent_at: float | None = None
    completed_at: float | None = None
    attempts: int = 0
    error: str | None = None
    result: str | None = None

    def to_dict(self):
        return {
            "command": self.command.to_dict(),
            "state": self.state,
            "sent_at": self.sent_at,
            "completed_at": self.completed_at,
            "attempts": self.attempts,
            "error": self.error,
            "result": self.result,
        }
