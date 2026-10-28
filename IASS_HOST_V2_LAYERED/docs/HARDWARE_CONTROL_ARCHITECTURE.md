# IASS Host Hardware Control Architecture

## Responsibility boundary

**AI/perception** reports facts: detections, identities, tracks, positions and confidence.

**Security scenario engine** decides what those facts mean: authorization, observation,
suspicion, high risk, security alert, restricted access, tailgating and camera handoff.

**Hardware controller** converts semantic decisions into bounded physical actions and
maintains commanded state versus latest reported state.

**Driver/transport** is the only layer that knows the ATmega serial protocol.

**ATmega firmware** remains the deterministic actuator/safety endpoint. It does not
recognize people or decide security scenarios.

## Command lifecycle

Every host command has a command ID and correlation ID even though the current V1
firmware cannot carry them on-wire. The host records:

`CREATED -> SENT -> CONFIRMED | FAILED | EXPIRED | UNKNOWN`

A physical write is **not** treated as firmware ACK. Simulation can confirm immediately;
real hardware is confirmed only when telemetry/ACK evidence exists.

## Current V1 wire compatibility

The supplied ATmega firmware currently uses:

`AA | DEVICE | COMMAND | VALUE_H | VALUE_L | XOR | 55`

The host preserves this wire format in `protocol/frame.py` while `protocol/contract.py`
defines the richer future-proof semantic contract: message type, priority, sequence,
expiry, retryability, lifecycle and error classes.

## Scenario flow

- Authorized person: track -> policy authorization -> unlock configured door -> auto relock -> audit.
- Unauthorized person: track -> keep doors locked -> observation -> configurable escalation.
- Suspicious dwell: risk transition -> notification/event -> optional alarm.
- High risk: lock -> optional alarm escalation.
- Security alert: lock all relevant doors -> alarm escalation -> critical event.
- Camera handoff: preserve a known person/explicit re-identification key across camera IDs.
- Target lost: stop the mount while preserving the security history.
- Tailgating: compound access observation can trigger a security alert without asking firmware to infer it.
- Hardware offline/fault: state becomes disconnected/fault and no false physical confirmation is reported.

## Real-time protections

- tracking deadband
- proportional pan control
- angular limits
- command cadence limiting
- duplicate suppression
- command expiry metadata
- correlation IDs
- thread-safe hardware state
- reconnect/heartbeat transport
- simulation driver with the same semantic API

## Hardware replacement strategy

The application uses `camera_mount`, `door_lock`, and `alarm` abstractions. Prototype
LEDs/buzzers are therefore replaceable with real lock/siren/strobe drivers without
changing security scenarios.
