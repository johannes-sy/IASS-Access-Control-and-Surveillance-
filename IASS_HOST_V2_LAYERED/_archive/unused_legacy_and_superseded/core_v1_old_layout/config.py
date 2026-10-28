from pathlib import Path
import tomllib
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parents[3]

@dataclass
class Settings:
    server_host: str = '0.0.0.0'; server_port: int = 5000
    camera_source: str = 'phone_browser'; camera_url: str = ''; fps_limit: int = 15; jpeg_quality: int = 82
    ai_enabled: bool = True; person_detection: bool = True; face_detection: bool = True; recognition: bool = True
    recognition_threshold: float = .78; process_every_n_frames: int = 2
    ai_embedding_backend: str = 'opencv'; ai_ambiguity_margin: float = .04
    ai_min_face_size: int = 45; ai_min_blur: float = 20.0
    ai_min_brightness: float = 25.0; ai_max_brightness: float = 235.0
    ai_track_max_missed: int = 8; ai_track_iou: float = .20; ai_handoff_timeout: float = 3.0
    tracking_enabled: bool = False; pan_kp: float = .045; pan_deadband_px: int = 45; max_step_command: int = 8; command_interval_ms: int = 120
    hardware_command_dedup_seconds: float = .75; hardware_min_angle_change: float = 1.0
    hardware_command_timeout_seconds: float = 1.0; hardware_max_retries: int = 2; hardware_heartbeat_interval_seconds: float = 1.0; hardware_telemetry_timeout_seconds: float = 3.0
    serial_enabled: bool = False; serial_port: str = '/dev/ttyACM0'; serial_baud: int = 115200
    database: str = 'data/iass.db'; recordings: str = 'data/recordings'
    hardware_enabled: bool = True; hardware_simulation: bool = True; hardware_topology: str = 'config/hardware_topology.json'
    hardware_camera_ids: tuple = ('camera_mount_1', 'camera_mount_2', 'camera_mount_3')
    hardware_door_ids: tuple = ('door_1', 'door_2'); hardware_alarm_ids: tuple = ('alarm_1', 'alarm_2')
    hardware_zone_policies: dict = None

def load_settings(path=ROOT/'config/v1.toml'):
    d = tomllib.loads(Path(path).read_text())
    s=Settings(); x=d.get('server',{}); s.server_host=x.get('host',s.server_host); s.server_port=x.get('port',s.server_port)
    x=d.get('camera',{}); s.camera_source=x.get('source',s.camera_source); s.camera_url=x.get('source_url',s.camera_url); s.fps_limit=x.get('fps_limit',s.fps_limit); s.jpeg_quality=x.get('jpeg_quality',s.jpeg_quality)
    x=d.get('ai',{}); s.ai_enabled=x.get('enabled',s.ai_enabled); s.person_detection=x.get('person_detection',s.person_detection); s.face_detection=x.get('face_detection',s.face_detection); s.recognition=x.get('recognition',s.recognition); s.recognition_threshold=x.get('recognition_threshold',s.recognition_threshold); s.process_every_n_frames=x.get('process_every_n_frames',s.process_every_n_frames)
    s.ai_embedding_backend=x.get('embedding_backend',s.ai_embedding_backend); s.ai_ambiguity_margin=x.get('ambiguity_margin',s.ai_ambiguity_margin)
    s.ai_min_face_size=x.get('min_face_size',s.ai_min_face_size); s.ai_min_blur=x.get('min_blur',s.ai_min_blur)
    s.ai_min_brightness=x.get('min_brightness',s.ai_min_brightness); s.ai_max_brightness=x.get('max_brightness',s.ai_max_brightness)
    s.ai_track_max_missed=x.get('track_max_missed',s.ai_track_max_missed); s.ai_track_iou=x.get('track_iou',s.ai_track_iou); s.ai_handoff_timeout=x.get('handoff_timeout',s.ai_handoff_timeout)
    x=d.get('tracking',{}); s.tracking_enabled=x.get('enabled',s.tracking_enabled); s.pan_kp=x.get('pan_kp',s.pan_kp); s.pan_deadband_px=x.get('pan_deadband_px',s.pan_deadband_px); s.max_step_command=x.get('max_step_command',s.max_step_command); s.command_interval_ms=x.get('command_interval_ms',s.command_interval_ms); s.hardware_command_dedup_seconds=x.get('hardware_command_dedup_seconds',s.hardware_command_dedup_seconds); s.hardware_min_angle_change=x.get('hardware_min_angle_change',s.hardware_min_angle_change)
    x=d.get('serial',{}); s.serial_enabled=x.get('enabled',s.serial_enabled); s.serial_port=x.get('port',s.serial_port); s.serial_baud=x.get('baud',s.serial_baud)
    x=d.get('storage',{}); s.database=x.get('database',s.database); s.recordings=x.get('recordings',s.recordings)
    x=d.get('hardware',{}); s.hardware_enabled=x.get('enabled',s.hardware_enabled); s.hardware_simulation=x.get('simulation',s.hardware_simulation); s.hardware_topology=x.get('topology',s.hardware_topology)
    s.hardware_camera_ids=tuple(x.get('camera_ids', list(s.hardware_camera_ids))); s.hardware_door_ids=tuple(x.get('door_ids', list(s.hardware_door_ids))); s.hardware_alarm_ids=tuple(x.get('alarm_ids', list(s.hardware_alarm_ids)))
    proto=x.get('protocol',{}); s.hardware_command_dedup_seconds=proto.get('command_dedup_seconds',s.hardware_command_dedup_seconds); s.hardware_command_timeout_seconds=proto.get('command_timeout_seconds',s.hardware_command_timeout_seconds); s.hardware_max_retries=proto.get('max_retries',s.hardware_max_retries); s.hardware_heartbeat_interval_seconds=proto.get('heartbeat_interval_seconds',s.hardware_heartbeat_interval_seconds); s.hardware_telemetry_timeout_seconds=proto.get('telemetry_timeout_seconds',s.hardware_telemetry_timeout_seconds)
    s.hardware_zone_policies=x.get('zone_policies', {'MAIN_ENTRANCE': {'lock_on_unauthorized': True, 'alarm_on_unauthorized': False, 'unlock_on_authorized': True, 'unlock_duration': 5, 'lock_on_suspicious': True, 'alarm_on_suspicious': False, 'alarm_on_high_risk': True, 'alarm_on_security_alert': True, 'alarm_mode': 'SIREN_STROBE', 'alarm_duration': 30, 'suspicious_dwell_seconds': 10, 'high_risk_dwell_seconds': 20, 'security_alert_dwell_seconds': 30}})
    return s
