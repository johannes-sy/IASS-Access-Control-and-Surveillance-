"""ai_perception layer.

Input:  raw frames from camera_stream.
Output: perception events, consumed by decision_security -- the "Person 42
        is being tracked by Camera 3" fact, plus lower-level detections for
        the UI overlay.

detector    - face/person detection (YOLO ONNX, falls back to classic CV)
embedder    - face -> identity vector
quality     - frame/face quality gating before a detection is trusted
tracker     - per-camera multi-object tracking (assigns stable track ids)
matcher     - identity vector -> enrolled person match
camera_association - cross-camera re-identification / handoff
pipeline    - wires the above into one process(frame) call
perception  - threaded worker (Perception, AIWorker) used by the API layer
"""
from .pipeline import AIPipeline
from .perception import Perception, AIWorker

__all__ = ["AIPipeline", "Perception", "AIWorker"]
