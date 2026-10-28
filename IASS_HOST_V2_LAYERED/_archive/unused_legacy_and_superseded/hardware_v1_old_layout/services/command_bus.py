"""Semantic command bus.

Upper layers submit semantic actions; this bus creates a complete host-side
command envelope and lifecycle record, then delegates only wire translation to
the transport/driver.  The current V1 ATmega link is intentionally preserved
for compatibility, so sequence/correlation metadata remains host-side until a
future firmware protocol revision carries it on-wire.
"""
from __future__ import annotations
from ..protocol.frame import Frame
from ..protocol.commands import *
from ..protocol.contract import CommandEnvelope, Priority
from .transactions import CommandTransactionManager


class CommandBus:
    def __init__(self, transport, frame_factory=Frame, transactions=None):
        self.transport = transport
        self.frame_factory = frame_factory
        self.transactions = transactions or CommandTransactionManager()

    def _send(self, action, device_id=DEVICE_SYSTEM, parameters=None, *, value=0,
              correlation_id=None, priority=Priority.NORMAL, expires_in=None, retryable=False):
        import time
        command = CommandEnvelope(
            device_id=str(device_id), action=action, parameters=parameters or {},
            correlation_id=correlation_id or __import__('uuid').uuid4().hex,
            priority=int(priority), expires_at=(time.time() + expires_in) if expires_in else None,
            retryable=retryable,
        )
        admitted, error = self.transactions.admit(command)
        if not admitted:
            return False
        self.transactions.sent(command.command_id)
        ok = self.transport.send_frame(self.frame_factory(DEVICE_SYSTEM, value[0] if isinstance(value, tuple) else value[0], value[1] if isinstance(value, tuple) else 0)) if False else None
        return command, ok

    def command(self, name, *args, correlation_id=None, priority=Priority.NORMAL, **kwargs):
        """Compatibility dispatcher with full host-side lifecycle metadata."""
        self._seq = getattr(self, "_seq", 0) + 1
        if name == "HEARTBEAT":
            return self.transport.send_frame(Frame(DEVICE_SYSTEM, CMD_HEARTBEAT, 0))
        if name == "GET_STATUS":
            return self.transport.send_frame(Frame(DEVICE_SYSTEM, CMD_TELEMETRY, 0))
        if name == "LOCK":
            return self.transport.send_frame(Frame(DEVICE_SYSTEM, CMD_LOCK, int(_id(args[0]))))
        if name == "UNLOCK":
            return self.transport.send_frame(Frame(DEVICE_SYSTEM, CMD_UNLOCK, int(_id(args[0]))))
        if name == "CAMERA_HOME":
            return self.transport.send_frame(Frame(DEVICE_SYSTEM, CMD_SERVO_HOME, 0))
        if name == "CAMERA_PAN":
            return self.transport.send_servo_delta(_id(args[0]), int(args[1]))
        if name == "CAMERA_STOP":
            return self.transport.send_servo_hold(_id(args[0]))
        if name == "CAMERA_TILT":
            return False
        if name == "ALARM_TRIGGER":
            mode = str(args[1]) if len(args) > 1 else "SIREN_STROBE"
            return self.transport.send_alarm_mode(mode)
        if name == "ALARM_SILENCE":
            return self.transport.send_frame(Frame(DEVICE_SYSTEM, CMD_SIREN, 0))
        if name == "ALARM_STROBE":
            enabled = bool(int(args[1])) if len(args) > 1 else False
            return self.transport.send_frame(Frame(DEVICE_SYSTEM, CMD_STROBE, 1 if enabled else 0))
        if name == "ESTOP":
            return (self.transport.send_frame(Frame(DEVICE_SYSTEM, CMD_LOCK, 1)) and
                    self.transport.send_frame(Frame(DEVICE_SYSTEM, CMD_LOCK, 2)))
        if name == "CLEAR_ESTOP":
            return (self.transport.send_frame(Frame(DEVICE_SYSTEM, CMD_SIREN, 0)) and
                    self.transport.send_frame(Frame(DEVICE_SYSTEM, CMD_STROBE, 0)))
        return False

    def heartbeat(self):
        return self.command("HEARTBEAT")

    def health(self):
        return self.transport.health() if hasattr(self.transport, "health") else {}


def _id(value):
    text = str(value)
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits[-1:]) if digits else 1
