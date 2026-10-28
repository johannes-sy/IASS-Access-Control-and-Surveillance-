from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None

from .protocol.frame import Frame, FrameParser
from .protocol.commands import (
    CMD_HEARTBEAT, CMD_LOCK, CMD_UNLOCK, CMD_SERVO_SET, CMD_SERVO_HOME,
    CMD_SIREN, CMD_STROBE, CMD_TELEMETRY, CMD_CLEAR_ALARM,
    DEVICE_SYSTEM, TEL_STATUS,
)

logger = logging.getLogger("IASS.Hardware")


class ArduinoLink:
    """Thread-safe ATmega328P UART link using the firmware's fixed 7-byte frame."""

    def __init__(self, enabled, port, baud, reconnect_interval=2.0):
        self.enabled = bool(enabled)
        self.port = port
        self.baud = int(baud)
        self.ser = None
        self.state = "DISABLED" if not self.enabled else "DISCONNECTED"
        self.error: Optional[str] = None
        self.reconnect_interval = float(reconnect_interval)
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._worker: Optional[threading.Thread] = None
        self._rx_worker: Optional[threading.Thread] = None
        self._service_worker: Optional[threading.Thread] = None
        self._parser = FrameParser()
        self.parser_errors = 0
        self.bytes_rx = 0
        self.bytes_tx = 0
        self._on_frame: Optional[Callable[[Frame], None]] = None
        self.last_rx = 0.0
        self.last_tx = 0.0
        self.last_telemetry = 0.0
        self.telemetry: dict = {}
        self._servo_angles = [90, 90, 90]
        self._last_tx_lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self.state == "CONNECTED"

    def set_frame_callback(self, callback: Optional[Callable[[Frame], None]]):
        self._on_frame = callback

    def connect(self):
        if not self.enabled:
            self.state = "DISABLED"
            return False
        if serial is None:
            self.state = "ERROR"
            self.error = "pyserial is not available"
            return False
        self._stop_event.clear()
        self._attempt_connect()
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._reconnect_loop, name="iass-atmega-reconnect", daemon=True)
            self._worker.start()
        if self._service_worker is None or not self._service_worker.is_alive():
            self._service_worker = threading.Thread(target=self._service_loop, name="iass-atmega-service", daemon=True)
            self._service_worker.start()
        return self.connected

    def _attempt_connect(self):
        if not self.enabled or serial is None or self._stop_event.is_set():
            return False
        with self._lock:
            if self.ser is not None and getattr(self.ser, "is_open", False):
                self.state = "CONNECTED"
                return True
            try:
                self.state = "INITIALIZING"
                self.ser = serial.Serial(self.port, self.baud, timeout=0.05, write_timeout=1)
                self.state = "CONNECTED"
                self.error = None
                self.last_rx = time.time()
                logger.info("Connected to ATmega328P on %s", self.port)
                if self._rx_worker is None or not self._rx_worker.is_alive():
                    self._rx_worker = threading.Thread(target=self._rx_loop, name="iass-atmega-rx", daemon=True)
                    self._rx_worker.start()
                return True
            except Exception as exc:
                self.ser = None
                self.state = "DISCONNECTED"
                self.error = str(exc)
                return False

    def _service_loop(self):
        """Maintain the MCU heartbeat independently of application traffic."""
        next_heartbeat = 0.0
        while not self._stop_event.wait(0.1):
            now = time.time()
            if self.connected and now >= next_heartbeat:
                self.send_heartbeat()
                next_heartbeat = now + 1.0

    def _reconnect_loop(self):
        while not self._stop_event.wait(self.reconnect_interval):
            if not self.connected:
                self._attempt_connect()
            else:
                with self._lock:
                    if self.ser is None or not getattr(self.ser, "is_open", False):
                        self._mark_disconnected("serial port closed")

    def _rx_loop(self):
        while not self._stop_event.is_set():
            with self._lock:
                ser = self.ser
            if ser is None or not getattr(ser, "is_open", False):
                if not self._stop_event.wait(0.1):
                    continue
                continue
            try:
                data = ser.read(128)
                if not data:
                    continue
                self.bytes_rx += len(data)
                self.last_rx = time.time()
                for frame in self._parser.feed(data):
                    if frame.device == DEVICE_SYSTEM and frame.command == TEL_STATUS:
                        self.telemetry = frame.telemetry_state()
                        self.last_telemetry = time.time()
                    callback = self._on_frame
                    if callback:
                        try:
                            callback(frame)
                        except Exception:
                            logger.exception("Hardware frame callback failed")
            except Exception as exc:
                if not self._stop_event.is_set():
                    logger.warning("ATmega serial read failed: %s", exc)
                    self._mark_disconnected(exc)

    def _mark_disconnected(self, error=None):
        with self._lock:
            ser = self.ser
            self.ser = None
            self.state = "DISCONNECTED" if self.enabled else "DISABLED"
            self.error = str(error) if error else None
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass

    def _send(self, frame: Frame) -> bool:
        raw = frame.encode()
        with self._lock:
            ser = self.ser
        if not self.enabled or ser is None or not getattr(ser, "is_open", False):
            self.state = "DISCONNECTED" if self.enabled else "DISABLED"
            return False
        try:
            with self._last_tx_lock:
                ser.write(raw)
                ser.flush()
                self.bytes_tx += len(raw)
                self.last_tx = time.time()
            return True
        except Exception as exc:
            logger.warning("ATmega serial write failed: %s", exc)
            self._mark_disconnected(exc)
            return False

    def _frame(self, command: int, value: int = 0) -> Frame:
        return Frame(DEVICE_SYSTEM, command, value)

    def send_heartbeat(self) -> bool:
        return self._send(self._frame(CMD_HEARTBEAT))

    def request_telemetry(self) -> bool:
        return self._send(self._frame(CMD_TELEMETRY))

    def send_lock(self, door: int) -> bool:
        return self._send(self._frame(CMD_LOCK, int(door) & 0xFFFF))

    def send_unlock(self, door: int) -> bool:
        return self._send(self._frame(CMD_UNLOCK, int(door) & 0xFFFF))

    def send_servo_set(self, servo: int, angle: int) -> bool:
        servo = int(servo)
        angle = max(0, min(180, int(angle)))
        if servo not in (0, 1, 2):
            return False
        value = (servo << 8) | angle
        ok = self._send(self._frame(CMD_SERVO_SET, value))
        if ok:
            self._servo_angles[servo] = angle
        return ok

    def send_servo_home(self) -> bool:
        ok = self._send(self._frame(CMD_SERVO_HOME))
        if ok:
            self._servo_angles = [90, 90, 90]
        return ok

    def send_siren(self, enabled: bool) -> bool:
        return self._send(self._frame(CMD_SIREN, 1 if enabled else 0))

    def send_strobe(self, enabled: bool) -> bool:
        return self._send(self._frame(CMD_STROBE, 1 if enabled else 0))

    def clear_alarm(self) -> bool:
        return self._send(self._frame(CMD_CLEAR_ALARM))

    # Compatibility methods retained for existing callers. The ATmega firmware
    # has no ASCII PAN/STOP commands, so they are translated to the real servo API.
    def send_pan(self, steps, servo=0, min_interval_ms=0):
        servo = int(servo)
        target = self._servo_angles[servo] + int(steps)
        return self.send_servo_set(servo, target)

    def send_stop(self, servo=0, min_interval_ms=0):
        servo = int(servo)
        return self.send_servo_set(servo, self._servo_angles[servo])

    def send_command(self, namespace, action, device_id, *parameters):
        """Compatibility semantic dispatcher; never emits the old ASCII protocol."""
        if namespace != "IASS":
            return False
        if action == "LOCK":
            return self.send_lock(_numeric_id(device_id))
        if action == "UNLOCK":
            return self.send_unlock(_numeric_id(device_id))
        if action == "ALARM_TRIGGER":
            mode = next((str(p).split("=", 1)[1] for p in parameters if str(p).startswith("mode=")), "SIREN_STROBE")
            if mode == "SILENT":
                return self.clear_alarm()
            if mode == "STROBE_ONLY":
                return self.send_siren(False) and self.send_strobe(True)
            return self.send_siren(True) and self.send_strobe(True)
        if action == "ALARM_CLEAR":
            return self.clear_alarm()
        if action == "ALARM_SILENCE":
            return self.send_siren(False)
        if action == "ALARM_STROBE":
            enabled = any(str(p).endswith("=1") or str(p) == "1" for p in parameters)
            return self.send_strobe(enabled)
        return False

    def health(self):
        now = time.time()
        return {
            "enabled": self.enabled, "state": self.state, "connected": self.connected,
            "port": self.port, "baud": self.baud, "last_rx": self.last_rx,
            "last_tx": self.last_tx, "last_telemetry": self.last_telemetry,
            "rx_age": (now - self.last_rx) if self.last_rx else None,
            "telemetry_age": (now - self.last_telemetry) if self.last_telemetry else None,
            "bytes_rx": self.bytes_rx, "bytes_tx": self.bytes_tx,
            "parser_errors": self.parser_errors, "error": self.error,
            "telemetry": dict(self.telemetry),
        }

    def stop(self):
        self._stop_event.set()
        with self._lock:
            ser = self.ser
            self.ser = None
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        for worker in (self._rx_worker, self._worker, self._service_worker):
            if worker and worker.is_alive() and worker is not threading.current_thread():
                worker.join(timeout=1.0)
        self._rx_worker = None
        self._worker = None
        self._service_worker = None
        self.state = "DISABLED" if not self.enabled else "DISCONNECTED"


def _numeric_id(device_id) -> int:
    text = str(device_id)
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits[-1:]) if digits else 1
