from __future__ import annotations

import logging
import threading
import time

from .serial import ArduinoLink

logger = logging.getLogger("IASS.Hardware.Driver")


class HardwareDriver:
    def connect(self): return False
    def close(self): pass
    @property
    def connected(self): return False


class MockHardwareDriver(HardwareDriver):
    """Deterministic simulation driver. It never claims to be physical hardware."""
    simulation = True
    def __init__(self): self._connected = True
    def connect(self): self._connected = True; return True
    def close(self): self._connected = False
    @property
    def connected(self): return self._connected
    def command(self, device_id, action, **params):
        return self._connected


class AtmegaHardwareDriver(HardwareDriver):
    simulation = False
    """Adapter over the existing ArduinoLink. Protocol details remain here."""
    def __init__(self, link: ArduinoLink): self.link = link
    def connect(self): return self.link.connect()
    def close(self): self.link.stop()
    @property
    def connected(self): return self.link.state == "CONNECTED"

    def command(self, device_id, action, **params):
        if not self.connected:
            return False
        # Existing V1 firmware compatibility for the original camera pan path.
        if action == "PAN_STEP":
            return self.link.send_pan(params.get("steps", 0), min_interval_ms=0)
        if action == "STOP":
            return self.link.send_stop(min_interval_ms=0)
        # New generic semantic protocol. The MCU firmware can implement these
        # messages without exposing them to the rest of IASS.
        return self.link.send_command(
            "IASS",
            action,
            device_id,
            *[f"{k}={v}" for k, v in params.items()],
        )
