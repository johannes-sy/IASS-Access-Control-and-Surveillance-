from __future__ import annotations

from .models import HardwareIntent


class HardwarePolicy:
    """Maps semantic security intents to configured devices, never to raw protocol."""

    def __init__(self, registry, settings):
        self.registry = registry
        self.settings = settings
        self.zone_policies = getattr(settings, "hardware_zone_policies", {}) or {}

    def actions_for_intent(self, intent: HardwareIntent):
        policy = self.zone_policies.get(intent.zone, {})
        actions = []
        if intent.intent == "UNAUTHORIZED_PERSON":
            for d in self.registry.by_zone(intent.zone, "CAMERA_MOUNT"):
                actions.append(("TRACK_CAMERA", d.device_id, {"target": intent.target}))
            if policy.get("lock_on_unauthorized", True):
                for d in self.registry.by_zone(intent.zone, "DOOR_LOCK"):
                    actions.append(("LOCK_DOOR", d.device_id, {"reason": "UNAUTHORIZED_PERSON"}))
            if policy.get("alarm_on_unauthorized", True):
                for d in self.registry.by_zone(intent.zone, "ALARM"):
                    actions.append(("TRIGGER_ALARM", d.device_id, {
                        "mode": policy.get("alarm_mode", "SIREN_STROBE"),
                        "duration": float(policy.get("alarm_duration", 30)),
                        "reason": "UNAUTHORIZED_PERSON",
                    }))
        elif intent.intent == "TARGET_MOVING" and intent.camera_id:
            cam = self.registry.get(intent.camera_id)
            if cam and cam.device_type == "CAMERA_MOUNT":
                actions.append(("TRACK_CAMERA", cam.device_id, {"target": intent.target}))
        elif intent.intent == "TARGET_LOST" and intent.camera_id:
            cam = self.registry.get(intent.camera_id)
            if cam and cam.device_type == "CAMERA_MOUNT":
                actions.append(("STOP_CAMERA", cam.device_id, {}))
        return actions
