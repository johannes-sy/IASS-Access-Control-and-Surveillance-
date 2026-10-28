# Host Integration Contract

The IASS host owns all security decisions. The firmware is the
deterministic physical actuator endpoint -- see
`docs/COMMAND_ARCHITECTURE.md` for exactly how a host-side scenario turns
into a firmware command without firmware ever knowing *why*.

## Host responsibilities

The host decides:

- authorization and denial
- suspicious/high-risk/security-alert state, and repeat-visit detection
- multi-camera tracking and handoff
- door/access policy
- alarm escalation policy (including which alarm channel, which mode)
- command transaction/correlation IDs and TTL
- database/event logging

## Firmware responsibilities

The MCU performs:

- command envelope validation (meta, TTL expiry, duplicate rejection)
- command routing to the correct hardware domain handler
- physical actuator execution
- local actuator timing (auto door relock, smooth servo movement, alarm
  duration)
- heartbeat-loss failsafe
- watchdog recovery
- unsolicited state-change events and periodic telemetry
- ACK/NACK per command, with error codes

## Protocol

See `docs/PROTOCOL.md`. V3 speaks exactly one wire format -- there is no
legacy 7-byte fallback. If your host still only speaks that, see
`docs/MIGRATION_V2_TO_V3.md`.

## State synchronization

The host must never interpret a successful serial write as physical
confirmation. The lifecycle is:

```text
scenario decision
    -> HardwareIntent
    -> HardwarePolicy action (device_id, params)
    -> protocol command (transaction id, TTL)
    -> MCU ACK (accepted, or a specific ERR_* rejection)
    -> physical execution
    -> MSG_EVENT (state actually changed) and/or periodic MSG_TELEMETRY
    -> host state update
```

Subscribe to `MSG_EVENT`, don't just poll telemetry -- events fire the
instant an actuator's observable state changes, including autonomous
changes (auto-relock timeout, failsafe engaging) that a command ACK alone
would never tell you about.

For the current prototype, lock-position feedback is not installed. The MCU
therefore reports commanded lock state and door-position state separately
rather than claiming sensor-confirmed lock engagement -- see
`docs/HARDWARE_SAFETY.md`.

## Capability discovery

Send `CMD_IDENTIFY` before assuming what a connected firmware build
supports. The response carries a capability bitmask and live servo/door/
alarm counts -- see `docs/PROTOCOL.md`'s `MSG_IDENTIFY` section.
