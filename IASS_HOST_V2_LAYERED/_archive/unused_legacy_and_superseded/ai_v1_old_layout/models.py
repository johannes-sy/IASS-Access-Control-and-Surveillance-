"""Typed data models for the host-side perception pipeline.

These models deliberately contain perception facts only.  Authorization,
security policy and physical actuation belong to higher layers.
"""
from dataclasses import dataclass, field
from typing import Optional, Tuple
import time

BBox = Tuple[int, int, int, int]

@dataclass
class FaceObservation:
    bbox: BBox
    landmarks: Optional[object] = None
    quality: float = 0.0
    blur: float = 0.0
    brightness: float = 0.0
    accepted: bool = True

@dataclass
class IdentityResult:
    person_id: Optional[int]
    identity: str
    similarity: float
    status: str  # MATCHED, UNKNOWN, AMBIGUOUS, LOW_CONFIDENCE, DISABLED
    stable: bool = False

@dataclass
class Track:
    track_id: str
    camera_id: str
    bbox: BBox
    first_seen: float
    last_seen: float
    velocity: Tuple[float, float] = (0.0, 0.0)
    direction: str = "STATIONARY"
    identity: IdentityResult = field(default_factory=lambda: IdentityResult(None, "UNKNOWN", 0.0, "UNKNOWN"))
    missed_frames: int = 0
    zone: str = "MAIN_ENTRANCE"
    active: bool = True
    previous_camera_id: Optional[str] = None

@dataclass
class PerceptionEvent:
    event_type: str
    track_id: str
    camera_id: str
    timestamp: float = field(default_factory=time.time)
    bbox: Optional[BBox] = None
    person_id: Optional[int] = None
    identity: str = "UNKNOWN"
    recognition_status: str = "UNKNOWN"
    confidence: float = 0.0
    direction: str = "STATIONARY"
    velocity: Tuple[float, float] = (0.0, 0.0)
    zone: str = "MAIN_ENTRANCE"
    quality: float = 0.0
    details: dict = field(default_factory=dict)
    correlation_id: Optional[str] = None
