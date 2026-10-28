from dataclasses import dataclass, field
import time
import uuid


@dataclass(order=True)
class HardwareCommand:
    priority: int
    device_id: str = field(compare=False)
    action: str = field(compare=False)
    params: dict = field(default_factory=dict, compare=False)
    correlation_id: str | None = field(default=None, compare=False)
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()), compare=False)
    created_at: float = field(default_factory=time.time, compare=False)
    timeout: float = field(default=2.0, compare=False)
