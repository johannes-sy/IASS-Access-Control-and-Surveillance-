#include "command_dispatch.h"
#include "payload.h"
#include "../include/config.h"

#define COMMAND_TABLE_SIZE 12u
static command_entry_t table[COMMAND_TABLE_SIZE];
static uint8_t table_count;

static uint32_t read_u32(const frame_t *f, uint8_t i) {
    uint32_t v = 0u; (void)payload_u32(f, i, &v); return v;
}

void command_dispatch_init(void) {
    table_count = 0u;
}

bool command_dispatch_register(uint8_t command_id, uint8_t min_args_len, uint8_t requires_meta, command_handler_fn handler) {
    if (table_count >= COMMAND_TABLE_SIZE || handler == 0) return false;
    for (uint8_t i = 0u; i < table_count; ++i)
        if (table[i].command_id == command_id) return false; /* already registered */
    table[table_count].command_id = command_id;
    table[table_count].min_args_len = min_args_len;
    table[table_count].requires_meta = requires_meta;
    table[table_count].handler = handler;
    ++table_count;
    return true;
}

static const command_entry_t *find_entry(uint8_t command_id) {
    for (uint8_t i = 0u; i < table_count; ++i)
        if (table[i].command_id == command_id) return &table[i];
    return 0;
}

/* Meta block layout (14 bytes, immediately at payload offset 0 for every
 * command that requires_meta):
 *   [0..3]  transaction id (u32)
 *   [4..7]  correlation id (u32)
 *   [8..11] issued_ms, MCU uptime at the moment the host issued this (u32)
 *   [12..13] ttl_ms (u16); 0 means "no expiry"
 * Command-specific arguments start at offset 14 (`base`).
 */
#define META_LEN 14u

static command_meta_t parse_meta(const frame_t *f) {
    command_meta_t m = {0};
    if (f->length < META_LEN) return m;
    m.transaction = read_u32(f, 0u);
    m.correlation = read_u32(f, 4u);
    m.issued_ms = read_u32(f, 8u);
    m.ttl_ms = (uint16_t)(((uint16_t)f->payload[12] << 8) | f->payload[13]);
    m.priority = f->flags;
    m.valid = 1u;
    return m;
}

static bool is_duplicate(uint32_t transaction, uint32_t now) {
    static uint32_t ids[4];
    static uint32_t times[4];
    static uint8_t next;
    if (transaction == 0u) return false;
    for (uint8_t i = 0u; i < 4u; ++i)
        if (ids[i] == transaction && (uint32_t)(now - times[i]) < 10000UL) return true;
    ids[next] = transaction; times[next] = now; next = (uint8_t)((next + 1u) & 3u);
    return false;
}

uint8_t command_dispatch_execute(const frame_t *f, uint32_t now) {
    const command_entry_t *entry = find_entry(f->command);
    if (entry == 0) return ERR_UNSUPPORTED;

    command_meta_t meta = {0};
    if (entry->requires_meta) {
        meta = parse_meta(f);
        if (!meta.valid) return ERR_BAD_PARAMETER;
        if (meta.ttl_ms != 0u && (uint32_t)(now - meta.issued_ms) > meta.ttl_ms) return ERR_STALE_COMMAND;
        if (is_duplicate(meta.transaction, now)) return ERR_DUPLICATE;
    }

    const uint8_t base = entry->requires_meta ? META_LEN : 0u;
    uint8_t args_len = (f->length > base) ? (uint8_t)(f->length - base) : 0u;
    if (args_len < entry->min_args_len) return ERR_BAD_PARAMETER;

    return entry->handler(f, &meta, base, now);
}

uint8_t command_dispatch_capabilities(void) {
    return CAP_SERVO | CAP_DOOR | CAP_ALARM | CAP_EVENTS | CAP_FAULT_REPORTING
         | CAP_PRIORITY_QUEUE | CAP_DUPLICATE_PROTECTION | CAP_TTL_EXPIRY;
}
