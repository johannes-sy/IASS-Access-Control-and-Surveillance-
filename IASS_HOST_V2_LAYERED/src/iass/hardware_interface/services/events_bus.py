"""Thread-safe hardware event bus.

Consumers can include UI, audit, command lifecycle and diagnostics without
coupling those concerns to the physical driver.
"""
from __future__ import annotations
import threading
import time
from dataclasses import dataclass, field, asdict
import uuid

@dataclass(frozen=True)
class HardwareEvent:
    event_type: str
    device_id: str | None = None
    correlation_id: str | None = None
    command_id: str | None = None
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    severity: str = "INFO"
    def to_dict(self): return asdict(self)

class HardwareEventBus:
    def __init__(self):
        self._listeners=[]; self._lock=threading.RLock()
    def subscribe(self, listener):
        with self._lock: self._listeners.append(listener)
    def publish(self, event):
        if isinstance(event, dict): event=HardwareEvent(**event)
        with self._lock: listeners=tuple(self._listeners)
        for listener in listeners:
            try: listener(event)
            except Exception: pass
        return event
