"""Stateful host-side security scenario engine.

AI supplies perception facts. This module owns risk transitions, access policy,
tracking/handoff orchestration, alarm escalation and event/audit semantics.
No serial or GPIO knowledge belongs here.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from iass.hardware.models import HardwareIntent
from iass.hardware.scenarios.risk import RiskLevel
from iass.ai.camera_association import CrossCameraTrackManager


@dataclass
class ScenarioTrack:
    track_id: str
    first_seen: float
    last_seen: float
    camera_id: str
    zone: str
    identity: str = "UNKNOWN"
    person_id: int | None = None
    recognition_status: str = "UNKNOWN"
    risk: str = RiskLevel.NORMAL.value
    authorized: bool = False
    last_transition: str | None = None
    previous_camera: str | None = None
    cameras: list[str] = field(default_factory=list)


class SecurityScenarioEngine:
    def __init__(self, hardware, settings, db=None, event_bus=None):
        self.hardware = hardware
        self.settings = settings
        self.db = db
        self.events = event_bus or getattr(hardware, "events", None)
        self.tracks: dict[str, ScenarioTrack] = {}
        self.global_tracks = CrossCameraTrackManager(getattr(settings, "ai_handoff_timeout", 3.0))
        self.cooldowns: dict[tuple, float] = {}
        self.last_events: list[dict] = []

    def _policy(self, zone):
        return (getattr(self.settings, "hardware_zone_policies", {}) or {}).get(zone, {})

    def _publish(self, event_type, e, severity="INFO", **payload):
        data = {"track_id": getattr(e, "track_id", None), "camera_id": getattr(e, "camera_id", None),
                "zone": getattr(e, "zone", None), "identity": getattr(e, "identity", "UNKNOWN"),
                "person_id": getattr(e, "person_id", None), **payload}
        self.last_events.append({"event_type": event_type, "timestamp": time.time(), **data})
        self.last_events = self.last_events[-200:]
        if self.db:
            try:
                self.db.event(data["identity"], float(getattr(e, "confidence", 0.0)),
                              bool(payload.get("authorized", False)), event_type=event_type,
                              person_id=data["person_id"], camera_id=data["camera_id"],
                              camera_name=data["camera_id"], correlation_id=getattr(e, "correlation_id", None),
                              details=data)
            except Exception:
                pass
        if self.events:
            try:
                from iass.hardware.services.events_bus import HardwareEvent
                self.events.publish(HardwareEvent(event_type=event_type, device_id=data["camera_id"],
                    correlation_id=getattr(e, "correlation_id", None), severity=severity, payload=data))
            except Exception:
                pass

    def _intent(self, event_type, e, authorized=None, **details):
        bbox = e.bbox or (0, 0, 0, 0)
        return HardwareIntent(
            intent=event_type, zone=e.zone, camera_id=e.camera_id, person_id=e.person_id,
            identity=e.identity, authorized=authorized, confidence=e.confidence,
            target={"x": bbox[0] + bbox[2] / 2, "y": bbox[1] + bbox[3] / 2,
                    "frame_width": e.details.get("frame_width", 640),
                    "frame_height": e.details.get("frame_height", 480)},
            source="AI", correlation_id=e.correlation_id or f"AI-{int(time.time()*1000)}",
            details={**e.details, "track_id": e.track_id, **details},
        )

    def _authorized(self, e, policy):
        if e.recognition_status != "MATCHED" or not self.db or not e.person_id:
            return False
        try:
            person = self.db.get_person(e.person_id)
        except Exception:
            person = None
        levels = set(policy.get("authorized_access_levels", ["STANDARD", "ADMIN", "SECURITY"]))
        return bool(person and person.get("enabled", 1) and person.get("access_level", "STANDARD") in levels)

    def _transition(self, tr, new):
        if tr.risk == new:
            return False
        tr.risk = new
        tr.last_transition = new
        return True

    def _cooldown(self, key, seconds):
        now = time.time(); last = self.cooldowns.get(key, 0.0)
        if now - last < seconds: return False
        self.cooldowns[key] = now; return True

    def handle(self, e):
        now = time.time(); policy = self._policy(e.zone)
        if e.event_type == "TRACK_LOST":
            tr = self.tracks.pop(e.track_id, None)
            if tr:
                self._publish("TARGET_LOST", e, risk=tr.risk, cameras=tr.cameras)
            self.hardware.handle_intent(self._intent("TARGET_LOST", e))
            return []

        tr = self.tracks.get(e.track_id)
        if tr is None:
            tr = ScenarioTrack(e.track_id, now, now, e.camera_id, e.zone)
            self.tracks[e.track_id] = tr
        tr.last_seen = now; tr.camera_id = e.camera_id
        tr.zone = e.zone; tr.identity = e.identity; tr.person_id = e.person_id
        tr.recognition_status = e.recognition_status
        if e.camera_id not in tr.cameras: tr.cameras.append(e.camera_id)

        # Cross-camera handoff uses an explicit re-identification/group key when available,
        # otherwise a stable person_id/known identity. Unknown faces are never guessed equal.
        handoff_key = e.details.get("track_group_id") or e.details.get("reid_key")
        global_id = e.person_id if e.person_id is not None else (e.identity if e.identity != "UNKNOWN" else handoff_key)
        if global_id is not None:
            old_tid, old_camera = self.global_tracks.handoff_candidate(str(global_id), e.person_id, now)
            if old_tid and old_camera != e.camera_id and old_tid != e.track_id:
                tr.previous_camera = old_camera
                if old_camera in tr.cameras: pass
                self._publish("CAMERA_HANDOFF", e, previous_camera=old_camera, new_camera=e.camera_id)
                self.hardware.handle_intent(self._intent("TRACK_HANDOFF", e, previous_camera=old_camera))
            self.global_tracks.update(str(global_id), e.camera_id, e.identity, e.person_id, now)

        # Every active target can be tracked, but the hardware controller rate-limits commands.
        if e.event_type in ("PERSON_RECOGNIZED", "PERSON_UNKNOWN", "TRACK_UPDATED", "FACE_UNCERTAIN"):
            self.hardware.handle_intent(self._intent("TARGET_MOVING", e))

        # Tailgating is a compound observation supplied by the perception/access layer;
        # the scenario engine owns the response and never asks the MCU to infer it.
        if e.details.get("tailgating") or (int(e.details.get("authorized_count", 0)) > 0 and int(e.details.get("unauthorized_count", 0)) > 0):
            if self._cooldown((e.zone, "tailgating"), float(policy.get("tailgating_cooldown", 10))):
                self._publish("TAILGATING_DETECTED", e, severity="CRITICAL", authorized=False)
                self.hardware.handle_intent(self._intent("SECURITY_ALERT", e, authorized=False, risk=RiskLevel.SECURITY_ALERT.value, tailgating=True))

        authorized = self._authorized(e, policy)
        tr.authorized = authorized
        if authorized:
            if self._transition(tr, RiskLevel.NORMAL.value) and e.event_type == "PERSON_RECOGNIZED":
                self._publish("AUTHORIZED_PERSON", e, authorized=True, risk=RiskLevel.NORMAL.value)
            if e.event_type == "PERSON_RECOGNIZED" and policy.get("unlock_on_authorized", True) and self._cooldown((e.track_id, "unlock"), float(policy.get("access_command_cooldown", 3))):
                self.hardware.handle_intent(self._intent("AUTHORIZED_PERSON", e, authorized=True))
            return []

        # Unknown/uncertain people never receive an unlock action.
        if e.recognition_status in ("UNKNOWN", "AMBIGUOUS", "LOW_CONFIDENCE") or e.event_type == "PERSON_UNKNOWN":
            dwell = now - tr.first_seen
            suspicious_after = float(policy.get("suspicious_dwell_seconds", 10))
            high_after = float(policy.get("high_risk_dwell_seconds", 20))
            alert_after = float(policy.get("security_alert_dwell_seconds", max(high_after + 10, 30)))
            if dwell >= alert_after:
                changed = self._transition(tr, RiskLevel.SECURITY_ALERT.value)
            elif dwell >= high_after:
                changed = self._transition(tr, RiskLevel.HIGH_RISK.value)
            elif dwell >= suspicious_after:
                changed = self._transition(tr, RiskLevel.SUSPICIOUS.value)
            else:
                changed = self._transition(tr, RiskLevel.OBSERVATION.value)
            if changed:
                self._publish("RISK_CHANGED", e, severity="WARNING" if tr.risk not in (RiskLevel.HIGH_RISK.value, RiskLevel.SECURITY_ALERT.value) else "CRITICAL", risk=tr.risk, dwell_seconds=dwell, authorized=False)
            if changed and tr.risk == RiskLevel.OBSERVATION.value and policy.get("lock_on_unauthorized", True):
                self.hardware.handle_intent(self._intent("UNAUTHORIZED_PERSON", e, authorized=False, risk=tr.risk))
            if tr.risk == RiskLevel.SUSPICIOUS.value and self._cooldown((e.track_id, "suspicious"), float(policy.get("suspicious_action_cooldown", 5))):
                self.hardware.handle_intent(self._intent("SUSPICIOUS_ACTIVITY", e, authorized=False, risk=tr.risk))
            elif tr.risk == RiskLevel.HIGH_RISK.value and self._cooldown((e.track_id, "high-risk"), float(policy.get("high_risk_action_cooldown", 5))):
                self.hardware.handle_intent(self._intent("HIGH_RISK_ACTIVITY", e, authorized=False, risk=tr.risk))
            elif tr.risk == RiskLevel.SECURITY_ALERT.value and self._cooldown((e.track_id, "alert"), float(policy.get("alert_action_cooldown", 10))):
                self.hardware.handle_intent(self._intent("SECURITY_ALERT", e, authorized=False, risk=tr.risk))

            # Explicit restricted-door/attempt events can escalate immediately.
            if e.details.get("door_attempt") or e.details.get("restricted_zone"):
                self._publish("RESTRICTED_ACCESS_ATTEMPT", e, severity="WARNING", authorized=False)
                if policy.get("alarm_on_restricted_attempt", False):
                    self.hardware.handle_intent(self._intent("SUSPICIOUS_ACTIVITY", e, authorized=False, risk=RiskLevel.SUSPICIOUS.value))
        return []

    def authorized_access(self, event, door_id=None):
        self.hardware.handle_intent(self._intent("AUTHORIZED_PERSON", event, authorized=True, door_id=door_id))
