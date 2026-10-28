# IASS Hardware Protocol Contract

## Current firmware compatibility

The currently supplied ATmega328P V1 firmware accepts the seven-byte frame:

```text
START DEVICE COMMAND VALUE_H VALUE_L XOR END
AA    01     xx      xx      xx     xx  55
```

XOR covers device, command and both value bytes.

## Host semantic contract

`protocol/contract.py` defines the application contract independently of the wire:

- COMMAND / ACK / NACK / TELEMETRY / HEARTBEAT / FAULT / EVENT
- NORMAL / HIGH / SAFETY / EMERGENCY priority
- command ID and correlation ID
- expiry timestamp
- retryable flag
- lifecycle state
- explicit error classes

This separation is intentional. The current firmware can remain lightweight while
IASS gains a complete transaction/state model. A later firmware protocol revision can
serialize these metadata fields without changing the AI or scenario layers.

## No false ACKs

A successful `serial.write()` means only that bytes were accepted by the host serial
stack. It does **not** prove physical actuation. The state manager therefore keeps
commanded state and reported state separate.

## Device semantics

Supported semantic device families are camera mounts, door locks and alarms. Physical
pins, servo indexes and UART framing remain below the hardware driver boundary.
