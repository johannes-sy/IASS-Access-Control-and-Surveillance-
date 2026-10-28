"""Centralized hardware safety policy.

The host application cannot bypass these checks through a controller.
The MCU must still enforce the final electrical/firmware failsafe.
"""
import time


class HardwareSafetyPolicy:
    def __init__(self, heartbeat_timeout=5.0):
        self.heartbeat_timeout = heartbeat_timeout
        self.estop = False
        self.last_heartbeat = 0.0

    def heartbeat(self):
        self.last_heartbeat = time.time()

    def communication_lost(self):
        return self.last_heartbeat and time.time() - self.last_heartbeat > self.heartbeat_timeout

    def emergency_stop(self):
        self.estop = True

    def clear_estop(self, operator_authorized=False):
        if operator_authorized:
            self.estop = False
            return True
        return False

    def authorize_unlock(self, lock_id, authorization):
        return bool(lock_id and authorization and not self.estop and not self.communication_lost())

    def allow_alarm(self, reason):
        return bool(reason and not self.estop)
