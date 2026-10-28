from __future__ import annotations

import logging

from .serial_link import ArduinoLink

logger = logging.getLogger("IASS.Hardware.Driver")


class HardwareDriver:
    def connect(self):
        return False

    def close(self):
        pass

    @property
    def connected(self):
        return False


class MockHardwareDriver(HardwareDriver):
    """Deterministic simulation driver. It never claims to be physical hardware."""

    simulation = True

    def __init__(self):
        self._connected = True
        self.commands = []

    def connect(self):
        self._connected = True
        return True

    def close(self):
        self._connected = False

    @property
    def connected(self):
        return self._connected

    def capabilities(self, device_id):
        if self.registry is None: return []
        d = self.registry.get(str(device_id))
        return list(d.capabilities) if d else []

    def command(self, device_id, action, **params):
        if not self._connected:
            return False
        self.commands.append((device_id, action, dict(params)))
        return True


class AtmegaHardwareDriver(HardwareDriver):
    """Semantic adapter for the exact ATmega328P V1 binary protocol."""

    simulation = False

    def __init__(self, link: ArduinoLink, registry=None):
        self.link = link
        self.registry = registry

    def connect(self):
        return self.link.connect()

    def close(self):
        self.link.stop()

    @property
    def connected(self):
        return self.link.connected

    @staticmethod
    def _number(device_id: str, valid):
        text = str(device_id)
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            return None
        value = int(digits[-2:])
        return value if value in valid else None

    def _servo_index(self, device_id: str, params=None):
        params = params or {}
        if "servo_index" in params:
            index = int(params["servo_index"])
            return index if index in (0, 1, 2) else None
        if self.registry is not None:
            definition = self.registry.get(str(device_id))
            if definition:
                index = definition.config.get("servo_index")
                if index is not None:
                    index = int(index)
                    return index if index in (0, 1, 2) else None
        number = AtmegaHardwareDriver._number(device_id, {1, 2, 3})
        return None if number is None else number - 1

    def command(self, device_id, action, **params):
        if not self.connected:
            return False

        if action == "PAN_STEP":
            servo = self._servo_index(device_id, params)
            if servo is None:
                return False
            return self.link.send_pan(params.get("steps", 0), servo=servo)

        if action == "STOP":
            servo = self._servo_index(device_id, params)
            return servo is not None and self.link.send_stop(servo=servo)

        if action == "SERVO_SET":
            servo = self._servo_index(device_id, params)
            return servo is not None and self.link.send_servo_set(servo, params.get("angle", 90))

        if action == "SERVO_HOME":
            return self.link.send_servo_home()

        if action == "LOCK":
            door = self._number(device_id, {1, 2})
            return door is not None and self.link.send_lock(door)

        if action == "UNLOCK":
            door = self._number(device_id, {1, 2})
            return door is not None and self.link.send_unlock(door)

        if action == "ALARM_TRIGGER":
            mode = str(params.get("mode", "SIREN_STROBE"))
            if mode == "SILENT":
                return self.link.send_siren(False)
            if mode == "STROBE_ONLY":
                return self.link.send_siren(False) and self.link.send_strobe(True)
            return self.link.send_siren(True) and self.link.send_strobe(True)

        if action == "ALARM_CLEAR":
            return self.link.clear_alarm()

        if action == "ALARM_SILENCE":
            return self.link.send_siren(False)

        if action == "ALARM_STROBE":
            return self.link.send_strobe(bool(params.get("enabled", False)))

        if action == "GET_STATUS":
            return self.link.request_telemetry()

        if action == "HEARTBEAT":
            return self.link.send_heartbeat()

        logger.warning("Unsupported ATmega action: %s", action)
        return False
