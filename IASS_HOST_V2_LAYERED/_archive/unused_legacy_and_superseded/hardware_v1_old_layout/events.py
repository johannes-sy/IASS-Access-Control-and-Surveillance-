from __future__ import annotations

import time


class HardwareAudit:
    def __init__(self, db):
        self.db = db

    def command(self, result, source="SYSTEM", correlation_id=None, details=None):
        return self.db.hardware_command(
            command_id=result.command_id,
            correlation_id=correlation_id or result.correlation_id,
            device_id=result.device_id,
            action=result.action,
            requested_state=result.requested_state,
            actual_state=result.actual_state,
            result=result.result,
            error=result.error,
            details={**(result.details or {}), **(details or {}), "source": source},
            timestamp=result.timestamp,
        )

    def event(self, device_id, event_type, previous_state=None, new_state=None,
              correlation_id=None, details=None):
        return self.db.hardware_event(
            device_id=device_id,
            event_type=event_type,
            previous_state=previous_state,
            new_state=new_state,
            correlation_id=correlation_id,
            details=details or {},
        )
