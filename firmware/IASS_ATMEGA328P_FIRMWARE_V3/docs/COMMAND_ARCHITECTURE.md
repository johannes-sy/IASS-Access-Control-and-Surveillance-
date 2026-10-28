# How the software and firmware stay coupled without being welded together

This is the question that mattered most: the software side already decides
*what* should happen (a scenario fires, a `HardwareIntent` is produced, a
`(action, device_id, params)` tuple comes out of `HardwarePolicy`) --
firmware just has to *do* it, correctly, without needing a rewrite every
time the scenario side invents something new. Here's the actual mechanism,
and why it's built this way rather than a big `switch` in `main.c`.

## The layers, and what each one is allowed to know

```
                                    SOFTWARE SIDE (host)
  ┌─────────────────────────────────────────────────────────────────┐
  │ AI perception  ->  decision_security scenarios  ->  HardwareIntent│
  │        (this box is the ONLY place "why" lives)                  │
  └──────────────────────────────┬──────────────────────────────────┘
                                  │ HardwarePolicy.actions_for_intent()
                                  │ turns intent -> (action, device_id, params)
                                  v
  ┌─────────────────────────────────────────────────────────────────┐
  │ hardware_interface: encodes (action, device_id, params) as a     │
  │ protocol command frame (transaction id, TTL, CRC16, etc)         │
  └──────────────────────────────┬──────────────────────────────────┘
                                  │  UART, protocol/PROTOCOL.md
════════════════════════════════ │ ═══════════════════════════════════
                                  v
                                    FIRMWARE SIDE (this repo)
  ┌─────────────────────────────────────────────────────────────────┐
  │ protocol/frame.c        -- bytes in, bytes out. Knows nothing    │
  │                            about what a command MEANS.           │
  ├─────────────────────────────────────────────────────────────────┤
  │ protocol/command_dispatch.c -- THE LAYER YOU ASKED FOR. Validates│
  │                            meta/TTL/duplicates once, generically,│
  │                            looks up a handler in a table. Knows  │
  │                            THAT commands exist and how they're   │
  │                            shaped, not WHY any of them fire.     │
  ├─────────────────────────────────────────────────────────────────┤
  │ handlers/*_handlers.c   -- one file per hardware domain. Each    │
  │                            command maps to exactly one function. │
  │                            Knows how to turn "unlock door 1 for  │
  │                            5000ms" into a call to door_lock_set. │
  ├─────────────────────────────────────────────────────────────────┤
  │ actuators/*.c           -- pure hardware. door_lock.c doesn't    │
  │                            know it's being driven by a command   │
  │                            at all -- it just tracks lock state   │
  │                            and timing. This layer is UNCHANGED   │
  │                            by anything above it.                 │
  └─────────────────────────────────────────────────────────────────┘
```

Your instinct was right: raw commands hitting actuators directly (no
middle layer) is fragile -- it means every new thing the software side
wants to do requires editing the same `main.c` switch statement,
increasing the odds of one change breaking an unrelated command. Equally
right: firmware still must not know about *scenarios* (why a door is
unlocking). The fix isn't "no layer", it's "a layer that understands
*commands*, not *decisions*."

This is the same shape as a REST API's router + controllers, or a Linux
driver's ioctl table, or ROS2's service dispatch -- in every one of those,
there's a generic dispatch layer (parses the envelope, matches a route/opcode
to a handler) and then isolated per-resource handler code, and the
transport layer at the bottom never knows what a route means. That's
exactly `command_dispatch.c` + `handlers/`.

## Why this makes the *software* side more flexible too, not just tidier firmware

Because `HardwarePolicy.actions_for_intent()` already emits `(action,
device_id, params)` tuples decoupled from any specific scenario, and
because firmware's command surface is a flat, self-describing table
(`command_dispatch_register()` calls) rather than an implicit switch, three
things become true:

1. **A new scenario needs zero firmware changes** if it reuses an existing
   action (`TRIGGER_ALARM`, `UNLOCK_DOOR`, `TRACK_CAMERA`, ...) -- which is
   the common case. `REPEAT_VISIT_DETECTED` (see the host's
   `decision_security/security_engine.py`) is a real example: it's a new
   *scenario*, but it emits a `TRIGGER_ALARM` action like everything else,
   so firmware needed exactly zero changes to support it.
2. **A genuinely new physical capability** (a new command the wire format
   doesn't have yet) means: one new handler function in the matching
   `handlers/*.c` file, one `command_dispatch_register()` call, done.
   `main.c` does not change. `protocol/frame.c` does not change. No other
   handler is at risk of being broken by the change, because handlers don't
   call each other or share mutable state beyond the actuator modules
   they're explicitly wrapping.
3. **The host can ask the firmware what it supports** before assuming.
   `CMD_IDENTIFY`'s response now carries a capability bitmask and live
   device counts (`num_servos`, `num_doors`, `num_alarms`) generated from
   the same constants the handlers were built against
   (`DEVICE_COUNT_SERVOS` etc in `include/config.h`) -- so a host talking to
   an older or differently-configured firmware build can detect a mismatch
   instead of silently assuming capability that isn't there.

## Why command handling isn't just "apply immediately"

Three things happen in `command_dispatch.c` before a handler ever runs, and
they exist specifically because "just apply the command" is the wrong
model for a security system talking over a lossy serial link:

- **Staleness (TTL) rejection.** A command queued behind a UART hiccup and
  delivered 4 seconds late should not fire -- the scenario that issued it
  may no longer be true. `command_dispatch.c` rejects it with
  `ERR_STALE_COMMAND` before any handler sees it.
- **Duplicate rejection.** If the host retries after losing an ACK, the
  physical actuator should not fire twice. A small bounded
  recent-transaction cache catches this generically, once, instead of
  every handler needing its own idempotency logic.
- **Priority preemption.** An `EMERGENCY_STOP` frame doesn't wait in line
  behind a burst of routine servo-tracking commands -- it jumps the queue,
  evicting the oldest buffered frame if there's no room, because a
  safety-critical command is the one thing that must never itself be the
  one dropped under load.

None of that is scenario knowledge. It's what "handle a command
responsibly" means at the protocol level, independent of what the command
is *for* -- which is exactly the boundary you described wanting.

## Extending this later

Adding a new command the host might start sending:

1. Pick a free `CMD_*` id in `include/config.h`.
2. Write one handler function in the right `handlers/<domain>_handlers.c`
   (or a new domain file, if it's a genuinely new hardware type) matching
   the `command_handler_fn` signature.
3. Register it: one `command_dispatch_register(CMD_X, min_args, requires_meta, handle_x)`
   call in that file's `_register()` function.
4. Document it in `docs/PROTOCOL.md`'s command table.

`main.c`, `frame.c`, and every *other* handler are untouched. That's the
whole point of the layer.
