class TelemetryController:
    """Read-only hardware status facade."""

    def __init__(self, command_bus, state_store):
        self.bus, self.state = command_bus, state_store

    def snapshot(self):
        return self.state.snapshot()

    def refresh(self) -> bool:
        return self.bus.command("GET_STATUS")
