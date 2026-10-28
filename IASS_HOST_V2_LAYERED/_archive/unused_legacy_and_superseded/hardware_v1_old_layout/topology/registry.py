from __future__ import annotations
from dataclasses import asdict
from .models import Site, Building, Floor, Zone, Installation, Relationship

class HardwareTopology:
    """Operator-defined physical installation model; contains no security decisions."""
    def __init__(self, site=None, buildings=None, floors=None, zones=None, installations=None, relationships=None):
        self.site = site
        self.buildings = {x.building_id: x for x in (buildings or [])}
        self.floors = {x.floor_id: x for x in (floors or [])}
        self.zones = {x.zone_id: x for x in (zones or [])}
        self.installations = {x.device_id: x for x in (installations or [])}
        self.relationships = list(relationships or [])

    def installation(self, device_id): return self.installations.get(device_id)
    def devices_in_zone(self, zone_id, device_type=None):
        return [x for x in self.installations.values() if x.enabled and x.zone_id == zone_id and (device_type is None or x.device_type == device_type)]
    def related(self, device_id, relation=None):
        out=[]
        for r in self.relationships:
            if r.source == device_id and (relation is None or r.relation == relation): out.append(r.target)
            elif r.target == device_id and (relation is None or r.relation == relation): out.append(r.source)
        return out
    def cameras_for_zone(self, zone_id): return self.devices_in_zone(zone_id, "CAMERA_MOUNT")
    def doors_for_zone(self, zone_id): return self.devices_in_zone(zone_id, "DOOR_LOCK")
    def alarms_for_zone(self, zone_id): return self.devices_in_zone(zone_id, "ALARM")
    def snapshot(self):
        return {"site": asdict(self.site) if self.site else None,
                "buildings": [asdict(x) for x in self.buildings.values()],
                "floors": [asdict(x) for x in self.floors.values()],
                "zones": [asdict(x) for x in self.zones.values()],
                "installations": [asdict(x) for x in self.installations.values()],
                "relationships": [asdict(x) for x in self.relationships]}
