# Archive: nothing here was deleted, only set aside

Everything in this folder is a **verbatim copy** of code that used to live
in `src/iass/`. Before anything was moved here, I grepped the entire live
codebase (`app.py`, every module, every test) for references to each file.
Nothing in this archive is imported by anything in `src/iass/` anymore.

## `hardware_v1_old_layout/` -- the old `hardware/` package, in full

This is the exact old `hardware/` directory, kept whole for reference. Most
of its live contents were relocated into the new layered packages (see
`MIGRATION.md` at the project root for the full file-by-file map). What's
**only** in this archive now (never reachable from the live app, confirmed
by grep before moving):

- `system.py` -- an entire second orchestrator, never imported anywhere.
- `controllers/{camera,alarms,locks,telemetry}/` -- a parallel per-device
  controller scaffold, only ever imported by `system.py`.
- `control/{coordinator,camera,door,alarm,planner}.py` -- a second,
  more sophisticated implementation of "resolve an intent into concrete
  device commands" (zone-aware, with a formal `HardwareActionPlan`
  object). It duplicates what the live `policy.py` + `controller.py`
  already do end-to-end, but was never wired into `app.py`. I moved the
  `HardwareAction`/`HardwareActionPlan` dataclasses into the new
  `hardware_control/action_plan.py` since they're a genuinely nicer
  formal contract than raw tuples -- available for you to adopt later,
  not deleted.
- `api/hardware_api.py` (`HardwareAPI`) -- only used by `system.py`.
- `services/command_bus.py`, `services/manager.py` -- only used by
  `system.py`. (The *live* `services/transactions.py` and
  `services/events_bus.py` moved to `hardware_interface/services/`.)
- `transport/uart_transport.py` -- only used by `system.py`. (The live
  serial transport is `serial.py` -> now `hardware_interface/serial_link.py`.)
- `state/store.py` + `state/models.py` (`HardwareStateStore`) -- a second,
  simpler state store with its own `CameraState`/`LockState`/`AlarmState`
  dataclasses (different field names than the live ones), only used by
  `system.py`. The live state manager is `state/__init__.py`'s
  `HardwareStateManager` -> now `hardware_state/manager.py`.
- `scenarios/access_control.py` (`AccessControlScenario`) -- only used by
  `system.py`. The live scenario engine is `scenarios/security.py` -> now
  `decision_security/security_engine.py`.
- `mock/backend.py` -- not imported anywhere, live or dead.
- `hardware/state.py` (the *file*, not the package) -- this one's worth
  knowing about: Python silently prefers the `state/` *package* over the
  `state.py` *file* when both exist with the same name, so this file was
  **completely unreachable** even though it looks like normal code. Latent
  bug, now moot since it's archived.

**One exception -- rescued, not archived:** `safety/policy.py`
(`HardwareSafetyPolicy`: e-stop + heartbeat/comms-loss gate before any
unlock) looked dead by the same "never imported by `system.py`'s callers"
logic, but `tests/test_hardware_architecture.py` exercises it directly and
it's genuinely useful safety logic. I moved it to
`hardware_interface/safety.py` and kept its test passing. **It is not yet
wired into `HardwareController.unlock_door()`** -- right now the live
unlock path doesn't check e-stop or comms freshness before commanding a
physical unlock. Wiring it in is a real behavior change (it would start
refusing unlocks during an e-stop/comms-loss condition that currently
succeed), so I left that decision to you rather than silently changing
runtime behavior mid-refactor.

## `ai_v1_old_layout/`, `core_v1_old_layout/`

Straight copies of the old `ai/` and `core/` packages, kept only because
their *names* are now reused (`ai_perception/`, parts of `camera_stream/`
and `config/`). Every file in these two had a live equivalent that was
already migrated -- nothing unique was left behind here.

## `hardware_legacy/`

The whole top-level `hardware_legacy/` package from the original zip: a
near-duplicate of an older `hardware/` (missing the newer transaction/event
-bus code). It was never imported by anything, live or dead, in either zip
you sent me. Kept whole here in case you want to diff it for anything you
remember building that isn't in the current live implementation.

---

If you review this and want anything back in `src/iass/`, it's all here,
untouched, with git-diffable file names matching where they came from.
