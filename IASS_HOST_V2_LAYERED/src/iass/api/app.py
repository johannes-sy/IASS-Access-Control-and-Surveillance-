import asyncio
import base64
import copy
import os
import threading
import time
import uuid
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, Body, File, Form, UploadFile, WebSocket
from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from iass.ai_perception import AIWorker, Perception
from iass.decision_security import SecurityScenarioEngine, HardwareIntent
from iass.camera_stream import CameraManager, FrameHub, MultiCameraHub
from iass.config import ROOT, load_settings
from iass.hardware_control import TrackerController, load_topology, save_topology, HardwareTopology
from iass.hardware_control import DeviceDefinition, DeviceRegistry
from iass.db.database import Database
from iass.hardware_interface import (
    ArduinoLink, HardwareController, AtmegaHardwareDriver, MockHardwareDriver,
    AtmegaHardwareInterface, SimulatedHardwareInterface, DeviceStatus, DeviceType,
    HardwareSafetyPolicy,
)
from iass.hardware_state import HardwareStateManager
from iass.ui.render import render



class CameraMoveRequest(BaseModel):
    pan: float = Field(..., ge=-180, le=180)
    tilt: float = Field(0.0, ge=-90, le=90)
    speed: float = Field(1.0, gt=0, le=1.0)


class CameraTrackRequest(BaseModel):
    x: float
    y: float
    frame_width: int = Field(640, gt=0)
    frame_height: int = Field(480, gt=0)


class DoorRequest(BaseModel):
    duration: float | None = Field(None, gt=0, le=60)
    reason: str | None = None


class AlarmRequest(BaseModel):
    mode: str = "SIREN_STROBE"
    duration: float | None = Field(None, gt=0, le=300)
    reason: str | None = None


class HardwareFeedbackRequest(BaseModel):
    state: str | None = None
    details: dict = Field(default_factory=dict)
    correlation_id: str | None = None


class AccessRequest(BaseModel):
    reader_id: str
    door_id: str
    identity: str | None = None
    authorized: bool
    person_id: int | None = None
    credential_ref: str | None = None
    unlock_duration: float = Field(5.0, gt=0, le=30)

CAMERAS = [
    {"id": "CAM-01", "name": "Main Entrance", "source": "phone_browser", "zone": "MAIN_ENTRANCE"},
    {"id": "CAM-02", "name": "Lobby", "source": "synthetic", "zone": "LOBBY"},
    {"id": "CAM-03", "name": "Parking Area", "source": None, "zone": "PARKING"},
    {"id": "CAM-04", "name": "Corridor", "source": None, "zone": "MAIN_ENTRANCE"},
    {"id": "CAM-05", "name": "Back Entrance", "source": None, "zone": "BACK_ENTRANCE"},
    {"id": "CAM-06", "name": "Main Office", "source": None, "zone": "MAIN_ENTRANCE"},
]
# CAM-02 defaults to a synthetic source (no physical camera needed) specifically so
# two cameras streaming and running AI concurrently is testable out of the box --
# this is the exact scenario that used to crash. Point any CAM-0x entry's "source"
# at "opencv" (with a "url" of a device index or RTSP URL) to drive a real camera;
# everything downstream (streaming, AI, tracking) picks it up with no other changes.


def host_telemetry(link, tracker):
    cpu = 0.0
    try:
        load = os.getloadavg()[0]
        cpu = min(100.0, load * 100.0 / max(1, os.cpu_count() or 1))
    except (AttributeError, OSError):
        pass
    memory = 0.0
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            info[k] = int(v.strip().split()[0])
        total = info.get("MemTotal", 0)
        available = info.get("MemAvailable", info.get("MemFree", 0))
        if total:
            memory = (total - available) * 100.0 / total
    except (OSError, ValueError):
        pass
    rx = 0
    try:
        for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
            if ":" not in line:
                continue
            _, data = line.split(":", 1)
            fields = data.split()
            if fields:
                rx += int(fields[0])
    except (OSError, ValueError):
        pass
    now = time.time()
    prev = getattr(host_telemetry, "_prev", None)
    host_telemetry._prev = (now, rx)
    kbps = 0.0 if not prev else max(0.0, (rx - prev[1]) / max(.001, now - prev[0]) / 1024.0)
    return {
        "cpu_percent": round(cpu, 1),
        "memory_percent": round(memory, 1),
        "network_rx_kbps": round(kbps, 1),
        "arduino_connected": link.state == "CONNECTED",
        "stepper_active": bool(tracker.enabled and link.state == "CONNECTED"),
        "alarm_active": bool(link.telemetry.get("siren") or link.telemetry.get("strobe")),
        "firmware_telemetry": dict(link.telemetry),
        "last_telemetry": link.last_telemetry,
        "serial_last_rx": link.last_rx,
        "serial_last_tx": link.last_tx,
    }


def create_app():
    s = load_settings()
    if os.environ.get("IASS_START_MODE") == "offline":
        s.camera_source = "synthetic"
        s.serial_enabled = False

    db = Database(ROOT / s.database)
    camera_hubs = MultiCameraHub([c["id"] for c in CAMERAS], s.jpeg_quality)

    def _camera_settings(source, url):
        """Shallow per-camera override of the global settings' single
        camera_source/camera_url fields, so each CameraManager instance can
        be told which physical/synthetic source it personally owns."""
        cs = copy.copy(s)
        cs.camera_source = source
        cs.camera_url = url
        return cs

    camera_managers: dict[str, CameraManager] = {}
    ai_pipelines: dict[str, Perception] = {}
    ai_workers: dict[str, AIWorker] = {}
    ai_camera_ids: list[str] = []  # cameras that actually run AI (have a live source)

    def _make_ai_worker(camera_id, zone):
        perception = Perception(
            db, s.recognition_threshold,
            face_detection=s.face_detection, recognition=s.recognition,
            person_detection=s.person_detection, settings=s,
            camera_id=camera_id, zone=zone,
        )
        worker = AIWorker(perception, lambda dets, w, frame=None, cid=camera_id: on_ai_result(cid, dets, w, frame=frame),
                           s.process_every_n_frames)
        ai_pipelines[camera_id] = perception
        ai_workers[camera_id] = worker
        ai_camera_ids.append(camera_id)
        return worker

    for c in CAMERAS:
        src = c.get("source")
        if src in ("opencv", "synthetic"):
            worker = _make_ai_worker(c["id"], c.get("zone", "MAIN_ENTRANCE"))

            def _feed_ai(frame, _worker=worker):
                # state["ai"] is defined further down in this function; safe to
                # reference here because this closure only runs after startup,
                # well after "state" has been assigned (Python late-binding).
                if state["ai"]:
                    _worker.submit(frame)

            hub = camera_hubs.ensure(c["id"])
            mgr = CameraManager(hub, _camera_settings(src, c.get("url") or s.camera_url), on_frame=_feed_ai)
            camera_managers[c["id"]] = mgr
        elif src == "phone_browser":
            # No capture thread: the browser/phone pushes frames via /ws/camera,
            # which submits to this camera's AI worker itself (see ws_camera).
            _make_ai_worker(c["id"], c.get("zone", "MAIN_ENTRANCE"))
        # src is None: camera slot declared but not wired to any source yet --
        # streaming/status endpoints report it OFFLINE, no AI worker is created
        # (nothing to process), matching the previous behavior for these slots.

    ai = ai_pipelines.get("CAM-01")  # kept for any legacy single-camera call sites (e.g. /api/register)
    link = ArduinoLink(s.serial_enabled, s.serial_port, s.serial_baud)
    hardware_state = HardwareStateManager()
    topology = load_topology(ROOT / s.hardware_topology)
    if topology.installations:
        registry = DeviceRegistry.from_topology(topology, default_driver="mock" if s.hardware_simulation or not s.serial_enabled else "atmega328p")
    else:
        definitions = []
        camera_zones = ["MAIN_ENTRANCE", "LOBBY", "PARKING"]
        for index, cid in enumerate(s.hardware_camera_ids):
            definitions.append(DeviceDefinition(cid, DeviceType.CAMERA_MOUNT.value, driver="mock" if s.hardware_simulation or not s.serial_enabled else "atmega328p", zone=camera_zones[index] if index < len(camera_zones) else "MAIN_ENTRANCE", capabilities=["PAN", "TILT", "STOP", "HOME", "POSITION_FEEDBACK"], limits={"min_pan":-180,"max_pan":180,"min_tilt":-90,"max_tilt":90,"max_speed":1.0}))
        for index, did in enumerate(s.hardware_door_ids):
            definitions.append(DeviceDefinition(did, DeviceType.DOOR_LOCK.value, driver="mock" if s.hardware_simulation or not s.serial_enabled else "atmega328p", zone=["MAIN_ENTRANCE","BACK_ENTRANCE"][index] if index < 2 else "MAIN_ENTRANCE", capabilities=["LOCK","UNLOCK","LOCK_FEEDBACK","DOOR_SENSOR"], limits={"max_unlock_duration":10}))
        for index, aid in enumerate(s.hardware_alarm_ids):
            definitions.append(DeviceDefinition(aid, DeviceType.ALARM.value, driver="mock" if s.hardware_simulation or not s.serial_enabled else "atmega328p", zone=["MAIN_ENTRANCE","LOBBY"][index] if index < 2 else "MAIN_ENTRANCE", capabilities=["SILENT","STROBE","SIREN","SIREN_STROBE"], limits={"max_duration":120}))
        registry = DeviceRegistry(definitions)
    for d in registry.all():
        db.upsert_hardware_device(d.device_id, d.device_type, d.driver, d.enabled, d.zone, {"capabilities": d.capabilities, "limits": d.limits, "config": d.config})
    driver = SimulatedHardwareInterface(registry) if s.hardware_simulation or not s.serial_enabled else AtmegaHardwareInterface(link, registry=registry)
    safety = HardwareSafetyPolicy(heartbeat_timeout=float(getattr(s, "hardware_heartbeat_timeout", 5.0)))
    hardware = HardwareController(s, registry, hardware_state, driver, db=db, safety=safety)
    tracker = TrackerController(s, link, hardware=hardware, camera_id=s.hardware_camera_ids[0])
    security = SecurityScenarioEngine(hardware, s, db=db)
    snapshot_root = ROOT / "data" / "snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)

    state = {
        "detections": [],
        "detections_by_camera": {},
        "activity_by_camera": {},
        "tracking": tracker.enabled,
        "ai": s.ai_enabled,
        "frames": 0,
        "fps": 0.0,
        "last_frame_ts": 0.0,
        "ai_status": "READY" if s.ai_enabled else "DISABLED",
        "ai_error": None,
        "previews": [],
        "previews_by_camera": {},
        "activity": "Waiting for a live target.",
        "security_events": [],
        "lock": threading.Lock(),
    }
    # "detections"/"previews"/"activity" mirror whichever camera the legacy
    # single-camera UI/API fields refer to (CAM-01 by default) so existing
    # consumers of /api/state keep working; "*_by_camera" carries the full
    # per-camera breakdown for anything that wants it.
    PRIMARY_CAMERA_ID = "CAM-01"
    event_guard = {"key": None, "time": 0.0}
    event_guard_lock = threading.Lock()

    def save_snapshot(frame, detection):
        if frame is None:
            return None, None
        now = time.localtime()
        folder = snapshot_root / time.strftime("%Y/%m/%d", now)
        folder.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%H%M%S", now) + f"_{int((time.time() % 1) * 1000):03d}"
        full_name = f"event_{stamp}.jpg"
        face_name = f"face_{stamp}.jpg"
        full_path = folder / full_name
        face_path = folder / face_name
        ok = cv2.imwrite(str(full_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        if not ok:
            return None, None
        x, y, w, h = [int(v) for v in detection.get("bbox", [0, 0, 0, 0])]
        x, y = max(0, x), max(0, y)
        crop = frame[y:y + max(1, h), x:x + max(1, w)]
        face_ok = crop.size > 0 and cv2.imwrite(str(face_path), crop, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        rel_full = 'snapshots/' + full_path.relative_to(snapshot_root).as_posix()
        rel_face = 'snapshots/' + face_path.relative_to(snapshot_root).as_posix() if face_ok else None
        return rel_full, rel_face

    def record_detection(detection, frame, camera=None, correlation_id=None):
        # Frame-level AI results are not all audit events. Group repeated observations
        # so a stationary face does not fill the audit database every 100 ms.
        camera = camera or CAMERAS[0]
        key = (camera["id"], detection.get("person_id"), detection.get("identity", "UNKNOWN"), bool(detection.get("authorized")))
        now = time.time()
        with event_guard_lock:
            if key == event_guard["key"] and now - event_guard["time"] < 5.0:
                return
            event_guard["key"] = key
            event_guard["time"] = now
        full_path, face_path = save_snapshot(frame, detection)
        who = detection.get("identity", "UNKNOWN")
        authorized = bool(detection.get("authorized"))
        db.event(
            who,
            detection.get("confidence", 0.0),
            authorized,
            person_id=detection.get("person_id"),
            camera_id=camera["id"],
            camera_name=camera["name"],
            snapshot_path=full_path,
            face_snapshot_path=face_path,
            details={"bbox": detection.get("bbox"), "detection_type": detection.get("detection_type"),
                     "recognition_status": detection.get("recognition_status"),
                     "authorization_status": detection.get("authorization_status", "POLICY_PENDING")},
            correlation_id=correlation_id,
        )

    def on_ai_result(camera_id, detections, frame_width, error=None, frame=None):
        previews = []
        if frame is not None and not error:
            for d in detections:
                if d.get("detection_type") != "face":
                    continue
                x, y, w, h = [int(v) for v in d.get("bbox", [0, 0, 0, 0])]
                x, y = max(0, x), max(0, y)
                crop = frame[y:y + max(1, h), x:x + max(1, w)]
                if crop.size == 0:
                    continue
                ok, enc = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                if ok:
                    previews.append({
                        "identity": d.get("identity", "UNKNOWN"),
                         "recognized": bool(d.get("recognized", d.get("recognition_status") == "MATCHED")),
                        "recognition_status": d.get("recognition_status", "UNKNOWN"),
                        "confidence": d.get("confidence", 0.0),
                        "image": "data:image/jpeg;base64," + base64.b64encode(enc.tobytes()).decode("ascii"),
                    })
        camera_name = next((c["name"] for c in CAMERAS if c["id"] == camera_id), camera_id)
        if detections:
            d = detections[0]
            activity = (
                f"{d.get('identity','UNKNOWN')} detected at {camera_name}. "
                f"{'Identified' if d.get('recognized') else d.get('recognition_status','UNKNOWN')} · "
                f"{round(float(d.get('confidence',0))*100)}% recognition confidence."
            )
        else:
            activity = "No current target detected."
        with state["lock"]:
            state["detections_by_camera"][camera_id] = detections
            state["previews_by_camera"][camera_id] = previews[:6]
            state["activity_by_camera"][camera_id] = activity
            if camera_id == PRIMARY_CAMERA_ID:
                state["detections"] = detections
                state["ai_status"] = "ERROR" if error else "RUNNING"
                state["ai_error"] = error
                state["previews"] = previews[:6]
                state["activity"] = activity
        if error:
            return

        # AI emits perception facts. The security scenario engine is the only
        # layer allowed to turn those facts into physical hardware intents.
        pipeline = ai_pipelines[camera_id].pipeline
        for event in getattr(pipeline, "_last_events", []):
            security.handle(event)
        with state["lock"]:
            state["security_events"] = list(security.last_events[-50:])

        # Persist semantic events, not every inference frame.
        if detections:
            for event in getattr(pipeline, "_last_events", []):
                candidate = next(
                    (d for d in detections
                     if d.get("identity", "UNKNOWN") == event.identity),
                    detections[0],
                )
                camera = {"id": camera_id, "name": camera_name}
                record_detection(candidate, frame, camera=camera, correlation_id=event.correlation_id)

    app = FastAPI(title="IASS Host V1", version="1.1.0")
    app.mount("/static", StaticFiles(directory=ROOT / "src/iass/ui/static"), name="static")
    app.mount("/snapshots", StaticFiles(directory=snapshot_root), name="snapshots")

    @app.on_event("startup")
    async def startup():
        for mgr in camera_managers.values():
            mgr.start()
        hardware.start()
        if s.ai_enabled:
            for worker in ai_workers.values():
                worker.start()

    @app.on_event("shutdown")
    async def shutdown():
        for worker in ai_workers.values():
            worker.stop_now()
        for mgr in camera_managers.values():
            mgr.stop_now()
        hardware.stop()
        if not s.hardware_simulation:
            link.stop()

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return render("app.html")

    @app.get("/logs", response_class=HTMLResponse)
    async def logs_page():
        return render("app.html")

    @app.get("/telemetry", response_class=HTMLResponse)
    async def telemetry_page():
        return render("app.html")

    @app.get("/personnel", response_class=HTMLResponse)
    async def personnel_page():
        return render("app.html")

    @app.get("/register", response_class=HTMLResponse)
    async def register_page():
        return render("app.html")

    @app.get("/security", response_class=HTMLResponse)
    async def security_page():
        return render("app.html")

    @app.get("/hardware", response_class=HTMLResponse)
    async def hardware_page():
        return render("app.html")

    @app.get("/hardware-config", response_class=HTMLResponse)
    async def hardware_config_page():
        return render("app.html")

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page():
        return render("app.html")

    @app.get("/camera", response_class=HTMLResponse)
    async def camera_page():
        return render("camera.html")

    @app.get("/api/security/overview")
    async def security_overview(limit: int = 100):
        rows = db.events(limit=max(1, min(limit, 500)))
        snapshot = hardware.snapshot()
        critical_types = {"SECURITY_ALERT", "HIGH_RISK", "RISK_CHANGED", "TAILGATING_DETECTED"}
        warning_types = {"SUSPICIOUS_ACTIVITY", "PERSON_UNKNOWN", "FACE_UNCERTAIN"}
        critical = sum(1 for r in rows if r.get("event_type") in critical_types)
        suspicious = sum(1 for r in rows if r.get("event_type") in warning_types)
        unauthorized = sum(1 for r in rows if not r.get("authorized"))
        active_alarms = sum(1 for a in snapshot.get("alarms", {}).values() if a.get("state") == "TRIGGERED")
        return {"events": rows, "critical_count": critical, "suspicious_count": suspicious, "unauthorized_count": unauthorized, "active_alarms": active_alarms}

    @app.get("/api/personnel/overview")
    async def personnel_overview():
        people = db.list_people()
        rows = db.events(limit=500)
        # Latest observation per identity is used as a live presence read model.
        # This does not invent entry/exit data; it only reports what the existing
        # perception/event stream actually knows.
        latest = {}
        for r in rows:
            key = r.get("person_id") or r.get("identity") or "UNKNOWN"
            if key not in latest:
                latest[key] = r
        presence=[]
        for r in latest.values():
            if not r.get("identity") and not r.get("person_id"):
                continue
            age=max(0.0, time.time()-float(r.get("ts") or time.time()))
            presence.append({
                "identity": r.get("identity") or "UNKNOWN",
                "person_id": r.get("person_id"),
                "camera_name": r.get("camera_name"),
                "zone": (r.get("details") or {}).get("zone") or r.get("camera_name"),
                "status": "RECENTLY OBSERVED" if age < 15 else "LAST OBSERVED",
                "duration": f"{int(age//60)}m ago" if age >= 60 else f"{int(age)}s ago",
                "authorized": bool(r.get("authorized")),
                "last_seen": r.get("ts"),
            })
        authorized=sum(1 for x in presence if x["authorized"])
        return {"registered_count":len(people),"active_count":len(presence),"authorized_count":authorized,"unauthorized_count":len(presence)-authorized,"presence":presence,"history":rows[:200]}

    @app.get("/api/hardware/overview")
    async def hardware_overview():
        snap=hardware.snapshot()
        commands=db.hardware_commands(limit=100)
        all_devices=list(snap.get("devices",{}).values())
        online=sum(1 for x in all_devices if x.get("status") in ("CONNECTED","SIMULATION"))
        faults=sum(1 for x in all_devices if x.get("status") in ("FAULT","OFFLINE","DISCONNECTED") or x.get("fault"))
        active_alarms=sum(1 for x in snap.get("alarms",{}).values() if x.get("state")=="TRIGGERED")
        mode="SIMULATION" if s.hardware_simulation or not s.serial_enabled else "ATMEGA328P ONLINE"
        return {"state":snap,"commands":commands,"total":len(all_devices),"online":online,"faults":faults,"active_alarms":active_alarms,"mode":mode}

    @app.get("/api/hardware/topology")
    async def hardware_topology_get():
        return topology.snapshot()

    @app.put("/api/hardware/topology")
    async def hardware_topology_put(payload: dict = Body(...)):
        nonlocal topology, registry
        from iass.hardware_control.topology.models import Site, Building, Floor, Zone, Installation, Relationship
        new_topology = HardwareTopology(
            site=Site(**payload["site"]) if payload.get("site") else None,
            buildings=[Building(**x) for x in payload.get("buildings", [])],
            floors=[Floor(**x) for x in payload.get("floors", [])],
            zones=[Zone(**x) for x in payload.get("zones", [])],
            installations=[Installation(**x) for x in payload.get("installations", [])],
            relationships=[Relationship(**x) for x in payload.get("relationships", [])],
        )
        save_topology(ROOT / s.hardware_topology, new_topology)
        return {"ok": True, "topology": new_topology.snapshot(), "restart_required": True}

    @app.get("/api/settings")
    async def api_settings():
        return {
            "ai_enabled": state["ai"], "tracking_enabled": tracker.enabled,
            "camera_source": s.camera_source, "fps_limit": s.fps_limit,
            "recognition_threshold": s.recognition_threshold, "embedding_backend": s.ai_embedding_backend,
            "min_face_size": s.ai_min_face_size, "min_blur": s.ai_min_blur,
            "serial_enabled": s.serial_enabled, "serial_port": s.serial_port, "serial_baud": s.serial_baud,
            "hardware_simulation": s.hardware_simulation,
            "camera_mounts": list(s.hardware_camera_ids), "doors": list(s.hardware_door_ids), "alarms": list(s.hardware_alarm_ids),
            "database": str(s.database),
        }

    @app.get("/api/cameras")
    async def api_cameras():
        result = []
        for c in CAMERAS:
            st = camera_hubs.status(c["id"])
            has_worker = c["id"] in ai_workers
            result.append({**c, "state": "LIVE" if st["connected"] else ("WAITING" if has_worker else "OFFLINE"), "stream": f"/video.mjpg/{c['id']}"})
        return result

    @app.get("/api/state")
    async def api_state():
        with state["lock"]:
            detections = list(state["detections"])
            ai_status = state["ai_status"]
            ai_error = state["ai_error"]
            fps = state["fps"]
            activity = state["activity"]
        camera_status = camera_hubs.status(PRIMARY_CAMERA_ID)
        primary_mgr = camera_managers.get(PRIMARY_CAMERA_ID)
        if primary_mgr is None:
            cam_state = "LIVE" if camera_status["connected"] else "WAITING"
            primary_mgr_status = {"state": cam_state, "error": None}
        else:
            primary_mgr_status = primary_mgr.status()
            cam_state = primary_mgr_status["state"]
        camera_states = {}
        for c in CAMERAS:
            cs = camera_hubs.status(c["id"])
            has_worker = c["id"] in ai_workers
            camera_states[c["id"]] = {**c, **cs, "state": "LIVE" if cs["connected"] else ("WAITING" if has_worker else "OFFLINE"), "stream": f"/video.mjpg/{c['id']}"}
        return {
            "camera": {**camera_status, **primary_mgr_status, "state": cam_state, "id": PRIMARY_CAMERA_ID, "name": "Main Entrance"},
            "cameras": camera_states,
            "detections": detections,
            "tracking": tracker.enabled,
            "ai": state["ai"],
            "ai_status": ai_status if state["ai"] else "DISABLED",
            "ai_error": ai_error,
            "activity": activity,
            "fps": fps,
            "arduino": {"state": link.state, "error": link.error},
            "database": {"state": "READY"},
            "stepper": "TRACKING" if tracker.enabled and link.state == "CONNECTED" else "STANDBY",
            "alarm": "TRIGGERED" if any(a.get("state") == "TRIGGERED" for a in hardware_state.snapshot()["alarms"].values()) else "STANDBY",
            "hardware": hardware.snapshot(),
            "previews": list(state.get("previews", [])),
            "telemetry": {**host_telemetry(link, tracker), "hardware": hardware.snapshot()},
        }

    @app.get("/api/v1/hardware/devices")
    async def hardware_devices():
        return {"devices": registry.snapshot(), "state": hardware.snapshot()}

    @app.get("/api/v1/hardware/state")
    async def hardware_state_endpoint():
        return hardware.snapshot()

    @app.get("/api/v1/hardware/devices/{device_id}")
    async def hardware_device(device_id: str):
        value = hardware_state.device(device_id)
        if value is None:
            return JSONResponse({"ok": False, "error": "Hardware device not found"}, 404)
        return value

    @app.post("/api/v1/hardware/cameras/{camera_id}/move")
    async def hardware_camera_move(camera_id: str, request: CameraMoveRequest):
        result = hardware.rotate_camera(camera_id, request.pan, request.tilt, request.speed, correlation_id="API-MANUAL")
        return result.to_dict()

    @app.post("/api/v1/hardware/cameras/{camera_id}/track")
    async def hardware_camera_track(camera_id: str, request: CameraTrackRequest):
        result = hardware.track_camera(camera_id, request.x, request.y, request.frame_width, request.frame_height, correlation_id="API-MANUAL")
        return result.to_dict()

    @app.post("/api/v1/hardware/cameras/{camera_id}/stop")
    async def hardware_camera_stop(camera_id: str):
        return hardware.stop_camera(camera_id, correlation_id="API-MANUAL").to_dict()

    @app.post("/api/v1/hardware/cameras/{camera_id}/home")
    async def hardware_camera_home(camera_id: str):
        return hardware.home_camera(camera_id, correlation_id="API-MANUAL").to_dict()

    @app.post("/api/v1/hardware/doors/{door_id}/lock")
    async def hardware_door_lock(door_id: str, request: DoorRequest | None = Body(None)):
        request = request or DoorRequest()
        return hardware.lock_door(door_id, request.duration, request.reason, "API-MANUAL").to_dict()

    @app.post("/api/v1/hardware/doors/{door_id}/unlock")
    async def hardware_door_unlock(door_id: str, request: DoorRequest | None = Body(None)):
        request = request or DoorRequest(duration=5)
        return hardware.unlock_door(door_id, request.duration, request.reason, "API-MANUAL").to_dict()

    @app.get("/api/v1/hardware/doors/{door_id}")
    async def hardware_door_state(door_id: str):
        value = hardware_state.device(door_id)
        if value is None:
            return JSONResponse({"ok": False, "error": "Door not found"}, 404)
        return value

    @app.post("/api/v1/hardware/alarms/{alarm_id}/trigger")
    async def hardware_alarm_trigger(alarm_id: str, request: AlarmRequest | None = Body(None)):
        request = request or AlarmRequest()
        return hardware.trigger_alarm(alarm_id, request.mode, request.duration, request.reason, "API-MANUAL").to_dict()

    @app.post("/api/v1/hardware/alarms/{alarm_id}/clear")
    async def hardware_alarm_clear(alarm_id: str):
        return hardware.clear_alarm(alarm_id, "API-MANUAL", "API-MANUAL").to_dict()

    @app.get("/api/v1/hardware/alarms/{alarm_id}")
    async def hardware_alarm_state(alarm_id: str):
        value = hardware_state.device(alarm_id)
        if value is None:
            return JSONResponse({"ok": False, "error": "Alarm not found"}, 404)
        return value

    @app.post("/api/v1/hardware/devices/{device_id}/feedback")
    async def hardware_feedback(device_id: str, request: HardwareFeedbackRequest):
        try:
            return hardware.apply_feedback(device_id, request.state, request.details, request.correlation_id)
        except ValueError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, 404)

    @app.post("/api/v1/hardware/access/decide")
    async def hardware_access_decide(request: AccessRequest):
        return hardware.process_access_request(
            request.reader_id, request.door_id, request.identity, request.authorized,
            request.person_id, request.credential_ref, request.unlock_duration, "API-MANUAL"
        )

    @app.post("/api/v1/hardware/emergency-stop")
    async def hardware_emergency_stop():
        return hardware.emergency_stop("API-EMERGENCY-STOP")

    @app.get("/api/v1/hardware/commands")
    async def hardware_commands(limit: int = 100, device_id: str = ""):
        return db.hardware_commands(limit=limit, device_id=device_id or None)

    @app.get("/api/v1/hardware/events")
    async def hardware_events(limit: int = 100, device_id: str = ""):
        return db.hardware_events(limit=limit, device_id=device_id or None)

    @app.get("/api/people")
    async def people():
        return db.list_people()

    @app.post("/api/people/{person_id}/enabled")
    async def set_person_enabled(person_id: int, enabled: bool):
        if not db.get_person(person_id):
            return JSONResponse({"ok": False, "error": "Person not found"}, 404)
        db.set_person_enabled(person_id, enabled)
        return {"ok": True, "enabled": bool(enabled)}

    @app.get("/api/events")
    async def events(limit: int = 100, person: str = "", camera: str = "", authorization: str = "", search: str = ""):
        return db.events(limit=limit, person=person, camera=camera, authorization=authorization, search=search)

    @app.get("/api/events/recent")
    async def recent_events(limit: int = 8):
        return db.events(limit=limit)

    @app.post("/api/register")
    async def register(name: str = Form(...), identifier: str = Form(""), role: str = Form(""), access_level: str = Form("STANDARD"), image: UploadFile = File(...)):
        raw = await image.read()
        arr = np.frombuffer(raw, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return JSONResponse({"ok": False, "error": "invalid image"}, 400)
        face = ai.extract_face(frame)
        if face is None:
            return JSONResponse({"ok": False, "error": "No face detected in supplied image."}, 422)
        ok, encoded = cv2.imencode(".jpg", face)
        if not ok:
            return JSONResponse({"ok": False, "error": "could not encode image"}, 400)
        pid = db.add_person(name.strip(), identifier.strip(), role.strip(), access_level.strip())
        db.add_sample(pid, encoded.tobytes())
        for p in ai_pipelines.values():
            p.refresh_enrollment()
        return {"ok": True, "person_id": pid, "face_detected": True}

    @app.post("/api/register/live")
    async def register_live(name: str = Form(...), identifier: str = Form(""), role: str = Form(""), access_level: str = Form("STANDARD"), camera_id: str = Form(PRIMARY_CAMERA_ID)):
        frame = camera_hubs.frame(camera_id)
        if frame is None:
            return JSONResponse({"ok": False, "error": "No live camera frame is available. Start the phone camera first."}, 409)
        camera_ai = ai_pipelines.get(camera_id, ai)
        face = camera_ai.extract_face(frame)
        if face is None:
            return JSONResponse({"ok": False, "error": "No face detected in the current camera frame. Align the face with the registration guide and try again."}, 422)
        ok, encoded = cv2.imencode(".jpg", face, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            return JSONResponse({"ok": False, "error": "Could not encode captured face."}, 500)
        clean_name = name.strip()
        if not clean_name:
            return JSONResponse({"ok": False, "error": "Name is required."}, 422)
        pid = db.add_person(clean_name, identifier.strip(), role.strip(), access_level.strip())
        db.add_sample(pid, encoded.tobytes())
        for p in ai_pipelines.values():
            p.refresh_enrollment()
        # Persist the enrollment snapshot separately from recognition events.
        person_dir = snapshot_root / "enrollment"
        person_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        cv2.imwrite(str(person_dir / f"person_{pid}_{stamp}.jpg"), face, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        return {"ok": True, "person_id": pid, "face_detected": True}

    @app.post("/api/tracking")
    async def tracking(enabled: bool):
        tracker.set_enabled(enabled)
        state["tracking"] = tracker.enabled
        return {"tracking": tracker.enabled}

    @app.post("/api/ai")
    async def ai_toggle(enabled: bool):
        state["ai"] = bool(enabled)
        with state["lock"]:
            state["ai_status"] = "READY" if state["ai"] else "DISABLED"
        return {"ai": state["ai"]}

    @app.get("/video.mjpg")
    async def video_default():
        return await video_camera("CAM-01")

    @app.get("/video.mjpg/{camera_id}")
    async def video_camera(camera_id: str):
        if camera_id not in {c["id"] for c in CAMERAS}:
            return JSONResponse({"error": "Unknown camera"}, status_code=404)
        async def gen():
            while True:
                j = camera_hubs.jpeg(camera_id)
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(j)).encode() + b"\r\n\r\n" + j + b"\r\n"
                await asyncio.sleep(1 / max(1, s.fps_limit))
        return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.websocket("/ws/camera")
    async def ws_camera(ws: WebSocket):
        camera_id = ws.query_params.get("camera_id", PRIMARY_CAMERA_ID)
        if camera_id not in {c["id"] for c in CAMERAS}:
            await ws.close(code=1008, reason="Unknown camera_id")
            return
        await ws.accept()
        mgr = camera_managers.get(camera_id)
        if mgr is not None:
            mgr.mark_phone_connected()
        try:
            while True:
                data = await ws.receive_bytes()
                arr = np.frombuffer(data, np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is None:
                    continue
                camera_hubs.publish(camera_id, frame, "phone_browser")
                if camera_id == PRIMARY_CAMERA_ID:
                    now = time.time()
                    with state["lock"]:
                        state["frames"] += 1
                        if state["last_frame_ts"]:
                            dt = now - state["last_frame_ts"]
                            if dt > 0:
                                state["fps"] = round(1.0 / dt, 1)
                        state["last_frame_ts"] = now
                if state["ai"]:
                    worker = ai_workers.get(camera_id)
                    if worker is not None:
                        worker.submit(frame)
        except Exception:
            pass
        finally:
            camera_hubs.clear(camera_id, "phone_browser")
            if mgr is not None:
                mgr.mark_phone_disconnected()

    return app
