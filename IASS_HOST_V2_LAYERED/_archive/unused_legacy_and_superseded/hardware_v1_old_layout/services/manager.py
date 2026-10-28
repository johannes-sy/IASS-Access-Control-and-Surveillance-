"""Lifecycle manager for reconnect, heartbeat and inbound telemetry."""
import threading
import time


class HardwareManager:
    def __init__(self, transport, bus, state_store, safety):
        self.transport, self.bus = transport, bus
        self.state, self.safety = state_store, safety
        self.running = False
        self.thread = None
        self.transport.on_frame = self._on_rx

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, name="iass-hardware", daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        self.transport.disconnect()

    def _loop(self):
        next_heartbeat = 0.0
        while self.running:
            now = time.time()
            if not self.transport.connected:
                self.transport.connect()
            if self.transport.connected and now >= next_heartbeat:
                if self.bus.heartbeat():
                    self.safety.heartbeat()
                next_heartbeat = now + 1.0
            self.transport.poll()
            time.sleep(0.01)

    def _on_rx(self, frame):
        self.state.apply_frame(frame)
