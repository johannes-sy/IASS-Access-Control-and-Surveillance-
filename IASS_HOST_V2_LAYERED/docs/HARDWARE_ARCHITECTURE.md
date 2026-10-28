# IASS Hardware Layer — Professional Architecture

This refactor is **additive**. Existing IASS software and legacy hardware modules are
preserved under `src/iass/hardware/` and a byte-for-byte backup is kept under
`src/iass/hardware_legacy/`.

## Layers

1. `transport/` — UART lifecycle and raw bytes.
2. `protocol/` — framing, checksum, device/command definitions.
3. `services/` — command bus and hardware lifecycle/reconnect/heartbeat.
4. `controllers/` — task-oriented camera, lock, alarm, telemetry APIs.
5. `safety/` — host-side authorization, heartbeat and E-stop policy.
6. `scenarios/` — business workflows such as authorized entry and intrusion response.
7. `state/` — typed hardware state used by telemetry/API/UI.
8. `api/` — application-facing facade; web routes should not touch UART directly.
9. `mock/` — explicit unavailable-hardware backend for development.

## Safety boundary

The host layer is not the final safety authority. The ATmega firmware must still
enforce watchdog, communication-loss, lock and actuator failsafe behavior.

## Integration rule

Do not import serial code from FastAPI routes, AI perception, or UI code. Those
subsystems call the hardware API/controller layer. This keeps the software side
replaceable and testable.
