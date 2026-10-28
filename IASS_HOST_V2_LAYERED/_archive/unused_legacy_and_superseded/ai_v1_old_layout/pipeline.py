"""End-to-end asynchronous perception pipeline."""
import time, uuid
from .detector import FaceDetector, PersonDetector
from .quality import FaceQualityGate
from .embedder import build_embedder
from .matcher import FaceMatcher
from .tracker import MultiObjectTracker
from .models import IdentityResult, PerceptionEvent

class AIPipeline:
    def __init__(self, db, settings, camera_id="CAM-01", zone="MAIN_ENTRANCE", event_bus=None):
        self.settings=settings; self.db=db; self.camera_id=camera_id; self.zone=zone
        self.faces=FaceDetector(settings.face_detection, getattr(settings,"ai_min_face_size",45))
        self.persons=PersonDetector(settings.person_detection)
        self.quality=FaceQualityGate(
            getattr(settings,"ai_min_face_size",45),
            getattr(settings,"ai_min_blur",20.0),
            getattr(settings,"ai_min_brightness",25.0),
            getattr(settings,"ai_max_brightness",235.0),
        )
        self.embedder=build_embedder(getattr(settings,"ai_embedding_backend","opencv"))
        self.matcher=FaceMatcher(db, settings.recognition_threshold, getattr(settings,"ai_ambiguity_margin",0.04), self.embedder)
        self.tracker=MultiObjectTracker(camera_id, getattr(settings,"ai_track_max_missed",8), getattr(settings,"ai_track_iou",0.20))
        self.event_bus=event_bus
        self.last_error=None

    def refresh_enrollment(self):
        self.matcher.refresh()

    def process(self, frame):
        if frame is None: return [], []
        events=[]; observations=[]
        face_boxes=self.faces.detect(frame)
        for box in face_boxes:
            x,y,w,h=box; crop=frame[y:y+h,x:x+w]
            q=self.quality.assess(crop)
            if q.accepted and self.settings.recognition:
                pid,name,sim,status=self.matcher.match(crop)
            else:
                pid,name,sim,status=None,"UNKNOWN",0.0,("LOW_CONFIDENCE" if not q.accepted else "DISABLED")
            observations.append({
                "bbox":box,
                "identity":IdentityResult(pid,name,float(sim),status),
                "quality":q.score,
                "detection_type":"face",
            })
        # Track faces; body detection remains an independent capability.
        for kind,t,obs in self.tracker.update(observations):
            ident=t.identity
            if obs:
                ident=obs["identity"]; t.identity=ident
            etype={"CREATED":"TRACK_CREATED","UPDATED":"TRACK_UPDATED","LOST":"TRACK_LOST"}[kind]
            if kind!="LOST":
                if ident.status=="MATCHED":
                    event_type="PERSON_RECOGNIZED" if kind=="CREATED" else "TRACK_UPDATED"
                elif ident.status=="UNKNOWN":
                    event_type="PERSON_UNKNOWN" if kind=="CREATED" else "TRACK_UPDATED"
                else:
                    event_type="FACE_UNCERTAIN"
            else:
                event_type=etype
            ev=PerceptionEvent(
                event_type=event_type,track_id=t.track_id,camera_id=self.camera_id,
                bbox=t.bbox if kind!="LOST" else t.bbox,person_id=ident.person_id,
                identity=ident.identity,recognition_status=ident.status,
                confidence=ident.similarity,direction=t.direction,velocity=t.velocity,
                zone=self.zone,quality=obs["quality"] if obs else 0.0,
                correlation_id=str(uuid.uuid4()),
                details={"movement_speed": (t.velocity[0]**2+t.velocity[1]**2)**0.5, "frame_width": int(frame.shape[1]), "frame_height": int(frame.shape[0])},
            )
            events.append(ev)
        # Explicit person detections are emitted only when no face box covers them.
        if self.settings.person_detection:
            for box in self.persons.detect(frame):
                x,y,w,h=box
                covered=any(x < fx+fw and x+w>fx and y<fy+fh and y+h>fy for fx,fy,fw,fh in face_boxes)
                if not covered:
                    observations.append({"bbox":box,"identity":IdentityResult(None,"UNKNOWN",0.0,"UNKNOWN"),"quality":0.0,"detection_type":"person"})
        self._last_events = events
        return observations, events
