"""Composition root for the new hardware architecture.

Existing legacy hardware modules remain untouched. New code can opt into this
stack through build_hardware_system().
"""
from .transport.uart_transport import UARTTransport
from .protocol.frame import Frame
from .services.command_bus import CommandBus
from .state.store import HardwareStateStore
from .safety.policy import HardwareSafetyPolicy
from .services.manager import HardwareManager
from .controllers.camera.controller import CameraController
from .controllers.locks.controller import LockController
from .controllers.alarms.controller import AlarmController
from .controllers.telemetry.controller import TelemetryController
from .api.hardware_api import HardwareAPI
from .scenarios.access_control import AccessControlScenario


class _Events:
    def record(self, *args):
        return None


def build_hardware_system(port="/dev/ttyACM0", baudrate=115200):
    transport = UARTTransport(port, baudrate)
    state = HardwareStateStore()
    safety = HardwareSafetyPolicy()
    bus = CommandBus(transport, Frame)
    manager = HardwareManager(transport, bus, state, safety)
    cameras = CameraController(bus)
    locks = LockController(bus, safety)
    alarms = AlarmController(bus, safety)
    telemetry = TelemetryController(bus, state)
    api = HardwareAPI(manager, cameras, locks, alarms, telemetry)
    scenarios = AccessControlScenario(locks, alarms, _Events())
    return {
        "manager": manager, "api": api, "cameras": cameras,
        "locks": locks, "alarms": alarms, "telemetry": telemetry,
        "scenarios": scenarios, "safety": safety,
    }
