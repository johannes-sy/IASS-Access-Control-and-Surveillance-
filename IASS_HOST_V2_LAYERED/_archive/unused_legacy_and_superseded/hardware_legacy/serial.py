import logging
import threading
import time

try:
    import serial
except ImportError:
    serial = None

logger = logging.getLogger("IASS.Hardware")


class ArduinoLink:
    """Non-fatal ATmega link with background reconnect and safe USB removal handling."""

    def __init__(self, enabled, port, baud, reconnect_interval=2.0):
        self.enabled = bool(enabled)
        self.port = port
        self.baud = int(baud)
        self.ser = None
        self.last = 0.0
        self.state = "DISABLED" if not self.enabled else "DISCONNECTED"
        self.error = None
        self.reconnect_interval = float(reconnect_interval)
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._worker = None

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
        return self.state == "CONNECTED"

    def _attempt_connect(self):
        if not self.enabled or serial is None or self._stop_event.is_set():
            return False
        with self._lock:
            if self.ser is not None and getattr(self.ser, "is_open", False):
                self.state = "CONNECTED"
                return True
            try:
                self.state = "INITIALIZING"
                self.ser = serial.Serial(self.port, self.baud, timeout=.2)
                self.state = "CONNECTED"
                self.error = None
                logger.info("Connected to ATmega328P on %s", self.port)
                return True
            except Exception as exc:
                self.ser = None
                self.state = "DISCONNECTED"
                self.error = str(exc)
                return False

    def _reconnect_loop(self):
        while not self._stop_event.wait(self.reconnect_interval):
            if self.state != "CONNECTED":
                self._attempt_connect()
            else:
                with self._lock:
                    if self.ser is None or not getattr(self.ser, "is_open", False):
                        self.state = "DISCONNECTED"

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

    def _write(self, payload):
        if not self.enabled:
            return False
        with self._lock:
            ser = self.ser
        if ser is None or not getattr(ser, "is_open", False):
            self.state = "DISCONNECTED"
            return False
        try:
            ser.write(payload.encode() if isinstance(payload, str) else payload)
            return True
        except Exception as exc:
            logger.warning("ATmega serial write failed: %s", exc)
            self._mark_disconnected(exc)
            return False

    def send_pan(self, steps, min_interval_ms=120):
        steps = max(-100, min(100, int(steps)))
        now = time.time()
        if now - self.last < max(0, int(min_interval_ms)) / 1000.0:
            return False
        self.last = now
        return self._write(f"IASS,PAN,{steps}\n")

    def send_stop(self, min_interval_ms=120):
        now = time.time()
        if now - self.last < max(0, int(min_interval_ms)) / 1000.0:
            return False
        self.last = now
        return self._write("IASS,STOP\n")

    def send_command(self, namespace, action, device_id, *parameters):
        """Low-level semantic protocol encoder. Upper layers never call this directly."""
        parts = [str(namespace), str(action), str(device_id), *map(str, parameters)]
        return self._write(",".join(parts) + "\n")

    def stop(self):
        self._stop_event.set()
        with self._lock:
            ser = self.ser
            self.ser = None
        if ser is not None:
            try:
                if getattr(ser, "is_open", False):
                    ser.write(b"IASS,STOP\n")
                    ser.close()
            except Exception:
                pass
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=1.0)
        self.state = "DISABLED" if not self.enabled else "DISCONNECTED"
