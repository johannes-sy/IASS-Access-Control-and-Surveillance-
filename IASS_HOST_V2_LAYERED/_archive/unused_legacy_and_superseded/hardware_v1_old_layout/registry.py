from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DeviceDefinition:
    device_id: str
    device_type: str
    driver: str = "mock"
    enabled: bool = True
    zone: str = "MAIN_ENTRANCE"
    capabilities: list[str] = field(default_factory=list)
    limits: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)


class DeviceRegistry:
    def __init__(self, definitions=None):
        self._devices = {d.device_id: d for d in (definitions or [])}


    @classmethod
    def from_topology(cls, topology, default_driver="mock"):
        return cls([DeviceDefinition(x.device_id, x.device_type, x.driver or default_driver, x.enabled, x.zone_id, list(x.capabilities), dict(x.limits), dict(x.config)) for x in topology.installations.values()])

    def register(self, definition: DeviceDefinition):
        self._devices[definition.device_id] = definition

    def get(self, device_id):
        return self._devices.get(device_id)

    def all(self):
        return list(self._devices.values())

    def by_type(self, device_type):
        return [d for d in self._devices.values() if d.device_type == device_type and d.enabled]

    def by_zone(self, zone, device_type=None):
        return [
            d for d in self._devices.values()
            if d.enabled and d.zone == zone and (device_type is None or d.device_type == device_type)
        ]

    def snapshot(self):
        return [
            {
                "device_id": d.device_id,
                "device_type": d.device_type,
                "driver": d.driver,
                "enabled": d.enabled,
                "zone": d.zone,
                "capabilities": list(d.capabilities),
                "limits": dict(d.limits),
                "config": dict(d.config),
            }
            for d in self._devices.values()
        ]
