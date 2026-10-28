"""Backward-compatible facade over the modular AI pipeline."""
import queue, threading
from .pipeline import AIPipeline

class Perception:
    def __init__(self, db, threshold=.78, face_detection=True, recognition=True, person_detection=True, settings=None, camera_id="CAM-01", zone="MAIN_ENTRANCE"):
        if settings is None:
            class S: pass
            settings=S(); settings.face_detection=face_detection; settings.recognition=recognition; settings.person_detection=person_detection
            settings.recognition_threshold=threshold
        self.pipeline=AIPipeline(db,settings,camera_id=camera_id,zone=zone)
    def process(self, frame):
        observations, events=self.pipeline.process(frame)
        results=[]
        for o in observations:
            ident=o["identity"]
            results.append({"bbox":list(o["bbox"]),"person_id":ident.person_id,"identity":ident.identity,
                             "confidence":round(float(ident.similarity),3),"authorized":False,
                            "recognized": ident.status=="MATCHED",
                            "authorization_status": "POLICY_PENDING",
                            "recognition_status":ident.status,"quality":o.get("quality",0.0),
                            "detection_type":o.get("detection_type","face")})
        # Authorization is deliberately not decided by AI.
        for r in results:
            r["authorized"] = r["recognition_status"]=="MATCHED"
        self._last_events = self.pipeline._last_events
        return results
    def extract_face(self, frame):
        boxes=self.pipeline.faces.detect(frame)
        if not boxes:return None
        x,y,w,h=max(boxes,key=lambda b:b[2]*b[3])
        return frame[y:y+h,x:x+w].copy()
    def refresh_enrollment(self): self.pipeline.refresh_enrollment()

class AIWorker:
    def __init__(self, perception, callback, every_n_frames=2, event_callback=None):
        self.perception=perception; self.callback=callback; self.event_callback=event_callback
        self.every_n_frames=max(1,int(every_n_frames)); self.queue=queue.Queue(maxsize=1)
        self.stop=threading.Event(); self.thread=None; self.frame_count=0; self.processed=0
    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop.clear(); self.thread=threading.Thread(target=self._run,name="iass-ai",daemon=True); self.thread.start()
    def submit(self,frame):
        self.frame_count+=1
        if self.frame_count%self.every_n_frames:return
        try:self.queue.put_nowait(frame.copy())
        except queue.Full:
            try:self.queue.get_nowait(); self.queue.put_nowait(frame.copy())
            except queue.Empty:pass
    def _run(self):
        while not self.stop.is_set():
            try:frame=self.queue.get(timeout=.2)
            except queue.Empty:continue
            try:
                detections=self.perception.process(frame)
                self.processed+=1
                if self.callback:self.callback(detections,frame.shape[1],frame=frame)
                if self.event_callback:
                    for event in getattr(self.perception.pipeline,"_last_events",[]): self.event_callback(event)
            except Exception as exc:
                if self.callback:self.callback([],frame.shape[1],error=str(exc),frame=frame)
    def stop_now(self):
        self.stop.set()
        if self.thread and self.thread.is_alive():self.thread.join(timeout=1)
