"""Application scenarios: authorization -> hardware action.

Controllers remain reusable; scenarios contain business workflows.
"""


class AccessControlScenario:
    def __init__(self, locks, alarms, events):
        self.locks, self.alarms, self.events = locks, alarms, events

    def authorized_entry(self, lock_id, person, authorization):
        ok = self.locks.unlock(lock_id, authorization)
        self.events.record("AUTHORIZED_ENTRY", person, lock_id, ok)
        return ok

    def unauthorized_attempt(self, alarm_id, person, camera_id):
        self.events.record("UNAUTHORIZED_ATTEMPT", person, camera_id, False)
        return self.alarms.trigger(alarm_id, f"Unauthorized target on {camera_id}")
