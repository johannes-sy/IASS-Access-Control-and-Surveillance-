import numpy as np
from iass.ai_perception.tracker import MultiObjectTracker
from iass.ai_perception.quality import FaceQualityGate
from iass.ai_perception.matcher import FaceMatcher
from iass.db.database import Database

def test_quality_rejects_tiny_face():
    q=FaceQualityGate(min_size=45)
    img=np.zeros((20,20,3),dtype=np.uint8)
    assert not q.assess(img).accepted

def test_tracker_persists_track_id_and_direction():
    t=MultiObjectTracker("CAM-01", max_missed=2, iou_threshold=.1)
    first=list(t.update([{"bbox":(100,100,80,80)}]))[0]
    tid=first[1].track_id
    second=list(t.update([{"bbox":(130,100,80,80)}]))[0]
    assert second[1].track_id==tid
    assert second[1].direction=="RIGHT"

def test_matcher_empty_enrollment_is_unknown(tmp_path):
    db=Database(tmp_path/"x.db")
    from iass.ai_perception.embedder import OpenCVFeatureEmbedder
    m=FaceMatcher(db,.78,.04,OpenCVFeatureEmbedder())
    img=np.ones((64,64,3),dtype=np.uint8)*128
    assert m.match(img)[3]=="UNKNOWN"
