# IASS Wire Protocol V3

One protocol. No legacy fixed-frame fallback -- V2 shipped both a 7-byte
legacy frame and a fuller versioned frame side by side; V3 speaks only the
versioned frame below. See `docs/MIGRATION_V2_TO_V3.md` if you have a host
that only speaks the old 7-byte frame.

## Frame layout

```
AA | VERSION | SEQUENCE | DEVICE | COMMAND | FLAGS | LENGTH | PAYLOAD[0..LENGTH-1] | CRC16_H | CRC16_L | 55
```

- `AA` / `55` -- fixed start/end bytes.
- `VERSION` -- protocol version, currently `3`.
- `SEQUENCE` -- host-assigned, echoed back in the ACK/NACK/response. Not
  used for ordering (see meta below); useful for matching a response to a
  specific request when several are in flight.
- `DEVICE` -- `0x01` (the controller) or `0xFF` (broadcast).
- `COMMAND` -- see the command table below.
- `FLAGS` -- priority/behavior bits: `0x01` ACK_REQUIRED, `0x02` RETRYABLE,
  `0x04` PRIORITY_HIGH, `0x08` PRIORITY_SAFETY, `0x10` PRIORITY_EMERGENCY.
  A frame flagged PRIORITY_EMERGENCY jumps the inbound queue ahead of
  whatever's already buffered, evicting the oldest buffered frame if
  necessary rather than risking the emergency frame itself being dropped.
- `LENGTH` -- payload byte count (0..48).
- `CRC16` -- CRC-16/CCITT-FALSE over VERSION..PAYLOAD, computed the same way
  on both ends (`protocol/frame.c::frame_crc16`).

A frame with a bad CRC is silently dropped (not ACK'd) and counted in
`protocol_faults`, visible in telemetry -- it does not stall the parser or
crash the loop.

## Command meta block

Every command except `CMD_HEARTBEAT` carries a fixed 14-byte meta block at
the start of its payload, before any command-specific arguments:

```
[0..3]   transaction id   (u32) -- for duplicate rejection
[4..7]   correlation id   (u32) -- opaque, echoed back, yours to use for
                                    request/response matching on the host
[8..11]  issued_ms        (u32) -- MCU uptime (per this device's clock) at
                                    the moment the host issued the command
[12..13] ttl_ms           (u16) -- 0 = no expiry; otherwise the command is
                                    rejected with ERR_STALE_COMMAND once
                                    (now - issued_ms) > ttl_ms
```

`issued_ms` is this device's own uptime clock, not the host's clock or wall
time -- there's no clock sync between host and MCU. In practice this means:
read the MCU's current uptime from telemetry (or an IDENTIFY/STATE_REQUEST
round trip) before computing `issued_ms` for a TTL-bearing command, don't
just send the host's own timestamp.

A command with a transaction id that was already seen in roughly the last
10 seconds is rejected with `ERR_DUPLICATE` -- this catches a retransmit
after an ACK was lost in transit turning into a second physical actuation.

## Commands

| Command | ID | Args (after the 14-byte meta) | Domain handler |
|---|---:|---|---|
| `CMD_HEARTBEAT` | 0x01 | none (no meta block either) | `handlers/system_handlers.c` |
| `CMD_LOCK` | 0x10 | `[door_id:u8]` | `handlers/door_handlers.c` |
| `CMD_UNLOCK` | 0x11 | `[door_id:u8][duration_ms:u32 optional]` | `handlers/door_handlers.c` |
| `CMD_SERVO_SET` | 0x20 | `[servo_id:u8][angle:u8]` | `handlers/servo_handlers.c` |
| `CMD_SERVO_HOME` | 0x21 | none | `handlers/servo_handlers.c` |
| `CMD_SERVO_STOP` | 0x22 | `[servo_id:u8]` (0 = all) | `handlers/servo_handlers.c` |
| `CMD_ALARM_TRIGGER` | 0x32 | `[alarm_id:u8][mode:u8][duration_ms:u32 optional]` | `handlers/alarm_handlers.c` |
| `CMD_ALARM_CLEAR` | 0x41 | `[alarm_id:u8]` (0 = all) | `handlers/alarm_handlers.c` |
| `CMD_STATE_REQUEST` | 0x40 | none | `handlers/system_handlers.c` |
| `CMD_EMERGENCY_STOP` | 0x42 | none | `handlers/system_handlers.c` |
| `CMD_IDENTIFY` | 0x43 | none | `handlers/system_handlers.c` |

`alarm mode` is `alarm_mode_t`: `0=OFF (rejected -- use CMD_ALARM_CLEAR)`,
`1=STROBE` (alarm_2, your LED channel), `2=SIREN` (alarm_1, your buzzer
channel), `3=SIREN_STROBE` (both). One command covers every alarm channel
in every mode, rather than separate siren/strobe commands -- this is also
exactly what the host's `REPEAT_VISIT_DETECTED` scenario uses (alarm_2,
mode=STROBE, no siren) without needing a new command.

There is no command in this table for a scenario the host doesn't need yet
-- see `docs/COMMAND_ARCHITECTURE.md` for how a new one gets added without
touching the wire format or `main.c`.

## Responses

- `MSG_ACK` (0x02) / `MSG_NACK` (0x03) -- one per received command, echoing
  the request's command id, sequence, and (if present) the meta block's
  transaction/correlation ids. Payload: `[command][result][error_code][sequence][echoed meta, up to 8 bytes]`.
- `MSG_TELEMETRY` (0x04) -- periodic (every `TELEMETRY_PERIOD_MS`, default
  100ms) and also sent immediately in response to `CMD_STATE_REQUEST`.
  Payload: uptime(u32), failsafe_active(u8), 3x[angle,target,moving] for
  servos, 2x[commanded|actual|open bitfield] for doors, 2x[active|mode
  bitfield] for alarms, last_reset_reason(u8), protocol_faults(u8, capped
  at 255).
- `MSG_EVENT` (0x06) -- unsolicited, emitted the instant an actuator's
  observable state changes, whether that change was commanded or
  autonomous (auto-relock timeout, failsafe engaging/clearing). Don't rely
  on polling telemetry to notice a state change promptly -- subscribe to
  these instead. Subtypes: `EVENT_DOOR_STATE` (0x01) `[door_id][locked_commanded][door_open]`,
  `EVENT_ALARM_STATE` (0x02) `[alarm_id][active]`, `EVENT_SERVO_STATE`
  (0x03) `[servo_id][angle]` (emitted when a servo transitions from moving
  to stopped, not on every degree of travel), `EVENT_FAILSAFE` (0x04)
  `[engaged:0|1]` (flagged PRIORITY_HIGH).
- `MSG_FAULT` (0x07) -- unsolicited, currently emitted once at boot if the
  reset reason indicates a watchdog reset. Payload: `[fault_code][uptime_ms:u32]`.
- `MSG_IDENTIFY` (0x08) -- response to `CMD_IDENTIFY`. Payload: `'I' 'A'
  'S' 'S' version capabilities num_servos num_doors num_alarms`.
  `capabilities` is a bitmask (`CAP_SERVO`, `CAP_DOOR`, `CAP_ALARM`,
  `CAP_EVENTS`, `CAP_FAULT_REPORTING`, `CAP_PRIORITY_QUEUE`,
  `CAP_DUPLICATE_PROTECTION`, `CAP_TTL_EXPIRY`) so a host can detect what a
  connected firmware build actually supports instead of assuming.

## Error codes

`ERR_NONE`(0x00) `ERR_BAD_FRAME`(0x01) `ERR_BAD_CHECKSUM`(0x02)
`ERR_BAD_DEVICE`(0x03) `ERR_BAD_COMMAND`(0x04) `ERR_BAD_PARAMETER`(0x05)
`ERR_LIMIT`(0x06) `ERR_BUSY`(0x07) `ERR_TIMEOUT`(0x08) `ERR_FAULT`(0x09)
`ERR_STALE_COMMAND`(0x0A) `ERR_DUPLICATE`(0x0B) `ERR_UNSUPPORTED`(0x0C)
