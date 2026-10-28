"""decision_security layer.

Input:  perception events from ai_perception (PerceptionEvent-like objects
        with .track_id, .camera_id, .zone, .identity, .person_id, .bbox, ...)
Output: HardwareIntent, consumed exclusively by hardware_control.

This is the "Person 42 is authorized" step: the only layer allowed to decide
who is authorized, what risk level a track is at, and when to escalate.
"""
from .intents import HardwareIntent
from .risk import RiskLevel
from .security_engine import SecurityScenarioEngine, ScenarioTrack

__all__ = ["HardwareIntent", "RiskLevel", "SecurityScenarioEngine", "ScenarioTrack"]
