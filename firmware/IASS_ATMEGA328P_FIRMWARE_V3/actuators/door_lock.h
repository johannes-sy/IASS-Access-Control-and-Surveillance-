#ifndef IASS_DOOR_LOCK_H
#define IASS_DOOR_LOCK_H
#include <stdint.h>
#include <stdbool.h>
void door_lock_init(void);
bool door_lock_set(uint8_t id, bool locked, uint32_t duration_ms, uint32_t now);
void door_lock_tick(uint32_t now);
bool door_is_locked_commanded(uint8_t id);
bool door_is_open(uint8_t id);
bool door_is_locked_actual(uint8_t id);
bool door_override(uint8_t id);
#endif
