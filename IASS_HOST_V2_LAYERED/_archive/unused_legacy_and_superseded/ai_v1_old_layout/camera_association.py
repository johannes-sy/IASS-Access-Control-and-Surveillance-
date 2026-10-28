"""Cross-camera identity/track handoff support.

A camera stream supplies observations; this registry lets the host preserve a
logical track when another camera sees a compatible target.  Actual visual
re-identification can later replace the simple identity/appearance hooks.
"""
import time

class CrossCameraTrackManager:
    def __init__(self, handoff_timeout=3.0):
        self.handoff_timeout=float(handoff_timeout)
        self.active={}
        self.history={}
    def update(self, track_id, camera_id, identity="UNKNOWN", person_id=None, timestamp=None):
        now=timestamp or time.time()
        previous=self.active.get(track_id)
        self.active[track_id]={"camera_id":camera_id,"identity":identity,"person_id":person_id,"last_seen":now}
        self.history.setdefault(track_id,[]).append({"camera_id":camera_id,"timestamp":now})
        return previous is not None and previous["camera_id"] != camera_id
    def handoff_candidate(self, identity, person_id=None, now=None):
        now=now or time.time()
        for tid,data in self.active.items():
            if now-data["last_seen"] > self.handoff_timeout: continue
            if person_id is not None and data["person_id"] == person_id: return tid,data["camera_id"]
            if identity != "UNKNOWN" and data["identity"] == identity: return tid,data["camera_id"]
        return None,None
    def history_for(self, track_id):
        return list(self.history.get(track_id,[]))
