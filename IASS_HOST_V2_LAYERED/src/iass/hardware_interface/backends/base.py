from __future__ import annotations
from abc import ABC, abstractmethod

class HardwareInterface(ABC):
    """Physical-controller boundary. No security or site-topology decisions live here."""
    simulation = False
    @abstractmethod
    def connect(self) -> bool: ...
    @abstractmethod
    def close(self) -> None: ...
    @property
    @abstractmethod
    def connected(self) -> bool: ...
    @abstractmethod
    def command(self, device_id: str, action: str, **params) -> bool: ...
