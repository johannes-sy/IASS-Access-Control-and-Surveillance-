# Architecture migration: V1 -> layered

Verified state after this migration: **28/28 existing tests pass, the full
FastAPI app boots with all 53 routes**, using only the reorganized code.
Nothing was deleted -- everything either moved to a new home or sits in
`_archive/` with a README explaining exactly why.

## The layer map, matching your flow exactly

```
camera_stream/      "here's a frame, from CAM-3 (USB) or a phone on the hotspot"
      |
      v  raw frame
vision_core/         (shared OpenCV primitives -- see below)
      |
      v
ai_perception/       "Person 42 is being tracked by Camera 3"
      |
      v  PerceptionEvent
decision_security/    "Person 42 is authorized"
      |
      v  HardwareIntent
hardware_control/    "Camera 3 is configured to cover Door 3.
                       Door 3 is therefore the relevant physical access point."
      |
      v  (action, device_id, params)
hardware_interface/  "Send unlock command to the ATmega channel assigned to Door 3."
      |
      v  wire frame
   [ATmega]           actuates physical output
      |
      v  telemetry frame
hardware_interface/  "Door 3 actuator acknowledged." (HardwareResult / audit)
      |
      v
hardware_state/      "Door 3 = UNLOCKED"
```

Each arrow is a real Python contract, not a convention:

| From -> To | Type | Defined in |
|---|---|---|
| camera_stream -> ai_perception | `numpy.ndarray` frame | -- |
| ai_perception -> decision_security | perception event (`.track_id`, `.camera_id`, `.zone`, `.identity`, `.bbox`, ...) | `ai_perception/events.py`, `ai_perception/models.py` |
| decision_security -> hardware_control | `HardwareIntent` | `decision_security/intents.py` |
| hardware_control -> hardware_interface | `(action, device_id, params)` via `HardwarePolicy.actions_for_intent()`, or the formal `HardwareActionPlan`/`HardwareAction` objects in `hardware_control/action_plan.py` | `hardware_control/policy.py`, `hardware_control/action_plan.py` |
| hardware_interface -> hardware_state | telemetry `Frame` -> state mutation | `hardware_interface/controller.py:_on_hardware_frame`, `hardware_state/manager.py` |
| hardware_interface -> caller | `HardwareResult` | `hardware_interface/models.py` |

Each layer's `__init__.py` now states its input/output contract in its
docstring -- open any of them and the boundary is the first thing you read.

## Where OpenCV core lives

You asked specifically where "OpenCV core" belongs. It's `vision_core/`:
low-level, dependency-only-on-cv2-and-numpy primitives with no business
logic, used by both `camera_stream` (JPEG encoding for the MJPEG stream)
and `ai_perception` (bbox IoU math for the tracker). Previously
`cv2.imencode` was called ad hoc in `framehub.py` and a hand-rolled `iou()`
was duplicated in `tracker.py`; both now call the shared implementation in
`vision_core/codec.py` and `vision_core/geometry.py`.

## Full file-by-file move map

### camera_stream/ (from core/)
- `core/camera.py` -> `camera_stream/capture.py` (`CameraManager`)
- `core/framehub.py` -> `camera_stream/framehub.py` (`FrameHub`) -- now uses `vision_core.codec`
- `core/multicamera.py` -> `camera_stream/multi.py` (`MultiCameraHub`)

### vision_core/ (new -- extracted, not moved)
- `vision_core/codec.py` -- `encode_jpeg`/`decode_jpeg`, factored out of `framehub.py`
- `vision_core/geometry.py` -- `iou`/`center`, factored out of `ai/tracker.py`

### ai_perception/ (from ai/, structure unchanged internally)
- `ai/detector.py`, `embedder.py`, `quality.py`, `matcher.py`, `tracker.py`,
  `camera_association.py`, `models.py`, `events.py`, `pipeline.py`,
  `perception.py` -> same filenames under `ai_perception/`
  (this is the layer already upgraded to YOLOv11-ONNX detection in the
  previous change -- see `CHANGES_AI_UPGRADE.md`)

### decision_security/ (from hardware/scenarios/)
- `hardware/scenarios/security.py` -> `decision_security/security_engine.py` (`SecurityScenarioEngine`)
- `hardware/scenarios/risk.py` -> `decision_security/risk.py` (`RiskLevel`)
- `HardwareIntent` (was in `hardware/models.py`) -> `decision_security/intents.py`

### hardware_control/ (from hardware/policy.py, registry.py, topology/, control/, core/tracking.py)
- `hardware/policy.py` -> `hardware_control/policy.py` (`HardwarePolicy` -- resolves an intent's zone into concrete devices)
- `hardware/registry.py` -> `hardware_control/device_registry.py` (`DeviceRegistry`, `DeviceDefinition`)
- `hardware/topology/*` -> `hardware_control/topology/*` (site/building/floor/zone model + JSON loader)
- `hardware/control/planner.py` -> `hardware_control/action_plan.py` (`HardwareAction`/`HardwareActionPlan` -- rescued from the dead `control/` subsystem, see `_archive/README.md`)
- `core/tracking.py` -> `hardware_control/camera_tracking.py` (`TrackerController` -- turns an AI target position into a camera pan/tilt command)

### hardware_interface/ (from hardware/controller.py, drivers.py, serial.py, commands.py, interface/, protocol/, services/, events.py, safety/policy.py)
- `hardware/controller.py` -> `hardware_interface/controller.py` (`HardwareController` -- the only thing that actually calls `driver.command(...)`)
- `hardware/drivers.py` -> `hardware_interface/drivers.py`
- `hardware/serial.py` -> `hardware_interface/serial_link.py` (`ArduinoLink`)
- `hardware/commands.py` -> `hardware_interface/commands.py`
- `hardware/interface/{api,atmega,simulated}.py` -> `hardware_interface/backends/{base,atmega,simulated}.py`
- `hardware/protocol/*` -> `hardware_interface/protocol/*` (wire frame format)
- `hardware/services/{transactions,events_bus}.py` -> `hardware_interface/services/*`
- `hardware/events.py` -> `hardware_interface/audit.py` (`HardwareAudit`)
- `hardware/safety/policy.py` -> `hardware_interface/safety.py` (`HardwareSafetyPolicy` -- **rescued from the dead subsystem, has real test coverage, not yet wired into `controller.unlock_door()` -- see `_archive/README.md` for what that means**)
- Enums + `HardwareResult` (was in `hardware/models.py`) -> `hardware_interface/models.py`

### hardware_state/ (from hardware/state/)
- `hardware/state/__init__.py` -> `hardware_state/manager.py` (`HardwareStateManager`)
- State record dataclasses (was in `hardware/models.py`) -> `hardware_state/models.py`

### config/ (from core/config.py)
- `core/config.py` -> `config/settings.py` (`Settings`, `load_settings`)

### Archived (see `_archive/README.md` for the full reasoning per file)
- `hardware_legacy/` -- whole unused legacy package from the original zip
- `hardware/system.py` + everything only *it* referenced (`controllers/`,
  `control/{coordinator,camera,door,alarm}.py` logic path, `api/hardware_api.py`,
  `services/{command_bus,manager}.py`, `transport/uart_transport.py`,
  `state/store.py`+`state/models.py`, `scenarios/access_control.py`, `mock/`)
- `hardware/state.py` (the file) -- silently shadowed by the `state/`
  package and therefore **completely unreachable** even in the original
  code; a real latent bug, now moot.
- The old `hardware/`, `ai/`, `core/` directories themselves, kept whole
  for reference/diffing.
- Five orphaned UI pages (`dashboard.html`, `logs.html`, `personnel.html`,
  `register.html`, `telemetry.html`) and their dedicated JS/CSS -- an
  earlier multi-page UI fully superseded by the `app.html` single-page-app
  shell, never deleted. See `src/iass/ui/README.md`.
- Two more orphaned copies of an even earlier dashboard (`app.js`/`app.css`
  directly under `static/`, plus a second unused `static/js/app.js`).

## Packaging fix

There was no `pyproject.toml`, so `PYTHONPATH=src` was required for
anything to import `iass` at all -- part of why the codebase felt
untraceable. Added `pyproject.toml` with proper package discovery and
`pytest` configuration; `pytest` now works with no environment setup, and
`pip install -e .` will work for real development.

## What I did not touch

- `db/` -- already a single, clean module; left as-is.
- `api/app.py` itself -- only its import block and one inline import were
  changed to point at the new layer packages. The endpoint logic inside is
  unchanged. It's still one large file wiring everything together; splitting
  it into per-concern routers (camera routes, hardware routes, security
  routes, personnel routes) is a reasonable next step but a separate piece
  of work from the module reorganization you asked for here.
- `app_shell.js` -- works, dense, not split into per-view files. See
  `src/iass/ui/README.md` for the suggested follow-up.
- `HardwareSafetyPolicy` wiring -- moved into the live tree but not called
  from `controller.unlock_door()`, since doing so changes runtime behavior
  (see above). Your call whether to wire it in.
