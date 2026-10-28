"""Command lifecycle, deduplication and expiry management.

This service deliberately does not pretend that a V1 firmware boolean write is
an ACK.  A command becomes CONFIRMED only when an ACK/telemetry-capable backend
provides evidence; otherwise its state remains SENT/UNKNOWN.
"""
from __future__ import annotations
import threading
import time
from collections import OrderedDict
from .events_bus import HardwareEventBus
from ..protocol.contract import CommandEnvelope, CommandLifecycle, Lifecycle, ErrorCode


class CommandTransactionManager:
    def __init__(self, event_bus: HardwareEventBus | None = None, dedup_window=1.0, max_history=500):
        self.events = event_bus or HardwareEventBus()
        self.dedup_window = float(dedup_window)
        self.max_history = int(max_history)
        self._lock = threading.RLock()
        self._active: dict[str, CommandLifecycle] = {}
        self._recent: OrderedDict[tuple, tuple[float, str]] = OrderedDict()
        self._history: OrderedDict[str, CommandLifecycle] = OrderedDict()

    def admit(self, command: CommandEnvelope) -> tuple[bool, str | None]:
        now = time.time()
        if command.expired(now):
            return False, ErrorCode.STALE_COMMAND.value
        key = (command.device_id, command.action, repr(sorted(command.parameters.items())))
        with self._lock:
            old = self._recent.get(key)
            if old and now - old[0] < self.dedup_window and old[1] in self._active:
                return False, ErrorCode.DUPLICATE.value
            self._recent[key] = (now, command.command_id)
            self._active[command.command_id] = CommandLifecycle(command=command)
        return True, None

    def sent(self, command_id: str):
        with self._lock:
            tx = self._active.get(command_id)
            if not tx: return None
            tx.state = Lifecycle.SENT.value
            tx.sent_at = time.time(); tx.attempts += 1
            return tx

    def confirm(self, command_id: str, result="CONFIRMED"):
        return self._finish(command_id, Lifecycle.CONFIRMED.value, result=result)

    def fail(self, command_id: str, error: str, result="FAILED"):
        return self._finish(command_id, Lifecycle.FAILED.value, error=error, result=result)

    def expire(self, command_id: str):
        return self._finish(command_id, Lifecycle.EXPIRED.value, error=ErrorCode.TIMEOUT.value, result="EXPIRED")

    def _finish(self, command_id, state, error=None, result=None):
        with self._lock:
            tx = self._active.pop(command_id, None)
            if not tx: return None
            tx.state = state; tx.error = error; tx.result = result; tx.completed_at = time.time()
            self._history[command_id] = tx
            while len(self._history) > self.max_history:
                self._history.popitem(last=False)
            return tx

    def get(self, command_id):
        with self._lock:
            return self._active.get(command_id) or self._history.get(command_id)

    def record_result(self, device_id, action, command_id, correlation_id, success, result, error=None, details=None):
        """Record an already-dispatched command (legacy V1 transport path)."""
        from ..protocol.contract import CommandEnvelope
        cmd = CommandEnvelope(device_id=device_id, action=action, parameters=details or {}, correlation_id=correlation_id or "", command_id=command_id, requires_confirmation=not success)
        tx = CommandLifecycle(command=cmd, state=(Lifecycle.CONFIRMED.value if success and result == "SUCCESS" else Lifecycle.SENT.value if success else Lifecycle.FAILED.value), sent_at=time.time(), attempts=1, result=result, error=error)
        if tx.state in (Lifecycle.CONFIRMED.value, Lifecycle.FAILED.value): tx.completed_at=time.time()
        with self._lock:
            self._history[command_id]=tx
            while len(self._history)>self.max_history: self._history.popitem(last=False)
        return tx

    def snapshot(self):
        with self._lock:
            return {
                "active": [x.to_dict() for x in self._active.values()],
                "history": [x.to_dict() for x in self._history.values()],
            }
