from .base import HardwareInterface
from ..drivers import MockHardwareDriver
class SimulatedHardwareInterface(HardwareInterface):
    simulation=True
    def __init__(self, registry=None): self.driver=MockHardwareDriver(); self.driver.registry=registry; self.registry=registry; self.link=None
    def connect(self): return self.driver.connect()
    def close(self): return self.driver.close()
    @property
    def connected(self): return self.driver.connected
    def command(self, device_id, action, **params): return self.driver.command(device_id, action, **params)
