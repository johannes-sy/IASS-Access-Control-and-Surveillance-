# AI / Security / Hardware Integration

## End-to-end responsibility

**AI perception**
- detects faces/people
- evaluates image quality
- tracks targets
- estimates movement
- produces identity hypotheses
- emits semantic perception events

**Security scenario engine**
- decides whether an identified person is allowed in a zone
- maintains suspicious dwell/risk escalation
- decides when access or alarm scenarios should start
- creates semantic `HardwareIntent`

**Hardware controller**
- maps semantic intents to registered camera/door/alarm devices
- applies device limits and safety policy
- records commanded/actual state
- communicates through the existing ATmega driver

**ATmega328P**
- performs deterministic actuator work, protocol validation, timing, watchdog and firmware failsafe
- does not perform face recognition, identity authorization, zone policy, suspicious-activity analysis, or multi-camera decisions

## Important behavior

An unknown face is not automatically an alarm. The configured zone policy can require a dwell period before escalation.

An identified person is not automatically "authorized" by the AI. The scenario engine checks the enrolled person's enabled state and configured access level.

Camera tracking can occur immediately from a valid perception event without waiting for an access decision.

Repeated AI frames do not create repeated unlock/alarm commands because scenario transitions are tied to persistent tracks and event types.

The existing mock hardware path remains available so the full pipeline can be tested without an ATmega connected.
