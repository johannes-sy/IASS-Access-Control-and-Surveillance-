from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

@dataclass
class Site:
    site_id: str
    name: str

@dataclass
class Building:
    building_id: str
    name: str
    site_id: str

@dataclass
class Floor:
    floor_id: str
    name: str
    building_id: str

@dataclass
class Zone:
    zone_id: str
    name: str
    floor_id: str
    zone_type: str = "ROOM"
    restricted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class Installation:
    device_id: str
    device_type: str
    zone_id: str
    position: str = ""
    orientation: dict[str, float] = field(default_factory=dict)
    coverage: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    driver: str = "mock"
    enabled: bool = True
    limits: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)

@dataclass
class Relationship:
    source: str
    relation: str
    target: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)
