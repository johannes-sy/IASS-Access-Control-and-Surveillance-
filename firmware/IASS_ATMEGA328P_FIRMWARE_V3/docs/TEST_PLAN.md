# Firmware V3 Verification Plan

V3 has two tiers of verification: an automated native test suite that runs
on any machine (no MCU needed) and covers the protocol/dispatch/handler
logic directly, and a bench procedure for the parts that only exist on real
hardware (timing, GPIO levels, watchdog reset).

## 1. Build (AVR)

```
make clean && make all
```

Confirm: zero warnings under `-Wall -Wextra -Wshadow -Wconversion`, and
check `avr-size build/iass_atmega328p.elf` stays comfortably under budget
(V3 baseline: ~7.8KB flash / 23.7% of 32KB, ~744B RAM / 36% of 2KB).

## 2. Automated native tests (no MCU required)

```
cd tests/native && make run
```

This links the real `protocol/frame.c`, `protocol/command_dispatch.c`,
every `handlers/*.c`, `actuators/door_lock.c`, `actuators/alarm.c`,
`system/state.c`, and `system/state_watch.c` against test-only mocks for
UART/GPIO/timer/servo (see `tests/native/README.md`), and exercises them
with real byte streams through the real `frame_send()`/`frame_poll()`
functions -- not hand-verified byte tables. Currently covers:

- CRC16 frame round-trip and corrupted-CRC rejection (with fault counting)
- `CMD_UNLOCK` with duration, and auto-relock after that duration elapses
- `CMD_ALARM_TRIGGER` strobe-only (the exact frame `REPEAT_VISIT_DETECTED`
  sends) hits alarm_2 without touching alarm_1
- stale-command (TTL) rejection
- duplicate-transaction rejection
- unsupported command handling
- `CMD_SERVO_SET` dispatch
- `state_watch_poll` emitting `MSG_EVENT` on a door-state change
- `CMD_EMERGENCY_STOP` (`FLAG_PRIORITY_EMERGENCY`) jumping the inbound queue
  ahead of three already-buffered frames
- `CMD_IDENTIFY` capability bitmask and device counts

Run this after any change to `protocol/`, `handlers/`, or the
`door_lock.c`/`alarm.c` actuators, before ever touching real hardware.

## 3. Bench procedure (requires the MCU)

### 3a. Malformed input handling
- Send a frame with a flipped CRC byte -- confirm no ACK/NACK is sent and
  `protocol_faults` in telemetry increments.
- Send a frame addressed to a device id other than `0x01`/`0xFF` -- confirm
  `ERR_BAD_DEVICE` NACK.
- Send a command id with no registered handler -- confirm `ERR_UNSUPPORTED`
  NACK.

### 3b. Camera mounts (repeat for servo ids 1, 2, 3)
- home (90 degrees), 0 degrees, 180 degrees, an intermediate angle, stop mid-travel
- confirm smooth movement (not an instant jump) at the bench
- invalid id, invalid angle (>180) both NACK with `ERR_BAD_PARAMETER`
- confirm `EVENT_SERVO_STATE` fires once travel completes, not once per
  degree

### 3c. Doors (repeat for door ids 1, 2)
- boot state is locked
- unlock with an explicit duration; confirm auto-relock at expiry
- lock immediately overrides a pending auto-relock timer
- invalid id NACKs
- `CMD_EMERGENCY_STOP` locks both regardless of individual state
- heartbeat loss (>5s) locks both and is reported via `EVENT_FAILSAFE`

### 3d. Alarms (this is your buzzer/LED bench test)
- `CMD_ALARM_TRIGGER` alarm_id=1 mode=SIREN -- confirm buzzer/D4 asserts
- `CMD_ALARM_TRIGGER` alarm_id=2 mode=STROBE -- confirm LED/D5 asserts
- `CMD_ALARM_TRIGGER` mode=SIREN_STROBE on either channel -- both assert
- timed activation auto-clears at duration expiry
- `CMD_ALARM_CLEAR` with id=0 clears both channels
- confirm the two channels are independent (triggering one never touches
  the other -- covered generically in the native suite; confirm physically
  here too)
- failsafe behavior: heartbeat loss silences alarm_1, asserts alarm_2
  (STROBE) regardless of what was active before

### 3e. Safety
- induce a watchdog reset (e.g. hold the main loop) -- confirm recovery and
  an `MSG_FAULT` (`FAULT_WATCHDOG_RESET`) on the next boot
- confirm startup state is safe (both doors locked, both alarms clear,
  servos homed) before any host command arrives

## 4. Host integration

With the IASS host running:

```text
AI/security scenario
    -> HardwareIntent
    -> HardwarePolicy action
    -> protocol command (transaction id, TTL)
    -> ATmega ACK/NACK
    -> actuator
    -> MSG_EVENT / MSG_TELEMETRY
    -> host state update
```

Do not declare an action physically confirmed from a successful
`serial.write()` alone -- wait for the ACK, and ideally the follow-up
`MSG_EVENT`, before the host records a state change as confirmed. See
`docs/HOST_INTEGRATION.md`.
