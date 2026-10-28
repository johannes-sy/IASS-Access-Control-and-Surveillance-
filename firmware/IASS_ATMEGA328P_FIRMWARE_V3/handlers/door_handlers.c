#include "door_handlers.h"
#include "../protocol/command_dispatch.h"
#include "../protocol/payload.h"
#include "../include/config.h"
#include "../actuators/door_lock.h"

/* CMD_LOCK args: [door_id:u8] (host-side LOCK_DOOR) */
static uint8_t handle_lock(const frame_t *f, const command_meta_t *meta, uint8_t base, uint32_t now) {
    (void)meta;
    uint8_t id = 0u;
    if (!payload_u8(f, base, &id)) return ERR_BAD_PARAMETER;
    return door_lock_set(id, true, 0u, now) ? ERR_NONE : ERR_BAD_PARAMETER;
}

/* CMD_UNLOCK args: [door_id:u8][duration_ms:u32 optional] (host-side
 * UNLOCK_DOOR, which HardwarePolicy always issues with an explicit
 * duration -- the optional-arg fallback exists for direct bench testing). */
static uint8_t handle_unlock(const frame_t *f, const command_meta_t *meta, uint8_t base, uint32_t now) {
    (void)meta;
    uint8_t id = 0u;
    uint32_t duration = 0u;
    if (!payload_u8(f, base, &id)) return ERR_BAD_PARAMETER;
    if (f->length >= (uint8_t)(base + 5u)) {
        uint32_t v = 0u;
        if (payload_u32(f, (uint8_t)(base + 1u), &v)) duration = v;
    }
    return door_lock_set(id, false, duration, now) ? ERR_NONE : ERR_BAD_PARAMETER;
}

void door_handlers_register(void) {
    command_dispatch_register(CMD_LOCK, 1u, 1u, handle_lock);
    command_dispatch_register(CMD_UNLOCK, 1u, 1u, handle_unlock);
}
