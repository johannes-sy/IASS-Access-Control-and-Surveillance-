class LockController:
    """Door-lock policy boundary. Safety policy can reject commands before transport."""

    def __init__(self, command_bus, safety):
        self.bus, self.safety = command_bus, safety

    def lock(self, lock_id: str) -> bool:
        return self.bus.command("LOCK", lock_id)

    def unlock(self, lock_id: str, authorization: str) -> bool:
        if not self.safety.authorize_unlock(lock_id, authorization):
            return False
        return self.bus.command("UNLOCK", lock_id)
