#include "alarm_handlers.h"
#include "../protocol/command_dispatch.h"
#include "../protocol/payload.h"
#include "../include/config.h"
#include "../actuators/alarm.h"

/* CMD_ALARM_TRIGGER args: [alarm_id:u8][mode:u8][duration_ms:u32 optional]
 * (host-side TRIGGER_ALARM). One command covers every alarm channel in
 * every mode (SIREN on alarm_1 = your buzzer, STROBE on alarm_2 = your LED,
 * or SIREN_STROBE on either) rather than the old separate CMD_SIREN /
 * CMD_STROBE commands -- this is also exactly what REPEAT_VISIT_DETECTED
 * uses (mode=STROBE only, no siren) without needing a new command. */
static uint8_t handle_alarm_trigger(const frame_t *f, const command_meta_t *meta, uint8_t base, uint32_t now) {
    (void)meta;
    uint8_t id = 0u, mode = 0u;
    uint32_t duration = 0u;
    if (!payload_u8(f, base, &id) || !payload_u8(f, (uint8_t)(base + 1u), &mode)) return ERR_BAD_PARAMETER;
    if (f->length >= (uint8_t)(base + 6u)) {
        uint32_t v = 0u;
        if (payload_u32(f, (uint8_t)(base + 2u), &v)) duration = v;
    }
    if (mode > ALARM_SIREN_STROBE || mode == ALARM_OFF) return ERR_BAD_PARAMETER;
    return alarm_trigger(id, (alarm_mode_t)mode, duration, now) ? ERR_NONE : ERR_BAD_PARAMETER;
}

/* CMD_ALARM_CLEAR args: [alarm_id:u8], 0 = all */
static uint8_t handle_alarm_clear(const frame_t *f, const command_meta_t *meta, uint8_t base, uint32_t now) {
    (void)meta; (void)now;
    uint8_t id = 0u;
    if (!payload_u8(f, base, &id)) return ERR_BAD_PARAMETER;
    if (id == 0u) { alarm_clear_all(); return ERR_NONE; }
    return alarm_clear(id) ? ERR_NONE : ERR_BAD_PARAMETER;
}

void alarm_handlers_register(void) {
    command_dispatch_register(CMD_ALARM_TRIGGER, 2u, 1u, handle_alarm_trigger);
    command_dispatch_register(CMD_ALARM_CLEAR, 1u, 1u, handle_alarm_clear);
}
