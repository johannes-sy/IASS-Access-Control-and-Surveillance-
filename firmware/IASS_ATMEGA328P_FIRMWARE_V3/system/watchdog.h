#ifndef IASS_WATCHDOG_H
#define IASS_WATCHDOG_H
#include <stdint.h>
void watchdog_init(void);
void watchdog_kick(void);
uint8_t watchdog_reset_reason(void);
#endif
