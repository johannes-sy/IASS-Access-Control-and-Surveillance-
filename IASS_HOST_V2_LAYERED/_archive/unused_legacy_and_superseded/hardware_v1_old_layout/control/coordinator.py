from .planner import HardwareActionPlan

class HardwareCoordinator:
    """Executes semantic hardware actions against the configured physical topology.

    It deliberately contains no authorization, threat, risk, or incident logic.
    """
    def __init__(self, hardware, topology):
        self.hardware=hardware; self.topology=topology
        self.camera=__import__(__package__+'.camera',fromlist=['CameraHardwareControl']).CameraHardwareControl(hardware)
        self.door=__import__(__package__+'.door',fromlist=['DoorHardwareControl']).DoorHardwareControl(hardware)
        self.alarm=__import__(__package__+'.alarm',fromlist=['AlarmHardwareControl']).AlarmHardwareControl(hardware)
    def execute(self,plan:HardwareActionPlan):
        results=[]
        for action in plan.actions:
            p=dict(action.params); zone=p.get('zone'); targets=[action.target] if action.target else []
            if not targets and zone:
                dtype={"LOCK_ZONE":"DOOR_LOCK","UNLOCK_ZONE":"DOOR_LOCK","TRACK_ZONE":"CAMERA_MOUNT","ALARM_ZONE":"ALARM","HOME_ZONE":"CAMERA_MOUNT"}.get(action.action)
                if dtype: targets=[d.device_id for d in self.topology.devices_in_zone(zone,dtype)]
            for target in targets:
                if not target: continue
                if action.action in {'TRACK_TARGET','TRACK_CAMERA'}: results.append(self.camera.track(target,p.get('x',0),p.get('y',0),p.get('frame_width',640),p.get('frame_height',480),p.get('target_id'),plan.correlation_id))
                elif action.action=='MOVE_CAMERA': results.append(self.camera.move(target,p.get('pan',0),p.get('tilt',0),p.get('speed',1),plan.correlation_id))
                elif action.action in {'STOP_CAMERA','STOP_TRACKING'}: results.append(self.camera.stop(target,plan.correlation_id))
                elif action.action=='HOME_CAMERA': results.append(self.camera.home(target,plan.correlation_id))
                elif action.action in {'LOCK_DOOR','LOCK_ZONE'}: results.append(self.door.lock(target,p.get('reason',plan.reason),plan.correlation_id))
                elif action.action in {'UNLOCK_DOOR','UNLOCK_ZONE'}: results.append(self.door.unlock(target,p.get('duration'),p.get('reason',plan.reason),plan.correlation_id))
                elif action.action in {'TRIGGER_ALARM','ALARM_ZONE'}: results.append(self.alarm.trigger(target,p.get('mode','SIREN_STROBE'),p.get('duration'),p.get('reason',plan.reason),plan.correlation_id))
                elif action.action=='CLEAR_ALARM': results.append(self.alarm.clear(target,p.get('reason',plan.reason),plan.correlation_id))
        return results
