#include "system_handlers.h"
#include "../protocol/command_dispatch.h"
#include "../protocol/frame.h"
#include "../include/config.h"
#include "../actuators/servo.h"
#include "../actuators/door_lock.h"
#include "../actuators/alarm.h"
#include "../system/state.h"

/* CMD_HEARTBEAT -- keeps the communication-loss failsafe from engaging.
 * Deliberately the one command that does not require meta: a host that has
 * just reconnected after a failsafe event needs heartbeat to work even
 * before any transaction/TTL bookkeeping is meaningful. */
static uint8_t handle_heartbeat(const frame_t *f, const command_meta_t *meta, uint8_t base, uint32_t now) {
    (void)f; (void)meta; (void)base;
    state_set_heartbeat(now);
    return ERR_NONE;
}

void system_send_telemetry(uint8_t sequence) {
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = sequence; f.device_id = DEVICE_CONTROLLER_ID;
    f.command = MSG_TELEMETRY; f.flags = 0u;
    uint32_t up = state_get()->uptime_ms;
    f.payload[f.length++] = (uint8_t)(up >> 24); f.payload[f.length++] = (uint8_t)(up >> 16);
    f.payload[f.length++] = (uint8_t)(up >> 8); f.payload[f.length++] = (uint8_t)up;
    f.payload[f.length++] = state_get()->failsafe_active;
    for (uint8_t i = 1u; i <= DEVICE_COUNT_SERVOS; ++i) {
        f.payload[f.length++] = servo_get_angle(i);
        f.payload[f.length++] = servo_get_target(i);
        f.payload[f.length++] = servo_is_moving(i);
    }
    for (uint8_t i = 1u; i <= DEVICE_COUNT_DOORS; ++i) {
        uint8_t x = 0u;
        if (door_is_locked_commanded(i)) x |= 1u;
        if (door_is_locked_actual(i)) x |= 2u;
        if (door_is_open(i)) x |= 4u;
        f.payload[f.length++] = x;
    }
    for (uint8_t i = 1u; i <= DEVICE_COUNT_ALARMS; ++i) {
        uint8_t x = alarm_is_active(i) ? 1u : 0u;
        x |= (uint8_t)(((uint8_t)alarm_get_mode(i) & 3u) << 1);
        f.payload[f.length++] = x;
    }
    f.payload[f.length++] = state_get()->last_reset_reason;
    uint16_t faults = frame_checksum_fault_count();
    f.payload[f.length++] = (faults > 0xFFu) ? 0xFFu : (uint8_t)faults;
    frame_send(&f);
}

static uint8_t handle_state_request(const frame_t *f, const command_meta_t *meta, uint8_t base, uint32_t now) {
    (void)meta; (void)base; (void)now;
    system_send_telemetry(f->sequence);
    return ERR_NONE;
}

static void send_identify(uint8_t sequence) {
    frame_t r = {0};
    r.version = PROTOCOL_VERSION; r.sequence = sequence; r.device_id = DEVICE_CONTROLLER_ID;
    r.command = MSG_IDENTIFY; r.flags = 0u; r.length = 9u;
    r.payload[0] = 'I'; r.payload[1] = 'A'; r.payload[2] = 'S'; r.payload[3] = 'S';
    r.payload[4] = PROTOCOL_VERSION;
    r.payload[5] = command_dispatch_capabilities();
    r.payload[6] = DEVICE_COUNT_SERVOS;
    r.payload[7] = DEVICE_COUNT_DOORS;
    r.payload[8] = DEVICE_COUNT_ALARMS;
    frame_send(&r);
}

static uint8_t handle_identify(const frame_t *f, const command_meta_t *meta, uint8_t base, uint32_t now) {
    (void)meta; (void)base; (void)now;
    send_identify(f->sequence);
    return ERR_NONE;
}

static uint8_t handle_emergency_stop(const frame_t *f, const command_meta_t *meta, uint8_t base, uint32_t now) {
    (void)f; (void)meta; (void)base;
    servo_stop_all();
    (void)door_lock_set(1u, true, 0u, now);
    (void)door_lock_set(2u, true, 0u, now);
    alarm_clear_all();
    return ERR_NONE;
}

void system_handlers_register(void) {
    command_dispatch_register(CMD_HEARTBEAT, 0u, 0u, handle_heartbeat);
    command_dispatch_register(CMD_STATE_REQUEST, 0u, 1u, handle_state_request);
    command_dispatch_register(CMD_IDENTIFY, 0u, 1u, handle_identify);
    command_dispatch_register(CMD_EMERGENCY_STOP, 0u, 1u, handle_emergency_stop);
}
