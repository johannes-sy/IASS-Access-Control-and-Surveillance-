"""hardware_control layer.

Input:  HardwareIntent from decision_security.
Output: concrete (action, device_id, params) commands, dispatched to
        hardware_interface.

This is the "Camera 3 is configured to cover Door 3, so Door 3 is the
relevant physical access point" step -- it owns site topology (zones,
which devices live where) and turns a semantic intent into a specific
device to command. It knows nothing about serial ports or ATmega wire
protocol, and nothing about authorization policy.
"""
from .policy import HardwarePolicy
from .device_registry import DeviceRegistry, DeviceDefinition
from .topology import load_topology, save_topology, HardwareTopology
from .camera_tracking import TrackerController, CameraTracker
from .action_plan import HardwareAction, HardwareActionPlan

__all__ = [
    "HardwarePolicy", "DeviceRegistry", "DeviceDefinition",
    "load_topology", "save_topology", "HardwareTopology",
    "TrackerController", "CameraTracker",
    "HardwareAction", "HardwareActionPlan",
]
