"""Semantic AI events. No hardware or GPIO imports belong here."""
from dataclasses import asdict
from .models import PerceptionEvent

class AIEventBus:
    def __init__(self):
        self._listeners=[]
    def subscribe(self, listener):
        self._listeners.append(listener)
    def publish(self, event: PerceptionEvent):
        for listener in tuple(self._listeners):
            try:
                listener(event)
            except Exception:
                # A consumer must never crash perception.
                continue
