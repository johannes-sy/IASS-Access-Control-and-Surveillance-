from __future__ import annotations
import json
from pathlib import Path
from .models import Site, Building, Floor, Zone, Installation, Relationship
from .registry import HardwareTopology

def load_topology(path: Path) -> HardwareTopology:
    if not path.exists(): return HardwareTopology()
    data=json.loads(path.read_text())
    site=Site(**data["site"]) if data.get("site") else None
    return HardwareTopology(site=site,
        buildings=[Building(**x) for x in data.get("buildings",[])],
        floors=[Floor(**x) for x in data.get("floors",[])],
        zones=[Zone(**x) for x in data.get("zones",[])],
        installations=[Installation(**x) for x in data.get("installations",[])],
        relationships=[Relationship(**x) for x in data.get("relationships",[])])

def save_topology(path: Path, topology: HardwareTopology):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(topology.snapshot(), indent=2, sort_keys=True))
