"""Framework-neutral API facade for FastAPI routes.

Routes should call this facade rather than reaching into UART/serial code.
"""


class HardwareAPI:
    def __init__(self, manager, cameras, locks, alarms, telemetry):
        self.manager = manager
        self.cameras = cameras
        self.locks = locks
        self.alarms = alarms
        self.telemetry = telemetry

    def status(self):
        s = self.telemetry.snapshot()
        return {
            "connected": s.connected,
            "mode": s.mode,
            "estop": s.estop,
            "heartbeat_age": s.heartbeat_age,
            "cameras": {k: vars(v) for k, v in s.cameras.items()},
            "locks": {k: vars(v) for k, v in s.locks.items()},
            "alarms": {k: vars(v) for k, v in s.alarms.items()},
        }
