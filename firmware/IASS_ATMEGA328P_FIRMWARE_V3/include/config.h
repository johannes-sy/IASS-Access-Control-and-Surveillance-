#ifndef IASS_CONFIG_H
#define IASS_CONFIG_H

/* AVR register/interrupt headers only exist under avr-gcc. Guarding this
 * (rather than requiring every consumer to know to skip it) is what lets
 * protocol/command_dispatch.c, handlers/ modules, actuators/alarm.c and
 * actuators/door_lock.c compile and be exercised under a normal host
 * compiler in tests/native/ -- real integration tests of the dispatch
 * logic, not just "it compiled for AVR". */
#ifdef __AVR__
#include <avr/io.h>
#endif
#include <stdint.h>

#define F_CPU 16000000UL
#define UART_BAUD 115200UL

/* Wire framing. V3 speaks exactly one protocol -- the versioned/CRC16
 * frame. There is no legacy fixed-frame fallback; see
 * docs/MIGRATION_V2_TO_V3.md if you are still running a host that only
 * speaks the old 7-byte frame. */
#define START_BYTE 0xAAu
#define END_BYTE   0x55u
#define PROTOCOL_VERSION 3u
#define DEVICE_CONTROLLER_ID 0x01u
#define BROADCAST_DEVICE_ID 0xFFu
#define FRAME_MAX_PAYLOAD 48u

#define SYSTEM_TICK_MS 1u
#define TELEMETRY_PERIOD_MS 100u
#define HEARTBEAT_TIMEOUT_MS 5000UL
#define DOOR_DEFAULT_UNLOCK_MS 5000UL
#define DOOR_OUTPUT_ACTIVE_HIGH_LOCKED 0
#define ALARM_OUTPUT_ACTIVE_HIGH 1
#define WATCHDOG_TIMEOUT_MS 2000UL

#define SERVO_HOME_DEG 90u
#define SERVO_MIN_DEG 0u
#define SERVO_MAX_DEG 180u
#define SERVO_STEP_MS 10u
#define SERVO_MAX_SPEED_DEG_PER_SEC 120u
#define SERVO_COMMAND_MIN_INTERVAL_MS 10u

/* Current physical prototype pin map.
 * Servo 1 = D10/PB2, Servo 2 = D3/PD3, Servo 3 = D11/PB3.
 * Door outputs = D8/PB0 and D9/PB1.
 * Alarm outputs = D4/PD4 and D5/PD5.
 */
#define SERVO1_DDR DDRB
#define SERVO1_PORT PORTB
#define SERVO1_PIN PB2
#define SERVO2_DDR DDRD
#define SERVO2_PORT PORTD
#define SERVO2_PIN PD3
#define SERVO3_DDR DDRB
#define SERVO3_PORT PORTB
#define SERVO3_PIN PB3

#define DOOR1_LOCK_DDR DDRB
#define DOOR1_LOCK_PORT PORTB
#define DOOR1_LOCK_PIN PB0
#define DOOR2_LOCK_DDR DDRB
#define DOOR2_LOCK_PORT PORTB
#define DOOR2_LOCK_PIN PB1

/* Optional future door-position sensors. Disabled on the current prototype
 * because D4/D5 are used by the two alarm outputs. */
#define IASS_ENABLE_DOOR_SENSORS 0
#define DOOR1_SENSOR_DDR DDRC
#define DOOR1_SENSOR_PORT PORTC
#define DOOR1_SENSOR_PIN PC0
#define DOOR2_SENSOR_DDR DDRC
#define DOOR2_SENSOR_PORT PORTC
#define DOOR2_SENSOR_PIN PC1

/* Optional local override inputs. Disabled by default on the current
 * prototype; enable only after wiring dedicated inputs. */
#define IASS_ENABLE_MANUAL_OVERRIDES 0
#define OVERRIDE_DDR DDRC
#define OVERRIDE_PORT PORTC
#define OVERRIDE_PINREG PINC
#define DOOR1_OVERRIDE_PIN PC2
#define DOOR2_OVERRIDE_PIN PC3

#define ALARM1_DDR DDRD
#define ALARM1_PORT PORTD
#define ALARM1_PIN PD4
#define ALARM2_DDR DDRD
#define ALARM2_PORT PORTD
#define ALARM2_PIN PD5

/* Command IDs. One flat set -- no legacy/rich duplication. ALARM_TRIGGER
 * takes an explicit (alarm_id, mode, duration) instead of separate
 * siren/strobe commands, so it covers both physical alarm channels in
 * every mode (SILENT/STROBE/SIREN/SIREN_STROBE) through one command
 * rather than two special-cased ones. */
#define CMD_HEARTBEAT       0x01u
#define CMD_LOCK             0x10u
#define CMD_UNLOCK           0x11u
#define CMD_SERVO_SET       0x20u
#define CMD_SERVO_HOME      0x21u
#define CMD_SERVO_STOP       0x22u
#define CMD_ALARM_TRIGGER   0x32u
#define CMD_ALARM_CLEAR      0x41u
#define CMD_STATE_REQUEST   0x40u
#define CMD_EMERGENCY_STOP  0x42u
#define CMD_IDENTIFY         0x43u

/* Message types. */
#define MSG_COMMAND        0x01u
#define MSG_ACK             0x02u
#define MSG_NACK            0x03u
#define MSG_TELEMETRY      0x04u
#define MSG_HEARTBEAT      0x05u
#define MSG_EVENT           0x06u
#define MSG_FAULT           0x07u
#define MSG_IDENTIFY        0x08u

/* Command flags. */
#define FLAG_ACK_REQUIRED 0x01u
#define FLAG_RETRYABLE    0x02u
#define FLAG_PRIORITY_HIGH 0x04u
#define FLAG_PRIORITY_SAFETY 0x08u
#define FLAG_PRIORITY_EMERGENCY 0x10u

/* Result/error codes. */
#define RESULT_OK 0u
#define RESULT_ERROR 1u
#define ERR_NONE            0x00u
#define ERR_BAD_FRAME       0x01u
#define ERR_BAD_CHECKSUM    0x02u
#define ERR_BAD_DEVICE      0x03u
#define ERR_BAD_COMMAND     0x04u
#define ERR_BAD_PARAMETER   0x05u
#define ERR_LIMIT           0x06u
#define ERR_BUSY            0x07u
#define ERR_TIMEOUT         0x08u
#define ERR_FAULT           0x09u
#define ERR_STALE_COMMAND   0x0Au
#define ERR_DUPLICATE       0x0Bu
#define ERR_UNSUPPORTED     0x0Cu

/* Fault codes, reported via an unsolicited MSG_FAULT frame and counted in
 * telemetry's protocol_faults field. */
#define FAULT_FRAME_CHECKSUM   0x01u
#define FAULT_WATCHDOG_RESET   0x02u

/* MSG_EVENT subtypes. Emitted by system/state_watch.c whenever an actuator's
 * observable state changes -- whether that change was commanded (a handler
 * just executed) or autonomous (auto-relock timeout, failsafe engaging).
 * One diffing mechanism covers both, instead of scattering event-emission
 * calls through every handler and every actuator tick function. */
#define EVENT_DOOR_STATE     0x01u
#define EVENT_ALARM_STATE    0x02u
#define EVENT_SERVO_STATE    0x03u
#define EVENT_FAILSAFE       0x04u

/* IDENTIFY capability bits. Lets the host detect what a connected firmware
 * build actually supports rather than assuming -- see
 * docs/COMMAND_ARCHITECTURE.md. */
#define CAP_SERVO                 0x01u
#define CAP_DOOR                  0x02u
#define CAP_ALARM                 0x04u
#define CAP_EVENTS                0x08u
#define CAP_FAULT_REPORTING       0x10u
#define CAP_PRIORITY_QUEUE        0x20u
#define CAP_DUPLICATE_PROTECTION  0x40u
#define CAP_TTL_EXPIRY            0x80u

#define DEVICE_COUNT_SERVOS 3u
#define DEVICE_COUNT_DOORS 2u
#define DEVICE_COUNT_ALARMS 2u

#endif
