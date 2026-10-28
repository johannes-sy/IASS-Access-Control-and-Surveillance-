#include "state_watch.h"
#include "state.h"
#include "../include/config.h"
#include "../protocol/frame.h"
#include "../actuators/servo.h"
#include "../actuators/door_lock.h"
#include "../actuators/alarm.h"

static uint8_t last_door_commanded[DEVICE_COUNT_DOORS];
static uint8_t last_door_open[DEVICE_COUNT_DOORS];
static uint8_t last_alarm_active[DEVICE_COUNT_ALARMS];
static alarm_mode_t last_alarm_mode[DEVICE_COUNT_ALARMS];
static uint8_t last_servo_moving[DEVICE_COUNT_SERVOS];
static uint8_t last_failsafe;
static uint8_t sequence;

static void emit_door(uint8_t id) {
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = sequence++; f.device_id = DEVICE_CONTROLLER_ID;
    f.command = MSG_EVENT; f.flags = 0u; f.length = 4u;
    f.payload[0] = EVENT_DOOR_STATE; f.payload[1] = id;
    f.payload[2] = door_is_locked_commanded(id) ? 1u : 0u;
    f.payload[3] = door_is_open(id) ? 1u : 0u;
    frame_send(&f);
}

static void emit_alarm(uint8_t id) {
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = sequence++; f.device_id = DEVICE_CONTROLLER_ID;
    f.command = MSG_EVENT; f.flags = 0u; f.length = 3u;
    f.payload[0] = EVENT_ALARM_STATE; f.payload[1] = id;
    f.payload[2] = alarm_is_active(id) ? 1u : 0u;
    frame_send(&f);
}

static void emit_servo(uint8_t id) {
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = sequence++; f.device_id = DEVICE_CONTROLLER_ID;
    f.command = MSG_EVENT; f.flags = 0u; f.length = 3u;
    f.payload[0] = EVENT_SERVO_STATE; f.payload[1] = id;
    f.payload[2] = servo_get_angle(id);
    frame_send(&f);
}

static void emit_failsafe(uint8_t engaged) {
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = sequence++; f.device_id = DEVICE_CONTROLLER_ID;
    f.command = MSG_EVENT; f.flags = FLAG_PRIORITY_HIGH; f.length = 2u;
    f.payload[0] = EVENT_FAILSAFE; f.payload[1] = engaged;
    frame_send(&f);
}

void state_watch_init(void) {
    sequence = 0u;
    for (uint8_t i = 0u; i < DEVICE_COUNT_DOORS; ++i) {
        last_door_commanded[i] = door_is_locked_commanded((uint8_t)(i + 1u)) ? 1u : 0u;
        last_door_open[i] = door_is_open((uint8_t)(i + 1u)) ? 1u : 0u;
    }
    for (uint8_t i = 0u; i < DEVICE_COUNT_ALARMS; ++i) {
        last_alarm_active[i] = alarm_is_active((uint8_t)(i + 1u)) ? 1u : 0u;
        last_alarm_mode[i] = alarm_get_mode((uint8_t)(i + 1u));
    }
    for (uint8_t i = 0u; i < DEVICE_COUNT_SERVOS; ++i)
        last_servo_moving[i] = servo_is_moving((uint8_t)(i + 1u));
    last_failsafe = state_get()->failsafe_active;
}

void state_watch_poll(uint32_t now) {
    (void)now;
    for (uint8_t i = 0u; i < DEVICE_COUNT_DOORS; ++i) {
        uint8_t id = (uint8_t)(i + 1u);
        uint8_t commanded = door_is_locked_commanded(id) ? 1u : 0u;
        uint8_t open = door_is_open(id) ? 1u : 0u;
        if (commanded != last_door_commanded[i] || open != last_door_open[i]) {
            last_door_commanded[i] = commanded; last_door_open[i] = open;
            emit_door(id);
        }
    }
    for (uint8_t i = 0u; i < DEVICE_COUNT_ALARMS; ++i) {
        uint8_t id = (uint8_t)(i + 1u);
        uint8_t active = alarm_is_active(id) ? 1u : 0u;
        alarm_mode_t mode = alarm_get_mode(id);
        if (active != last_alarm_active[i] || mode != last_alarm_mode[i]) {
            last_alarm_active[i] = active; last_alarm_mode[i] = mode;
            emit_alarm(id);
        }
    }
    for (uint8_t i = 0u; i < DEVICE_COUNT_SERVOS; ++i) {
        uint8_t id = (uint8_t)(i + 1u);
        uint8_t moving = servo_is_moving(id);
        /* A servo transitioning from moving to stopped is the useful
         * signal (it just reached its commanded angle); we don't emit on
         * every degree of travel, only on that transition. */
        if (moving != last_servo_moving[i]) {
            last_servo_moving[i] = moving;
            if (!moving) emit_servo(id);
        }
    }
    uint8_t failsafe = state_get()->failsafe_active;
    if (failsafe != last_failsafe) {
        last_failsafe = failsafe;
        emit_failsafe(failsafe);
    }
}
