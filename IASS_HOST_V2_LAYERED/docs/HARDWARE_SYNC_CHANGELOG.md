# IASS Host Hardware Synchronization Changelog

## Scope

This revision changes the **Python host hardware layer only**. The supplied ATmega328P firmware remains the authoritative V1 wire-protocol implementation and was not modified.

## Fixed

- Replaced the incompatible variable-length/versioned host frame with the firmware's exact 7-byte frame.
- Centralized firmware command IDs and telemetry bit definitions.
- Added strict incremental frame parsing with checksum and framing validation.
- Removed active use of the old ASCII `IASS,...` serial protocol.
- Added a dedicated serial RX worker for continuous telemetry reception.
- Added automatic serial reconnect handling without crashing IASS.
- Added an independent host heartbeat service so the MCU's five-second failsafe can operate as designed.
- Added telemetry decoding for failsafe, siren, strobe, lock state, and door sensors.
- Connected decoded telemetry to the existing semantic hardware state manager.
- Changed physical command results to distinguish `COMMAND_SENT` from confirmed physical state.
- Mapped the three logical camera mounts to firmware servo channels 0, 1, and 2.
- Converted the host logical camera-center convention to the firmware's 90° servo home.
- Explicitly reject physical tilt commands because the current firmware exposes no independent tilt command.
- Preserved the existing semantic HardwareController/API and simulation driver.
- Preserved existing application/UI/database/AI modules.
- Kept the persistent virtual-environment startup behavior; dependencies are installed only on first run or when `requirements.txt` changes.

## Deliberately not added to V1

The firmware currently has no ACK/NACK, sequence numbers, CRC-16, servo-position telemetry, or independent tilt-axis protocol. The host does not invent these features. They should be introduced as an explicit future protocol revision on both sides.

## Verification

- Host test suite: **19 passed**.
- FastAPI application import: passed.
- FastAPI startup/shutdown test with simulated hardware: passed.
- Exact firmware frame serialization test: passed.
- Firmware compilation was not executed in this environment because `avr-gcc` is not installed; the firmware source was left unchanged.
