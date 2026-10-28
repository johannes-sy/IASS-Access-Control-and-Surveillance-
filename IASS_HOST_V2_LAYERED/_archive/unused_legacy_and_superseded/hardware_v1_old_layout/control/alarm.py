class AlarmHardwareControl:
    def __init__(self, owner): self.hw=owner
    def trigger(self,alarm_id,mode="SIREN_STROBE",duration=None,reason=None,correlation_id=None): return self.hw.trigger_alarm(alarm_id,mode,duration,reason,correlation_id)
    def clear(self,alarm_id,reason=None,correlation_id=None): return self.hw.clear_alarm(alarm_id,reason,correlation_id)
