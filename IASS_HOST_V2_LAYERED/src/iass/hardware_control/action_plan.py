from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import uuid
@dataclass(frozen=True)
class HardwareAction:
    action: str
    target: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
@dataclass
class HardwareActionPlan:
    actions: list[HardwareAction] = field(default_factory=list)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = "SYSTEM"
    reason: str | None = None
