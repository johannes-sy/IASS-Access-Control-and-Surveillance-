from __future__ import annotations
from iass.decision_security.intents import HardwareIntent

class HardwarePolicy:
    """Semantic physical-action policy. No AI/model or serial knowledge."""
    def __init__(self, registry, settings):
        self.registry=registry; self.settings=settings
        self.zone_policies=getattr(settings,"hardware_zone_policies",{}) or {}

    def actions_for_intent(self,intent):
        p=self.zone_policies.get(intent.zone,{})
        actions=[]
        if intent.intent in ("TARGET_MOVING","UNAUTHORIZED_PERSON","SUSPICIOUS_ACTIVITY","SECURITY_ALERT","AUTHORIZED_PERSON"):
            if intent.camera_id:
                cam=self.registry.get(intent.camera_id)
                if cam and cam.device_type=="CAMERA_MOUNT":
                    actions.append(("TRACK_CAMERA",cam.device_id,{"target":intent.target}))
            elif intent.intent in ("UNAUTHORIZED_PERSON","SUSPICIOUS_ACTIVITY","SECURITY_ALERT"):
                for cam in self.registry.by_zone(intent.zone,"CAMERA_MOUNT"):
                    actions.append(("TRACK_CAMERA",cam.device_id,{"target":intent.target}))
        if intent.intent=="AUTHORIZED_PERSON":
            if p.get("unlock_on_authorized",True):
                for d in self.registry.by_zone(intent.zone,"DOOR_LOCK"):
                    actions.append(("UNLOCK_DOOR",d.device_id,{"duration":float(p.get("unlock_duration",5)),"reason":"AUTHORIZED_PERSON"}))
        elif intent.intent in ("UNAUTHORIZED_PERSON",):
            for d in self.registry.by_zone(intent.zone,"DOOR_LOCK"):
                actions.append(("LOCK_DOOR",d.device_id,{"reason":"UNAUTHORIZED_PERSON"}))
            if p.get("alarm_on_unauthorized", False):
                for a in self.registry.by_zone(intent.zone,"ALARM"):
                    actions.append(("TRIGGER_ALARM",a.device_id,{"mode":p.get("alarm_mode","SIREN_STROBE"),"duration":float(p.get("alarm_duration",30)),"reason":"UNAUTHORIZED_PERSON"}))
        elif intent.intent in ("SUSPICIOUS_ACTIVITY", "HIGH_RISK_ACTIVITY"):
            if p.get("lock_on_suspicious",True):
                for d in self.registry.by_zone(intent.zone,"DOOR_LOCK"):
                    actions.append(("LOCK_DOOR",d.device_id,{"reason":"SUSPICIOUS_ACTIVITY"}))
            alarm_key = "alarm_on_high_risk" if intent.intent == "HIGH_RISK_ACTIVITY" else "alarm_on_suspicious"
            if p.get(alarm_key, False):
                for a in self.registry.by_zone(intent.zone,"ALARM"):
                    mode = p.get("high_risk_alarm_mode", p.get("alarm_mode","SIREN_STROBE")) if intent.intent == "HIGH_RISK_ACTIVITY" else p.get("alarm_mode","SIREN_STROBE")
                    actions.append(("TRIGGER_ALARM",a.device_id,{"mode":mode,"duration":float(p.get("alarm_duration",30)),"reason":intent.intent}))
        elif intent.intent=="SECURITY_ALERT":
            for d in self.registry.by_zone(intent.zone,"DOOR_LOCK"):
                actions.append(("LOCK_DOOR",d.device_id,{"reason":"SECURITY_ALERT"}))
            if p.get("alarm_on_security_alert",True):
                for a in self.registry.by_zone(intent.zone,"ALARM"):
                    actions.append(("TRIGGER_ALARM",a.device_id,{"mode":p.get("alarm_mode","SIREN_STROBE"),"duration":float(p.get("alarm_duration",30)),"reason":"SECURITY_ALERT"}))
        elif intent.intent=="TARGET_LOST" and intent.camera_id:
            cam=self.registry.get(intent.camera_id)
            if cam and cam.device_type=="CAMERA_MOUNT":
                actions.append(("STOP_CAMERA",cam.device_id,{}))
        elif intent.intent=="TRACK_HANDOFF" and intent.camera_id:
            cam=self.registry.get(intent.camera_id)
            if cam and cam.device_type=="CAMERA_MOUNT":
                actions.append(("TRACK_CAMERA",cam.device_id,{"target":intent.target}))
        elif intent.intent=="REPEAT_VISITOR":
            # Distinct from UNAUTHORIZED_PERSON/SUSPICIOUS_ACTIVITY: a repeat
            # visitor may well be authorized. This is a "flag it" signal, not
            # a "lock down" signal, so it defaults to a silent, strobe-only
            # indicator (e.g. an LED on the alarm output) rather than a siren,
            # and is opt-in (off by default) since not every deployment wants
            # a physical indicator for this at all.
            if p.get("alert_on_repeat_visitor", False):
                for a in self.registry.by_zone(intent.zone,"ALARM"):
                    actions.append(("TRIGGER_ALARM",a.device_id,{"mode":p.get("repeat_visitor_alarm_mode","STROBE_ONLY"),"duration":float(p.get("repeat_visitor_alarm_duration",5)),"reason":"REPEAT_VISITOR"}))
        return actions
