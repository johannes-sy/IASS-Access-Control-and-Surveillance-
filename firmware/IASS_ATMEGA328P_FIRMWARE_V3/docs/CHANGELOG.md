# Firmware Changelog

## 3.0.0

### Removed
- The legacy 7-byte fixed frame protocol. V3 speaks exactly one wire
  format. See `docs/MIGRATION_V2_TO_V3.md`.
- `CMD_SIREN` / `CMD_STROBE` as separate commands -- both channels and
  every mode now go through `CMD_ALARM_TRIGGER(alarm_id, mode, duration)`.

### Added
- `protocol/command_dispatch.c`: a real command-dispatch layer (table of
  command id -> handler, with generic meta/TTL/duplicate validation)
  replacing a hand-written switch statement in `main.c`.
- `handlers/{system,servo,door,alarm}_handlers.c`: one file per hardware
  domain, each command mapped to exactly one handler function.
- `system/state_watch.c`: polls actuator state every loop iteration and
  emits unsolicited `MSG_EVENT` frames on any change -- commanded or
  autonomous (auto-relock, failsafe engaging/clearing) -- instead of
  requiring the host to infer state changes from periodic telemetry alone.
- `MSG_FAULT`, emitted at boot when the reset reason indicates a watchdog
  reset.
- Live `protocol_faults` counting: every CRC-rejected frame now increments
  a real counter surfaced in telemetry (previously declared, always 0).
- `CMD_SERVO_STOP`: stop a specific mount (or all, id=0) without re-homing.
- Capability bitmask + live device counts (`num_servos`, `num_doors`,
  `num_alarms`) in the `CMD_IDENTIFY` response.
- Emergency-stop queue priority: a `FLAG_PRIORITY_EMERGENCY` frame jumps
  the inbound queue, evicting the oldest buffered frame if full, so it is
  never itself the frame dropped under load.
- `tests/native/`: an x86 integration test suite exercising the real
  protocol/dispatch/handler/actuator logic against test-only driver mocks,
  runnable with a normal host compiler.
- `docs/COMMAND_ARCHITECTURE.md`: the full writeup of the dispatch/handler
  layering and how it stays decoupled from (and flexible to) the host's
  evolving scenario set.

### Fixed
- Makefile was missing the project root from the include path
  (`INCLUDES := -Iinclude`), breaking any source file outside the root
  that quote-included a header from another subdirectory. Confirmed fixed
  with a real `avr-gcc` build, not just Makefile inspection.
- `system_state_t.uptime_ms` was declared, initialized to 0, and never
  written again anywhere -- telemetry's uptime field was silently always
  0. Now updated every loop iteration via `state_set_uptime()`.
- Removed `include/pinmap.h`, an unused dead file not included anywhere.

### Unchanged (by design)
- Physical device inventory: 3 servos, 2 doors, 2 alarm channels.
- Watchdog (~2s) and heartbeat failsafe (5s) behavior.
- Door commanded/actual/open state separation; optional sensor/override
  interfaces (disabled by default, same reason as V2 -- current pins are
  occupied by alarm outputs).
- Servo smooth-movement scheduler and 0-180 degree bound.

## 2.0.0

- Corrected the physical prototype pin mapping to the current IASS test wiring.
- Preserved compatibility with the existing IASS seven-byte host protocol.
- Added an extensible versioned protocol with CRC16.
- Added message types for command, ACK, NACK, telemetry, heartbeat, event, fault and identify.
- Added rich transaction/correlation metadata.
- Added rich command TTL validation.
- Added bounded duplicate transaction protection.
- Added rich state telemetry.
- Added semantic emergency-stop command.
- Kept security/scenario decisions out of firmware.
- Kept watchdog and communication-loss failsafe local to the MCU.
- Kept door commanded state separate from physical sensor state.
- Made door/alarm electrical polarity configurable.
- Kept optional door sensors/manual overrides without consuming the current prototype alarm pins.
- Added a bounded inbound frame queue instead of a single pending frame.
- Kept 100 ms legacy telemetry for the current host.
