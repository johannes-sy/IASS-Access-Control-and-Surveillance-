#ifndef IASS_STATE_H
#define IASS_STATE_H
#include "system_types.h"
#include <stdint.h>
void state_init(uint8_t reset_reason);
system_state_t *state_get(void);
void state_set_heartbeat(uint32_t now);
void state_check_failsafe(uint32_t now);
void state_apply_failsafe(uint32_t now);
/* Was previously never called anywhere -- system_state_t.uptime_ms stayed 0
 * for the life of the process, silently making both the telemetry uptime
 * field and any boot-fault-report timestamp meaningless. main.c now calls
 * this once per loop iteration. */
void state_set_uptime(uint32_t now);
#endif
