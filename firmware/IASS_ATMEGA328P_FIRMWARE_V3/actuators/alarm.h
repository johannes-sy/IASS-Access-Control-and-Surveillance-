#ifndef IASS_ALARM_H
#define IASS_ALARM_H
#include <stdint.h>
#include <stdbool.h>
#include "system_types.h"
void alarm_init(void);
bool alarm_trigger(uint8_t id, alarm_mode_t mode, uint32_t duration_ms, uint32_t now);
bool alarm_clear(uint8_t id);
void alarm_clear_all(void);
void alarm_tick(uint32_t now);
bool alarm_is_active(uint8_t id);
alarm_mode_t alarm_get_mode(uint8_t id);
#endif
