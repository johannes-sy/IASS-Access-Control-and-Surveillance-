from types import SimpleNamespace
from iass.hardware_interface.controller import HardwareController
from iass.hardware_interface.drivers import MockHardwareDriver
from iass.hardware_interface.models import DeviceType
from iass.decision_security.intents import HardwareIntent
from iass.hardware_control.device_registry import DeviceDefinition, DeviceRegistry
from iass.hardware_state import HardwareStateManager
from iass.decision_security.security_engine import SecurityScenarioEngine
from iass.ai_perception.models import PerceptionEvent


def make_system():
    settings = SimpleNamespace(
        pan_deadband_px=20, pan_kp=.1, max_step_command=8, command_interval_ms=120,
        hardware_command_dedup_seconds=.75, hardware_min_angle_change=1,
        ai_handoff_timeout=3,
        hardware_zone_policies={"MAIN_ENTRANCE": {
            "lock_on_unauthorized": True, "unlock_on_authorized": True,
            "unlock_duration": 2, "alarm_on_suspicious": False,
            "alarm_on_high_risk": True, "alarm_on_security_alert": True,
            "suspicious_dwell_seconds": .01, "high_risk_dwell_seconds": .02,
            "security_alert_dwell_seconds": .03, "alarm_duration": .2,
            "alarm_mode": "SIREN_STROBE", "authorized_access_levels": ["STANDARD"],
        }},
    )
    defs=[]
    for i in range(1,4):
        defs.append(DeviceDefinition(f"camera_mount_{i}", DeviceType.CAMERA_MOUNT.value, zone="MAIN_ENTRANCE", limits={"min_pan":-180,"max_pan":180,"min_tilt":-90,"max_tilt":90,"max_speed":1}))
    for i in range(1,3):
        defs.append(DeviceDefinition(f"door_{i}", DeviceType.DOOR_LOCK.value, zone="MAIN_ENTRANCE", limits={"max_unlock_duration":2}))
        defs.append(DeviceDefinition(f"alarm_{i}", DeviceType.ALARM.value, zone="MAIN_ENTRANCE", limits={"max_duration":2}))
    h=HardwareController(settings, DeviceRegistry(defs), HardwareStateManager(), MockHardwareDriver())
    h.start(); return h, settings


def event(kind, track="T1", camera="camera_mount_1", status="UNKNOWN", identity="UNKNOWN", details=None, person_id=None):
    return PerceptionEvent(kind, track, camera, bbox=(500,200,80,120), recognition_status=status, identity=identity, person_id=person_id, confidence=.9, zone="MAIN_ENTRANCE", details={"frame_width":640,"frame_height":480, **(details or {})}, correlation_id="corr")


def test_unauthorized_never_unlocks_and_locks():
    h,s=make_system(); sec=SecurityScenarioEngine(h,s)
    sec.handle(event("PERSON_UNKNOWN"))
    snap=h.snapshot(); assert all(d["commanded_lock"] for d in snap["doors"].values())
    assert all(a["state"] != "TRIGGERED" for a in snap["alarms"].values())


def test_tracking_is_rate_limited():
    h,s=make_system()
    first=h.track_camera("camera_mount_1", 600, 240, 640, 480)
    second=h.track_camera("camera_mount_1", 601, 240, 640, 480)
    assert first.success and second.result in {"RATE_LIMITED", "DUPLICATE", "DEADBAND"}


def test_scenario_escalates_without_alarm_storm():
    h,s=make_system(); sec=SecurityScenarioEngine(h,s)
    sec.handle(event("PERSON_UNKNOWN"))
    tr=sec.tracks["T1"]; tr.first_seen -= .05
    sec.handle(event("TRACK_UPDATED"))
    assert any(a["state"] == "TRIGGERED" for a in h.snapshot()["alarms"].values())


def test_cross_camera_known_person_handoff():
    h,s=make_system(); sec=SecurityScenarioEngine(h,s)
    sec.handle(event("PERSON_RECOGNIZED", "T1", "camera_mount_1", "MATCHED", "JOHN"))
    sec.handle(event("PERSON_RECOGNIZED", "T2", "camera_mount_2", "MATCHED", "JOHN"))
    assert any(e["event_type"] == "CAMERA_HANDOFF" for e in sec.last_events)


def test_repeat_visitor_fires_at_threshold_and_resets():
    h, s = make_system()
    s.hardware_zone_policies["MAIN_ENTRANCE"]["repeat_visit_threshold"] = 3
    s.hardware_zone_policies["MAIN_ENTRANCE"]["alert_on_repeat_visitor"] = True
    sec = SecurityScenarioEngine(h, s)

    # Same known person (person_id=7), same camera, but a NEW track each time
    # (as if they left frame and came back) -- exactly "coming to camera >3 times".
    sec.handle(event("PERSON_RECOGNIZED", "T1", "camera_mount_1", "MATCHED", "JOHN", person_id=7))
    assert not any(e["event_type"] == "REPEAT_VISITOR" for e in sec.last_events)

    sec.handle(event("PERSON_RECOGNIZED", "T2", "camera_mount_1", "MATCHED", "JOHN", person_id=7))
    assert not any(e["event_type"] == "REPEAT_VISITOR" for e in sec.last_events)

    sec.handle(event("PERSON_RECOGNIZED", "T3", "camera_mount_1", "MATCHED", "JOHN", person_id=7))
    assert any(e["event_type"] == "REPEAT_VISITOR" for e in sec.last_events)
    assert any(a["mode"] == "STROBE_ONLY" or a["state"] in ("TRIGGERED",) for a in h.snapshot()["alarms"].values())

    # Counter reset after firing -- two more visits should not immediately re-fire.
    events_before = len(sec.last_events)
    sec.handle(event("PERSON_RECOGNIZED", "T4", "camera_mount_1", "MATCHED", "JOHN", person_id=7))
    sec.handle(event("PERSON_RECOGNIZED", "T5", "camera_mount_1", "MATCHED", "JOHN", person_id=7))
    new_events = sec.last_events[events_before:]
    assert not any(e["event_type"] == "REPEAT_VISITOR" for e in new_events)
    assert sec.visit_counts[(7, "camera_mount_1")] == 2


def test_repeat_visitor_never_counts_unknown_faces():
    h, s = make_system()
    s.hardware_zone_policies["MAIN_ENTRANCE"]["repeat_visit_threshold"] = 2
    s.hardware_zone_policies["MAIN_ENTRANCE"]["alert_on_repeat_visitor"] = True
    sec = SecurityScenarioEngine(h, s)
    # Same track pattern, but never resolved to a person_id -- must never fire,
    # since an unrecognized face can't be confirmed as "the same person" twice.
    for i in range(5):
        sec.handle(event("PERSON_UNKNOWN", f"T{i}", "camera_mount_1", "UNKNOWN", "UNKNOWN", person_id=None))
    assert not any(e["event_type"] == "REPEAT_VISITOR" for e in sec.last_events)
