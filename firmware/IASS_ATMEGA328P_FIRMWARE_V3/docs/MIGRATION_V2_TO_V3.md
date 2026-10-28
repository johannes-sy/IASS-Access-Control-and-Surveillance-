# Migrating from Firmware V2 to V3

V2 is archived nowhere in this repo (it's the version you already had) --
this documents what changed if you're moving a host that spoke V2's wire
format.

## The one breaking change: legacy protocol removed

V2 accepted two wire formats: a 7-byte legacy frame (`AA DEVICE COMMAND
VALUE_H VALUE_L XOR 55`) and a fuller versioned frame. V3 speaks **only**
the versioned frame (`docs/PROTOCOL.md`). If your host still builds the
7-byte frame, it will not be understood by V3 firmware -- you need the
matching host-side protocol client update (the IASS host's
`hardware_interface/protocol/` module) alongside this firmware update.

## Command ID changes

The old separate `CMD_SIREN` (0x30) / `CMD_STROBE` (0x31) commands are
gone. Both are now `CMD_ALARM_TRIGGER` (0x32) with an explicit
`(alarm_id, mode, duration)`:

| Old (V2 legacy) | New (V3) |
|---|---|
| `CMD_SIREN` value=1 | `CMD_ALARM_TRIGGER` alarm_id=1, mode=SIREN |
| `CMD_SIREN` value=0 | `CMD_ALARM_CLEAR` alarm_id=1 |
| `CMD_STROBE` value=1 | `CMD_ALARM_TRIGGER` alarm_id=2, mode=STROBE |
| `CMD_STROBE` value=0 | `CMD_ALARM_CLEAR` alarm_id=2 |

Every other command id is unchanged in value (`CMD_LOCK=0x10`,
`CMD_UNLOCK=0x11`, `CMD_SERVO_SET=0x20`, `CMD_SERVO_HOME=0x21`,
`CMD_ALARM_CLEAR=0x41`, `CMD_STATE_REQUEST=0x40`,
`CMD_EMERGENCY_STOP=0x42`, `CMD_IDENTIFY=0x43`); one new command was added,
`CMD_SERVO_STOP=0x22`, to stop a specific mount (or all, id=0) without
re-homing it.

## Every command now requires the 14-byte meta block

V2's rich path already supported this optionally; V3 requires it for every
command except `CMD_HEARTBEAT`. See `docs/PROTOCOL.md`'s meta block
section.

## IDENTIFY response payload grew

V2: `'I' 'A' 'S' 'S' version 0x00 0x00 0x3F` (8 bytes, capability byte
unused/hardcoded).
V3: `'I' 'A' 'S' 'S' version capabilities num_servos num_doors num_alarms`
(9 bytes, capability bitmask is real and device counts are live).

## New: unsolicited MSG_EVENT and MSG_FAULT

V2 only reported state via periodic telemetry. V3 additionally emits
`MSG_EVENT` the instant an actuator's state changes (commanded or
autonomous) and `MSG_FAULT` on a watchdog-reset boot. Neither requires host
changes to keep working (they're new message types the host can simply
ignore if unhandled), but you should subscribe to `MSG_EVENT` for prompt
state confirmation instead of relying on the 100ms telemetry poll.

## Build system fix

V2's `Makefile` was missing the project root from the include path
(`INCLUDES := -Iinclude`), which meant any source file outside the project
root that quote-included a header from another subdirectory (e.g.
`drivers/timer.c` including `"actuators/servo.h"`) failed to compile. V3's
Makefile fixes this (`INCLUDES := -Iinclude -I.`) -- confirmed by actually
building both with a real `avr-gcc` toolchain, not just inspecting the
Makefile.

## Internal-only changes (no host impact)

- `main.c` no longer contains command-handling logic at all -- it's a thin
  init-and-loop shell. See `docs/COMMAND_ARCHITECTURE.md`.
- `system_state_t.uptime_ms` is now actually updated every loop iteration.
  In V2 it was declared, initialized to 0, and never written again --
  telemetry's uptime field and any uptime-based logic were silently always
  reading 0. Fixed in `system/state.c` (`state_set_uptime`), called from
  `main.c`'s loop.
- `protocol_faults` in telemetry is now a real, live counter (incremented
  on every CRC-rejected frame in `protocol/frame.c`) instead of a field
  that existed but was never incremented.
