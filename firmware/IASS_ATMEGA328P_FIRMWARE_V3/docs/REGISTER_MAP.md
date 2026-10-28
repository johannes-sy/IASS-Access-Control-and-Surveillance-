# IASS Logical Device Map

The frame-level device address is always the ATmega controller (`0x01`) or
broadcast (`0xFF`). Individual physical devices are identified inside
command payloads by a small integer id, listed below.

| Logical device | ID | Current prototype pin | Handler module |
|---|---:|---|---|
| Controller | 0x01 | ATmega328P | -- |
| camera_mount_1 (servo) | 1 | D10 / PB2 | `handlers/servo_handlers.c` |
| camera_mount_2 (servo) | 2 | D3 / PD3 | `handlers/servo_handlers.c` |
| camera_mount_3 (servo) | 3 | D11 / PB3 | `handlers/servo_handlers.c` |
| door_1 | 1 | D8 / PB0 | `handlers/door_handlers.c` |
| door_2 | 2 | D9 / PB1 | `handlers/door_handlers.c` |
| alarm_1 (siren / your buzzer) | 1 | D4 / PD4 | `handlers/alarm_handlers.c` |
| alarm_2 (strobe / your LED) | 2 | D5 / PD5 | `handlers/alarm_handlers.c` |

These counts (`DEVICE_COUNT_SERVOS=3`, `DEVICE_COUNT_DOORS=2`,
`DEVICE_COUNT_ALARMS=2` in `include/config.h`) are also what `CMD_IDENTIFY`
reports live, so the host doesn't have to hardcode them independently of
what firmware actually has.

The application should address devices by these logical id numbers, per
device type -- pin numbers are firmware configuration detail, changeable in
`include/config.h` without affecting the wire protocol or the host at all.
