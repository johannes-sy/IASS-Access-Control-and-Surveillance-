#include "servo_handlers.h"
#include "../protocol/command_dispatch.h"
#include "../protocol/payload.h"
#include "../include/config.h"
#include "../actuators/servo.h"

/* CMD_SERVO_SET args: [servo_id:u8][angle:u8] (host-side TRACK_CAMERA) */
static uint8_t handle_servo_set(const frame_t *f, const command_meta_t *meta, uint8_t base, uint32_t now) {
    (void)meta; (void)now;
    uint8_t id = 0u, angle = 0u;
    if (!payload_u8(f, base, &id) || !payload_u8(f, (uint8_t)(base + 1u), &angle)) return ERR_BAD_PARAMETER;
    return servo_set_target(id, angle) ? ERR_NONE : ERR_BAD_PARAMETER;
}

/* CMD_SERVO_STOP args: [servo_id:u8], 0 = all (host-side STOP_CAMERA) */
static uint8_t handle_servo_stop(const frame_t *f, const command_meta_t *meta, uint8_t base, uint32_t now) {
    (void)meta; (void)now;
    uint8_t id = 0u;
    if (!payload_u8(f, base, &id)) return ERR_BAD_PARAMETER;
    if (id == 0u) { servo_stop_all(); return ERR_NONE; }
    if (id > DEVICE_COUNT_SERVOS) return ERR_BAD_PARAMETER;
    servo_stop(id);
    return ERR_NONE;
}

static uint8_t handle_servo_home(const frame_t *f, const command_meta_t *meta, uint8_t base, uint32_t now) {
    (void)f; (void)meta; (void)base; (void)now;
    servo_home_all();
    return ERR_NONE;
}

void servo_handlers_register(void) {
    command_dispatch_register(CMD_SERVO_SET, 2u, 1u, handle_servo_set);
    command_dispatch_register(CMD_SERVO_STOP, 1u, 1u, handle_servo_stop);
    command_dispatch_register(CMD_SERVO_HOME, 0u, 1u, handle_servo_home);
}
