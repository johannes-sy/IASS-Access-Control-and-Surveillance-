from types import SimpleNamespace

from iass.hardware_interface.drivers import AtmegaHardwareDriver
from iass.hardware_interface.serial_link import ArduinoLink


class FakeLink:
    connected = True

    def __init__(self):
        self.calls = []

    def send_pan(self, steps, servo=0, min_interval_ms=0):
        self.calls.append(("PAN", servo, steps)); return True

    def send_stop(self, servo=0, min_interval_ms=0):
        self.calls.append(("STOP", servo)); return True

    def send_servo_set(self, servo, angle):
        self.calls.append(("SERVO_SET", servo, angle)); return True

    def send_servo_home(self):
        self.calls.append(("SERVO_HOME",)); return True

    def send_lock(self, door):
        self.calls.append(("LOCK", door)); return True

    def send_unlock(self, door):
        self.calls.append(("UNLOCK", door)); return True

    def send_siren(self, enabled):
        self.calls.append(("SIREN", enabled)); return True

    def send_strobe(self, enabled):
        self.calls.append(("STROBE", enabled)); return True

    def clear_alarm(self):
        self.calls.append(("CLEAR_ALARM",)); return True

    def request_telemetry(self):
        self.calls.append(("TELEMETRY",)); return True

    def send_heartbeat(self):
        self.calls.append(("HEARTBEAT",)); return True



def test_atmega_driver_maps_semantic_actions_to_firmware_commands():
    link = FakeLink()
    driver = AtmegaHardwareDriver(link)
    assert driver.command("door_2", "LOCK")
    assert driver.command("door_1", "UNLOCK")
    assert driver.command("camera_mount_3", "PAN_STEP", steps=5)
    assert driver.command("alarm_1", "ALARM_TRIGGER", mode="SIREN_STROBE")
    assert ("LOCK", 2) in link.calls
    assert ("UNLOCK", 1) in link.calls
    assert ("PAN", 2, 5) in link.calls
    assert ("SIREN", True) in link.calls and ("STROBE", True) in link.calls


def test_link_never_uses_old_ascii_protocol():
    link = ArduinoLink(False, "/dev/null", 115200)
    assert not link.send_command("IASS", "PAN", "CAM1", 5)


def test_serial_link_emits_exact_firmware_frame(monkeypatch):
    import iass.hardware_interface.serial_link as serial_module

    class FakeSerialPort:
        last = None
        def __init__(self, *args, **kwargs):
            self.is_open = True
            self.writes = []
            FakeSerialPort.last = self
        def write(self, payload):
            self.writes.append(bytes(payload))
            return len(payload)
        def flush(self): pass
        def read(self, n=1): return b""
        def close(self): self.is_open = False

    class FakeSerialModule:
        Serial = FakeSerialPort

    monkeypatch.setattr(serial_module, "serial", FakeSerialModule)
    link = serial_module.ArduinoLink(True, "/dev/test", 115200)
    assert link.connect()
    assert link.send_lock(1)
    assert FakeSerialPort.last.writes[-1] == bytes([0xAA, 0x01, 0x10, 0x00, 0x01, 0x10, 0x55])
    link.stop()
