"""HardwareIntent -- the decision_security layer's output contract.

This is the "Person 42 is authorized" fact, expressed as data, on its way
down to hardware_control. decision_security is the only layer that
constructs these; hardware_control is the only layer that consumes them.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any
import time
import uuid


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
