"""Lightweight multi-object tracker for face/person observations.

It is intentionally dependency-free.  The interface can later be backed by
ByteTrack/SORT without changing AI events consumed by the rest of IASS.
"""
import math, time, uuid
from .models import Track, IdentityResult

def iou(a,b):
    ax,ay,aw,ah=a; bx,by,bw,bh=b
    x1=max(ax,bx); y1=max(ay,by); x2=min(ax+aw,bx+bw); y2=min(ay+ah,by+bh)
    inter=max(0,x2-x1)*max(0,y2-y1)
    union=aw*ah+bw*bh-inter
    return inter/union if union else 0.0

class MultiObjectTracker:
    def __init__(self, camera_id="CAM-01", max_missed=8, iou_threshold=0.20):
        self.camera_id=camera_id
        self.max_missed=int(max_missed)
        self.iou_threshold=float(iou_threshold)
        self.tracks={}
        self.sequence=0

    def _new_id(self):
        self.sequence += 1
        return f"TRACK-{self.sequence:05d}"

    def update(self, observations, now=None):
        now=now or time.time()
        unmatched=set(range(len(observations)))
        # Greedy IoU association is predictable and adequate for the dependency-light V1.
        for tid,t in list(self.tracks.items()):
            best_i=-1; best_score=0.0
            for i in unmatched:
                score=iou(t.bbox, observations[i]["bbox"])
                if score>best_score:
                    best_score=score; best_i=i
            if best_i>=0 and best_score>=self.iou_threshold:
                obs=observations[best_i]; unmatched.remove(best_i)
                ox,oy,ow,oh=obs["bbox"]; tx,ty,tw,th=t.bbox
                dt=max(1e-3, now-t.last_seen)
                oldcx,oldcy=tx+tw/2,ty+th/2
                ncx,ncy=ox+ow/2,oy+oh/2
                vx,vy=(ncx-oldcx)/dt,(ncy-oldcy)/dt
                t.velocity=(vx,vy)
                t.direction=self._direction(vx,vy)
                t.bbox=obs["bbox"]; t.last_seen=now; t.missed_frames=0
                t.active=True
                yield "UPDATED",t,obs
            else:
                t.missed_frames+=1
                if t.missed_frames>self.max_missed:
                    t.active=False
                    yield "LOST",t,None
                    del self.tracks[tid]
        for i in unmatched:
            obs=observations[i]
            tid=self._new_id()
            t=Track(tid,self.camera_id,obs["bbox"],now,now)
            t.identity=obs.get("identity",t.identity)
            self.tracks[tid]=t
            yield "CREATED",t,obs

    @staticmethod
    def _direction(vx,vy):
        if abs(vx)<8 and abs(vy)<8: return "STATIONARY"
        if abs(vx)>=abs(vy): return "RIGHT" if vx>0 else "LEFT"
        return "DOWN" if vy>0 else "UP"
