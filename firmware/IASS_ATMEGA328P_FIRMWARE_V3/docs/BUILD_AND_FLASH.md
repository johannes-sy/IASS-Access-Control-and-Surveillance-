# Build and Flash

## Ubuntu/Debian prerequisites

Install the AVR toolchain and avrdude using your distribution's package manager.

Then verify:

```bash
avr-gcc --version
avrdude -?
```

## Build

```bash
make clean
make all
make size
```

## Flash

For a USB-UART bootloader:

```bash
make flash PORT=/dev/ttyUSB0
```

If the programmer/port differs, override:

```bash
make flash PORT=/dev/ttyACM0 PROGRAMMER=arduino
```

The exact bootloader baud and programmer settings must match the installed bootloader/programmer.

## Production verification

After flashing, connect the host and verify:

1. IDENTIFY response;
2. heartbeat ACK;
3. 100 ms telemetry;
4. servo movement;
5. door lock command;
6. timed door unlock/relock;
7. alarm trigger/clear;
8. communication-loss failsafe;
9. watchdog recovery;
10. manual override.
