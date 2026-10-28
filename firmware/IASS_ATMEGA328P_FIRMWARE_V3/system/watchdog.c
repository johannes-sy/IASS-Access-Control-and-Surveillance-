#include "watchdog.h"
#include <avr/wdt.h>
#include <avr/io.h>

static uint8_t reset_reason;

void watchdog_init(void) {
    reset_reason = MCUSR;
    MCUSR = 0;
    wdt_disable();
    wdt_enable(WDTO_2S);
}

void watchdog_kick(void) {
    wdt_reset();
}

uint8_t watchdog_reset_reason(void) {
    return reset_reason;
}
