#ifndef IASS_SYSTEM_TYPES_H
#define IASS_SYSTEM_TYPES_H
#include <stdint.h>
#include <stdbool.h>

typedef enum { DEVICE_DISCONNECTED = 0, DEVICE_CONNECTED, DEVICE_FAULT } device_status_t;
typedef enum { ALARM_OFF = 0, ALARM_STROBE = 1, ALARM_SIREN = 2, ALARM_SIREN_STROBE = 3 } alarm_mode_t;

typedef struct {
    uint8_t angle;
    uint8_t target_angle;
    uint8_t min_angle;
    uint8_t max_angle;
    uint8_t moving;
    uint8_t fault;
} servo_state_t;

typedef struct {
    uint8_t locked_commanded;
    uint8_t locked_actual;
    uint8_t door_open;
    uint8_t fault;
    uint32_t unlock_deadline_ms;
} door_state_t;

typedef struct {
    uint8_t active;
    alarm_mode_t mode;
    uint32_t deadline_ms;
    uint8_t fault;
} alarm_state_t;

typedef struct {
    servo_state_t servos[3];
    door_state_t doors[2];
    alarm_state_t alarms[2];
    uint32_t uptime_ms;
    uint32_t last_heartbeat_ms;
    uint8_t failsafe_active;
    uint8_t last_reset_reason;
    uint8_t protocol_faults;
} system_state_t;

#endif
