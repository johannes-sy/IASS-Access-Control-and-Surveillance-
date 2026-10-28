from types import SimpleNamespace

from iass.hardware_interface.controller import HardwareController
from iass.hardware_interface.drivers import MockHardwareDriver
from iass.hardware_interface.models import DeviceType
from iass.decision_security.intents import HardwareIntent
from iass.hardware_control.device_registry import DeviceDefinition, DeviceRegistry
from iass.hardware_state import HardwareStateManager


def settings():
    return SimpleNamespace(
        pan_deadband_px=10,
        pan_kp=0.1,
        max_step_command=8,
        hardware_zone_policies={"MAIN_ENTRANCE": {"lock_on_unauthorized": True, "alarm_on_unauthorized": True, "alarm_duration": 1, "alarm_mode": "SIREN_STROBE"}},
    )


def controller():
    defs = [
        DeviceDefinition("camera_mount_1", DeviceType.CAMERA_MOUNT.value, "mock", zone="MAIN_ENTRANCE", limits={"min_pan": -180, "max_pan": 180, "min_tilt": -90, "max_tilt": 90, "max_speed": 1}),
        DeviceDefinition("camera_mount_2", DeviceType.CAMERA_MOUNT.value, "mock", zone="MAIN_ENTRANCE", limits={"min_pan": -180, "max_pan": 180, "min_tilt": -90, "max_tilt": 90, "max_speed": 1}),
        DeviceDefinition("camera_mount_3", DeviceType.CAMERA_MOUNT.value, "mock", zone="MAIN_ENTRANCE", limits={"min_pan": -180, "max_pan": 180, "min_tilt": -90, "max_tilt": 90, "max_speed": 1}),
        DeviceDefinition("door_1", DeviceType.DOOR_LOCK.value, "mock", zone="MAIN_ENTRANCE", limits={"max_unlock_duration": 2}),
        DeviceDefinition("door_2", DeviceType.DOOR_LOCK.value, "mock", zone="MAIN_ENTRANCE", limits={"max_unlock_duration": 2}),
        DeviceDefinition("alarm_1", DeviceType.ALARM.value, "mock", zone="MAIN_ENTRANCE", limits={"max_duration": 2}),
        DeviceDefinition("alarm_2", DeviceType.ALARM.value, "mock", zone="MAIN_ENTRANCE", limits={"max_duration": 2}),
    ]
    return HardwareController(settings(), DeviceRegistry(defs), HardwareStateManager(), MockHardwareDriver())


def test_hardware_inventory_and_state():
    h = controller(); h.start(); snap = h.snapshot()
    assert len(snap["cameras"]) == 3
    assert len(snap["doors"]) == 2
    assert len(snap["alarms"]) == 2
    assert all(v["status"] == "SIMULATION" for v in snap["cameras"].values())


def test_camera_track_and_limits():
    h = controller(); h.start()
    result = h.track_camera("camera_mount_1", 600, 240, 640, 480)
    assert result.success
    assert h.snapshot()["cameras"]["camera_mount_1"]["direction"] == "RIGHT"
    bad = h.rotate_camera("camera_mount_1", 999)
    assert not bad.success and bad.result == "ANGLE_LIMIT"


def test_door_and_alarm():
    h = controller(); h.start()
    door = h.lock_door("door_1", reason="TEST")
    assert door.success
    assert h.snapshot()["doors"]["door_1"]["state"] == "LOCKED"
    alarm = h.trigger_alarm("alarm_1", duration=0.2, reason="TEST")
    assert alarm.success
    assert h.snapshot()["alarms"]["alarm_1"]["state"] == "TRIGGERED"


def test_unauthorized_intent_maps_to_hardware():
    h = controller(); h.start()
    intent = HardwareIntent(intent="UNAUTHORIZED_PERSON", zone="MAIN_ENTRANCE", target={"x": 600, "y": 240, "frame_width": 640, "frame_height": 480})
    results = h.handle_intent(intent)
    assert len(results) == 7
    snap = h.snapshot()
    assert snap["doors"]["door_1"]["state"] == "LOCKED"
    assert snap["alarms"]["alarm_1"]["state"] == "TRIGGERED"
