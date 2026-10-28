"""hardware_interface layer.

Input:  concrete commands from hardware_control (e.g. controller.unlock_door(...)).
Output: an actual command sent down the wire to the ATmega (or the simulated
        backend), plus HardwareResult acknowledgements and parsed telemetry
        frames that flow into hardware_state.

This is the "send unlock command to the ATmega channel assigned to Door 3"
step. It owns the serial link, the wire protocol (frame.py, contract.py),
command transactions/dedup, and the audit trail -- and nothing about zones,
topology, or authorization.
"""
from .controller import HardwareController
from .safety import HardwareSafetyPolicy
from .drivers import HardwareDriver, MockHardwareDriver, AtmegaHardwareDriver
from .serial_link import ArduinoLink
from .commands import HardwareCommand
from .audit import HardwareAudit
from .models import (
    DeviceType, DeviceStatus, CameraMode, DoorState, AlarmState, AlarmMode,
    HardwareResult,
)
from .backends import HardwareInterface, AtmegaHardwareInterface, SimulatedHardwareInterface

__all__ = [
    "HardwareController", "HardwareSafetyPolicy",
    "HardwareDriver", "MockHardwareDriver", "AtmegaHardwareDriver",
    "ArduinoLink", "HardwareCommand", "HardwareAudit",
    "DeviceType", "DeviceStatus", "CameraMode", "DoorState", "AlarmState", "AlarmMode",
    "HardwareResult",
    "HardwareInterface", "AtmegaHardwareInterface", "SimulatedHardwareInterface",
]
