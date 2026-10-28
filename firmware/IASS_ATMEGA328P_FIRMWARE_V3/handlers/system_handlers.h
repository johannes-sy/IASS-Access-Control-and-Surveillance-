#ifndef IASS_SYSTEM_HANDLERS_H
#define IASS_SYSTEM_HANDLERS_H
#include <stdint.h>
void system_handlers_register(void);
/* Used by main.c's periodic telemetry tick (not just the on-demand
 * STATE_REQUEST command) -- exposed rather than duplicated. */
void system_send_telemetry(uint8_t sequence);
#endif
