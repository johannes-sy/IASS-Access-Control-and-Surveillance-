# IASS ATmega328P Hardware Actuator Firmware V3

Bare-metal ATmega328P firmware for the IASS hardware-control subsystem.

## Design boundary

The ATmega is intentionally a **lightweight deterministic actuator
endpoint**. Security scenarios stay in the IASS host -- this firmware does
not perform face recognition, authorization, suspicious-activity analysis,
multi-camera decisions, or security policy. It receives semantic physical
commands, validates them, actuates hardware, enforces local timing/safety
constraints, and reports physical state. See
`docs/COMMAND_ARCHITECTURE.md` for exactly how a command gets from "the
host's security engine decided X" to "a relay clicked", and why firmware
never needs to know *why*.

## What's new in V3

- **One wire protocol**, not two. V2 spoke both a 7-byte legacy frame and a
  richer versioned frame; V3 speaks only the versioned frame
  (`docs/PROTOCOL.md`). See `docs/MIGRATION_V2_TO_V3.md` if you're updating
  a host that only speaks the old frame.
- **A real command-dispatch layer** (`protocol/command_dispatch.c` +
  `handlers/*.c`) replaces a hand-written switch statement in `main.c`.
  Meta validation (TTL, duplicate rejection), routing, and per-domain
  handlers are cleanly separated -- adding a command the host might start
  sending later never means editing `main.c`. `docs/COMMAND_ARCHITECTURE.md`
  is the full writeup.
- **Unsolicited state-change events** (`MSG_EVENT`) fire the instant an
  actuator's observable state changes -- commanded or autonomous (auto-
  relock, failsafe engaging) -- instead of the host only finding out from
  the next periodic telemetry frame.
- **Capability negotiation.** `CMD_IDENTIFY` now reports a real capability
  bitmask and live servo/door/alarm counts, so a host can detect what a
  connected firmware build actually supports.
- **Emergency-stop priority.** A `FLAG_PRIORITY_EMERGENCY` frame jumps the
  inbound command queue, evicting the oldest buffered frame if necessary --
  it is never the frame that gets dropped under load.
- **Fixed a real build bug.** V2's Makefile was missing the project root
  from the include path, breaking any source file outside the root that
  included a header from another subdirectory. Confirmed fixed by actually
  building with `avr-gcc`, not just reading the Makefile.
- **Fixed a real state bug.** `system_state_t.uptime_ms` was declared,
  initialized to 0, and never written again anywhere in V2 -- telemetry's
  uptime field was silently always 0. Now updated every loop iteration.
- **A native (x86) integration test suite** (`tests/native/`) exercises the
  real protocol/dispatch/handler/actuator logic with a normal host
  compiler, no MCU required -- see `docs/TEST_PLAN.md`.

## Current prototype hardware

| Logical device | Current prototype pin |
|---|---|
| camera_mount_1 | D10 / PB2 |
| camera_mount_2 | D3 / PD3 |
| camera_mount_3 | D11 / PB3 |
| door_1 actuator | D8 / PB0 |
| door_2 actuator | D9 / PB1 |
| alarm_1 (siren) | D4 / PD4 |
| alarm_2 (strobe) | D5 / PD5 |
| UART RX / TX | D0 / D1 |

Door-position sensors and manual overrides are retained as optional future
interfaces (`IASS_ENABLE_DOOR_SENSORS`, `IASS_ENABLE_MANUAL_OVERRIDES` in
`include/config.h`) and disabled by default because the current prototype
uses those pins for the alarm outputs. Door output polarity defaults to
**HIGH = unlocked**; see `DOOR_OUTPUT_ACTIVE_HIGH_LOCKED` before wiring a
real relay/strike driver.

## Physical safety

Never drive a real solenoid, electric strike, siren, or other high-current
load directly from an ATmega GPIO. Use an appropriate transistor/MOSFET/
relay driver, flyback protection where required, isolated inputs where
required, and an independent power path. See `docs/HARDWARE_SAFETY.md`.

## Build

```bash
make clean && make all && make size
```

Artifacts: `build/iass_atmega328p.elf`, `build/iass_atmega328p.hex`.

```bash
make flash PORT=/dev/ttyUSB0
```

## Test

```bash
cd tests/native && make run   # protocol/dispatch/handler logic, no MCU needed
```

See `docs/TEST_PLAN.md` for the full verification plan, including the
bench procedure for hardware-dependent behavior.

## Architecture

```text
UART
  |
protocol/frame.c            (bytes in/out, CRC16, priority-aware queue)
  |
protocol/command_dispatch.c (meta validation, TTL, duplicates, routing)
  |
handlers/*_handlers.c       (one file per hardware domain)
  |
actuators/*.c                (pure hardware, unaware of protocol/commands)
  |
system/state_watch.c        (diffs actuator state -> unsolicited events)

Safety services run independently: watchdog, heartbeat failsafe,
command TTL, duplicate protection, emergency-stop queue priority.
```

Full explanation, and how this stays flexible as the host's scenario set
evolves: `docs/COMMAND_ARCHITECTURE.md`.

## Documentation index

- `docs/PROTOCOL.md` -- wire format, commands, responses, error codes
- `docs/COMMAND_ARCHITECTURE.md` -- the dispatch/handler layer, why it's
  shaped this way, how to extend it
- `docs/HOST_INTEGRATION.md` -- the host/firmware responsibility boundary
- `docs/HARDWARE_SAFETY.md` -- watchdog, failsafe, command expiry, servo
  limits, door state caveats
- `docs/REGISTER_MAP.md` -- logical device ids and current pin mapping
- `docs/TEST_PLAN.md` -- automated + bench verification
- `docs/BUILD_AND_FLASH.md` -- toolchain setup, build, flash
- `docs/MIGRATION_V2_TO_V3.md` -- what changed if you're updating a V2 host
- `docs/CHANGELOG.md` -- version history
