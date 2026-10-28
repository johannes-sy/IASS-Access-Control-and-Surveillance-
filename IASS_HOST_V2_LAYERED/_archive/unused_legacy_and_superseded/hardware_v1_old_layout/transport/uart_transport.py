"""Low-level serial transport for the ATmega328P fixed-frame protocol."""
from __future__ import annotations
import threading
import time
from typing import Optional, Callable

try:
    import serial
except ImportError:
    serial = None

from ..protocol.frame import Frame, FrameParser


class UARTTransport:
    def __init__(self, port="/dev/ttyACM0", baudrate=115200, timeout=0.05):
        self.port, self.baudrate, self.timeout = port, baudrate, timeout
        self._ser = None
        self._lock = threading.RLock()
        self.connected = False
        self.last_error: Optional[str] = None
        self.last_rx = 0.0
        self.last_tx = 0.0
        self.on_frame: Optional[Callable[[Frame], None]] = None
        self._parser = FrameParser()

    def connect(self) -> bool:
        if serial is None:
            self.last_error = "pyserial is not installed"
            return False
        try:
            self._ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout, write_timeout=1)
            self.connected = True
            self.last_error = None
            return True
        except Exception as exc:
            self.connected = False
            self.last_error = str(exc)
            return False

    def disconnect(self) -> None:
        with self._lock:
            ser = self._ser
            self._ser = None
            self.connected = False
        if ser:
            try: ser.close()
            except Exception: pass

    def send(self, payload: bytes) -> bool:
        if not payload:
            return False
        with self._lock:
            if not self.connected or self._ser is None:
                return False
            try:
                self._ser.write(payload)
                self._ser.flush()
                self.last_tx = time.time()
                return True
            except Exception as exc:
                self.last_error = str(exc)
                self.disconnect()
                return False

    def send_frame(self, frame: Frame) -> bool:
        return self.send(frame.encode())

    def send_servo_delta(self, servo_id, delta):
        return False  # absolute-angle translation belongs in the semantic controller

    def send_servo_hold(self, servo_id):
        return False

    def send_alarm_mode(self, mode):
        from ..protocol.commands import CMD_SIREN, CMD_STROBE, DEVICE_SYSTEM
        if mode == "SILENT":
            return self.send_frame(Frame(DEVICE_SYSTEM, CMD_SIREN, 0)) and self.send_frame(Frame(DEVICE_SYSTEM, CMD_STROBE, 0))
        if mode == "STROBE_ONLY":
            return self.send_frame(Frame(DEVICE_SYSTEM, CMD_SIREN, 0)) and self.send_frame(Frame(DEVICE_SYSTEM, CMD_STROBE, 1))
        return self.send_frame(Frame(DEVICE_SYSTEM, CMD_SIREN, 1)) and self.send_frame(Frame(DEVICE_SYSTEM, CMD_STROBE, 1))

    def poll(self) -> None:
        # In the production path ArduinoLink owns RX in its dedicated reader.
        return None
