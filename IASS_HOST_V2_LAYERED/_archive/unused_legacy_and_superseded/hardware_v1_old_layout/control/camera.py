class CameraHardwareControl:
    def __init__(self, owner): self.hw=owner
    def move(self,camera_id,pan_angle,tilt_angle=0.0,speed=1.0,correlation_id=None): return self.hw.rotate_camera(camera_id,pan_angle,tilt_angle,speed,correlation_id)
    def track(self,camera_id,target_x,target_y,frame_width,frame_height,target_id=None,correlation_id=None): return self.hw.track_camera(camera_id,target_x,target_y,frame_width,frame_height,correlation_id,target_id)
    def stop(self,camera_id,correlation_id=None): return self.hw.stop_camera(camera_id,correlation_id)
    def home(self,camera_id,correlation_id=None): return self.hw.home_camera(camera_id,correlation_id)
