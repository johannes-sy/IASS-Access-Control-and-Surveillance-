#ifndef IASS_COMMAND_DISPATCH_H
#define IASS_COMMAND_DISPATCH_H
#include <stdint.h>
#include <stdbool.h>
#include "frame.h"

/* This is the layer the host-side software's scenario/intent changes should
 * never require you to touch main.c for. main.c only calls
 * command_dispatch_execute(); everything about *which* command means *what*
 * lives here and in handlers/.
 *
 * Design: a small static table of (command_id -> handler), not a switch
 * statement. Adding a new command the host might start sending (a future
 * HardwarePolicy action) means adding one row to the table below and one
 * handler function in the matching handlers/ module -- nothing else in the
 * firmware changes. This mirrors how a REST router or a Linux driver's
 * ioctl table works: the transport layer (frame.c) doesn't know command
 * semantics, and the semantic layer doesn't know wire bytes.
 *
 * Rich transaction metadata (transaction/correlation id, issued timestamp,
 * TTL, duplicate detection) is validated here, once, generically -- not
 * duplicated per handler. A handler only ever sees a frame it's already
 * known to be non-stale, non-duplicate, and correctly shaped for its
 * command.
 */

typedef struct {
    uint32_t transaction;
    uint32_t correlation;
    uint32_t issued_ms;
    uint16_t ttl_ms;
    uint8_t priority;
    uint8_t valid;
} command_meta_t;

/* Handler signature every command handler implements. `meta` is already
 * validated (non-stale, non-duplicate) by the time a handler is called.
 * `base` is the payload offset where command-specific arguments start
 * (immediately after the 14-byte meta block). Returns an ERR_* code from
 * config.h -- ERR_NONE on success. */
typedef uint8_t (*command_handler_fn)(const frame_t *f, const command_meta_t *meta, uint8_t base, uint32_t now);

typedef struct {
    uint8_t command_id;
    uint8_t min_args_len;   /* minimum payload bytes required *after* meta */
    uint8_t requires_meta;  /* 0 for CMD_HEARTBEAT, which predates a full session */
    command_handler_fn handler;
} command_entry_t;

void command_dispatch_init(void);

/* Registers a handler for a command id. Returns false if the table is full
 * or the id is already registered -- callers should treat that as a build
 * misconfiguration, not a runtime condition to recover from. */
bool command_dispatch_register(uint8_t command_id, uint8_t min_args_len, uint8_t requires_meta, command_handler_fn handler);

/* Validates meta/TTL/duplicate, looks up the handler, calls it. Returns an
 * ERR_* code suitable for frame_send_ack(). */
uint8_t command_dispatch_execute(const frame_t *f, uint32_t now);

/* Capability bits reported in the IDENTIFY response -- lets the host detect
 * what a connected firmware build actually supports before assuming, e.g.
 * during first bring-up against a firmware whose feature set hasn't been
 * confirmed yet. See docs/COMMAND_ARCHITECTURE.md. */
uint8_t command_dispatch_capabilities(void);

#endif
