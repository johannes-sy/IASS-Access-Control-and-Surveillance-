# IASS V1 Hardware Integration Testing

## 1. Software-only protocol test

Run:

```bash
PYTHONPATH=src pytest -q
```

The tests validate exact frame bytes, checksum rejection, fragmented input, telemetry bit decoding, semantic command mapping, and the simulation hardware path.

## 2. Prepare the host

In `config/v1.toml`:

```toml
[serial]
enabled = true
port = "/dev/ttyACM0"
baud = 115200

[hardware]
simulation = false
```

Make sure the Linux user can access the serial device. Do not use `sudo` to run IASS just to bypass serial permissions; add the user to the appropriate serial group if required.

## 3. Flash the supplied firmware

From the firmware project:

```bash
make
make flash PORT=/dev/ttyACM0
```

Verify the actual pin map against the schematic before connecting power to locks, sirens, strobes or other inductive loads.

## 4. Expected startup

Start IASS:

```bash
./start.sh
```

The hardware telemetry should eventually show:

```text
Arduino: CONNECTED
Failsafe: OFF
Door 1: LOCKED
Door 2: LOCKED
Siren: OFF
Strobe: OFF
```

The firmware emits telemetry every 100 ms and the host sends heartbeat frames approximately every second.

## 5. Safe functional tests

Use the hardware API or UI controls one action at a time.

### Door 1 lock

Send lock door 1. Expected:

```text
host → AA 01 10 00 01 checksum 55
MCU → telemetry with lock1 bit set
host state → DOOR_1 LOCKED
```

### Door 1 unlock

Send unlock door 1. Expected:

```text
host → AA 01 11 00 01 checksum 55
MCU → telemetry with lock1 bit cleared
host state → DOOR_1 UNLOCKED (or OPEN if sensor is active)
```

The firmware's own relock timer is five seconds. The host may also issue an earlier configured relock command.

### Servo

Move `camera_mount_1`. Expected physical mapping:

```text
camera_mount_1 → servo 0
camera_mount_2 → servo 1
camera_mount_3 → servo 2
```

The host uses 0° as the logical center and translates that to the firmware's 90° servo home.

### Alarm

Trigger `SIREN_STROBE`. Expected telemetry:

```text
siren = ON
strobe = ON
```

Clear the alarm and expect both outputs to become OFF.

## 6. Heartbeat/failsafe test

Start IASS with the ATmega connected. Verify normal telemetry. Then deliberately stop the host while keeping the MCU powered.

After approximately five seconds, the MCU should independently enter failsafe, lock both doors, home the servos, turn the siren off and activate the strobe according to the firmware implementation.

Restart IASS and verify heartbeat recovery clears the failsafe indication according to the firmware behavior.

## 7. Disconnect/reconnect test

With IASS running:

1. Disconnect the USB serial cable.
2. Confirm the host reports `DISCONNECTED` without crashing.
3. Reconnect the cable.
4. Confirm the background reconnect restores the serial link.
5. Confirm telemetry resumes and the state store updates.

## 8. Important limitation of firmware V1

The current ATmega firmware does not provide ACK/NACK, servo-position telemetry, or a separate tilt-axis command. The host must not claim those capabilities. The protocol layer is deliberately strict so future firmware can add them as a versioned protocol revision instead of silently changing V1 semantics.
