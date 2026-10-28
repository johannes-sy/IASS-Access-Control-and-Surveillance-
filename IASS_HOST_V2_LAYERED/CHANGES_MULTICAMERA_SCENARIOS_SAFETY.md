# Multi-camera fix, repeat-visitor scenario, safety wiring, hardware bench test

Verified: **31/31 tests pass**, app boots with all 53 routes, plus a live
instrumented run proving two cameras process AI concurrently (see below).

## 1. The actual multi-camera crash, root-caused and fixed

The reported bug ("can't stream two cameras, crashes") was a split-brain
design in `app.py`:

- A single global `FrameHub` existed, hardcoded to CAM-01 only.
- A separate `MultiCameraHub` existed and *did* accept frames for every
  camera -- but nothing ever read AI results from it. There was exactly
  one `AIWorker`/`Perception` instance, permanently bound to CAM-01.
- `AIPipeline` already had `camera_id`/`zone` constructor parameters
  (correctly per-instance), but `Perception.__init__` silently dropped
  them and always defaulted to `"CAM-01"`/`"MAIN_ENTRANCE"` -- so even a
  second `Perception` instance would have mislabeled all its events as
  coming from CAM-01.
- `CAMERAS` list entries had a `"source"` field that was **never read by
  any code** -- pure dead metadata suggesting someone started wiring
  per-camera sources and stopped.

Fixed:
- `Perception.__init__` now actually forwards `camera_id`/`zone` to
  `AIPipeline`.
- `app.py` now builds one `CameraManager` + `Perception` + `AIWorker` set
  per camera that has a real source (`opencv` or `synthetic`), and one
  `Perception` + `AIWorker` (no capture thread needed) per `phone_browser`
  camera. `CameraManager` gained an `on_frame` callback so opencv/synthetic
  captures actually feed their own AI worker, not just the stream hub.
- The standalone `hub`/`cam` globals are gone; `MultiCameraHub` is now the
  single source of truth for every camera.
- `record_detection()`, `register_live()`, and enrollment refresh no longer
  hardcode CAM-01/`CAMERAS[0]`.
- CAM-02 now defaults to a `synthetic` source (no physical hardware needed)
  specifically so two-camera concurrent operation is testable out of the
  box -- point any `CAM-0x` entry's `"source"` at `"opencv"` with a
  `"url"` (device index or RTSP URL) to drive a real second camera; nothing
  else needs to change.

**Verified, not just asserted**: I instrumented `Perception.process()` and
ran the app for real, pushing live frames into CAM-01 over its websocket
while CAM-02's synthetic loop ran independently in the background:
```
AI process() calls per camera (concurrent CAM-01 push + CAM-02 synthetic): {'CAM-02': 3, 'CAM-01': 1}
```
Both cameras processed independently, concurrently, with zero errors --
the exact scenario that used to crash.

`/api/state`'s existing top-level `detections`/`previews`/`activity`
fields still mirror CAM-01 specifically (`PRIMARY_CAMERA_ID`), so nothing
that reads them today breaks. New `detections_by_camera`,
`previews_by_camera`, `activity_by_camera` dicts carry the full per-camera
breakdown for anything that wants it.

## 2. Repeat-visitor scenario

New: `decision_security/security_engine.py` now counts, per
`(person_id, camera_id)`, how many separate times a **known, recognized**
identity has produced a brand-new track at that camera -- i.e. how many
times they've walked up to it, left, and come back. Once the count reaches
`repeat_visit_threshold` (default 3), it fires a `REPEAT_VISITOR` event and
resets the counter (so it fires again after another `threshold` visits,
rather than only once ever).

`hardware_control/policy.py` maps `REPEAT_VISITOR` to a `TRIGGER_ALARM`
action in `STROBE_ONLY` mode by default (an LED-style flag, not a siren) --
deliberately distinct from the `UNAUTHORIZED_PERSON`/security-escalation
alarm path, since a repeat visitor may well be authorized; this is a "flag
it" signal, not a "lock down" signal. It's **off by default**
(`alert_on_repeat_visitor = false` in `config/v1.toml`) since not every
deployment wants a physical indicator for this.

Deliberate design choice, not an oversight: **unrecognized/unknown faces
are never counted.** Without a confirmed identity there's no reliable way
to say "this is the same stranger as before" versus a different one --
counting them would be exactly the kind of false confidence this codebase
has avoided elsewhere (e.g. `HardwareResult`'s explicit commanded-vs-actual
state distinction). Covered by
`test_repeat_visitor_never_counts_unknown_faces`.

To test with your LED: wire it to an alarm output (`D4`/`D5` per your
firmware's `config.h`), set `alert_on_repeat_visitor = true` and
`repeat_visit_threshold` to something low like `2` in `config/v1.toml`,
and walk into frame, out, and back in front of an enrolled face.

## 3. HardwareSafetyPolicy -- now actually wired in

Previously rescued into `hardware_interface/safety.py` (real e-stop +
heartbeat/comms-loss gate, with test coverage) but never called from
anywhere. Now wired into `HardwareController`:
- `unlock_door()` and `trigger_alarm()` both check the safety policy before
  touching the driver, returning a new `result="SAFETY_BLOCKED"` outcome
  (distinct from `FAULT`/`DISCONNECTED`) if refused -- no partial
  side effects, nothing gets sent to the wire.
- `lock_door()` and `clear_alarm()` are deliberately **not** gated -- the
  "make safe" direction should never be blocked by the safety policy
  itself.
- Real firmware telemetry receipt now calls `safety.heartbeat()`, so
  comms-loss detection reflects actual link health instead of app-level
  assumptions. In simulation mode (`MockHardwareDriver`, no real serial
  link), no telemetry callback is ever registered, so the comms-loss check
  never triggers -- simulation behavior is unaffected.
- This **is** a real behavior change if you deploy against a real board:
  unlocking now refuses during an active e-stop or after 5+ seconds
  without a telemetry frame (configurable via
  `hardware_heartbeat_timeout`), where it previously would have proceeded.
  Covered end-to-end by `test_safety_policy_blocks_unlock_during_estop`
  (unlock succeeds -> e-stop trips -> unlock refused -> unauthorized clear
  correctly ignored -> authorized clear restores normal operation).
- All existing tests construct `HardwareController(...)` without a
  `safety=` argument, which defaults to `None` -- zero behavior change for
  every other test and for any code that doesn't opt in.

## 4. Standalone hardware bench-test tool

New: `tools/bench_test_hardware.py`. Talks directly to your board over the
real serial port using the exact same `ArduinoLink`/`Frame` classes the
full app uses -- no camera, no AI, no security engine, no simulation layer
in between. Walks your firmware's own `docs/TEST_PLAN.md` sections 2
(heartbeat), 4 (servo sweep on all 3 mounts, plus an invalid-id check that
correctly expects the *link* to reject it before transmitting), 5 (doors:
unlock, watch the firmware's own auto-relock timer fire, explicit lock,
plus an invalid-door-id check that -- unlike servos -- genuinely tests your
firmware's own validation, since the link layer doesn't check door ids),
and 6 (alarms: siren, strobe, both together, clear-alarm).

```bash
python tools/bench_test_hardware.py --port /dev/ttyACM0 --step
```

`--step` pauses after every command so you can actually look at your
buzzer/LED before the next one fires -- it does not auto-pass/fail the
alarm/servo/door steps, since the whole point is *you* confirming the
physical output matches. It does clean up on exit (locks both doors,
clears alarms, homes servos) even on Ctrl-C.

Not covered: firmware `TEST_PLAN.md` sections 3 (rich V2 protocol -- no
standalone client exists for it yet), 7 (safety/watchdog -- needs
deliberately killing the serial connection mid-session), and 8 (full host
integration -- needs the running app, not a bench tool).

## Known follow-ups, not attempted here

- The deeper camera-identity mismatch: `hardware_control`'s device registry
  uses its own camera IDs (`camera_mount_1/2/3`) which are **not** the same
  ID space as the video-stream `CAMERAS` list (`CAM-01`..`CAM-06`). This
  pre-dates this change and wasn't part of the reported crash, but it means
  "which video camera watches which physical mount" isn't explicit anywhere
  yet -- worth unifying if you want the two to line up 1:1.
- `repeat_visit_threshold` has no time-decay window -- a visit from a year
  ago counts the same as one from five minutes ago. Simple by design for
  now; add a window if stale visits shouldn't count.
