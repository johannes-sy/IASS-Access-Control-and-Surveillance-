class DoorHardwareControl:
    def __init__(self, owner): self.hw=owner
    def lock(self,door_id,reason=None,correlation_id=None): return self.hw.lock_door(door_id,reason,correlation_id)
    def unlock(self,door_id,duration=None,reason=None,correlation_id=None): return self.hw.unlock_door(door_id,duration,reason,correlation_id)
    def state(self,door_id): return self.hw.state.doors[door_id]
