class AlarmController:
    def __init__(self, command_bus, safety):
        self.bus, self.safety = command_bus, safety

    def trigger(self, alarm_id: str, reason: str) -> bool:
        if not self.safety.allow_alarm(reason):
            return False
        return self.bus.command("ALARM_TRIGGER", alarm_id, reason)

    def strobe(self, alarm_id: str, enabled: bool) -> bool:
        return self.bus.command("ALARM_STROBE", alarm_id, int(enabled))

    def silence(self, alarm_id: str) -> bool:
        return self.bus.command("ALARM_SILENCE", alarm_id)
