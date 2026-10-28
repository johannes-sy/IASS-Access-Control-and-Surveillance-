from .base import HardwareInterface
from ..drivers import AtmegaHardwareDriver

class AtmegaHardwareInterface(HardwareInterface):
    simulation = False
    def __init__(self, link, registry=None): self.link=link; self.driver=AtmegaHardwareDriver(link, registry=registry)
    def connect(self): return self.driver.connect()
    def close(self): return self.driver.close()
    @property
    def connected(self): return self.driver.connected
    def command(self, device_id, action, **params): return self.driver.command(device_id, action, **params)
