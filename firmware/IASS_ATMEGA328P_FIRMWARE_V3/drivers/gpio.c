#include "gpio.h"
#include "config.h"

void gpio_init(void) {
    SERVO1_DDR |= _BV(SERVO1_PIN);
    SERVO2_DDR |= _BV(SERVO2_PIN);
    SERVO3_DDR |= _BV(SERVO3_PIN);
    DOOR1_LOCK_DDR |= _BV(DOOR1_LOCK_PIN);
    DOOR2_LOCK_DDR |= _BV(DOOR2_LOCK_PIN);
    ALARM1_DDR |= _BV(ALARM1_PIN);
    ALARM2_DDR |= _BV(ALARM2_PIN);

#if IASS_ENABLE_DOOR_SENSORS
    DOOR1_SENSOR_DDR &= (uint8_t)~_BV(DOOR1_SENSOR_PIN);
    DOOR2_SENSOR_DDR &= (uint8_t)~_BV(DOOR2_SENSOR_PIN);
    DOOR1_SENSOR_PORT |= _BV(DOOR1_SENSOR_PIN);
    DOOR2_SENSOR_PORT |= _BV(DOOR2_SENSOR_PIN);
#endif
#if IASS_ENABLE_MANUAL_OVERRIDES
    OVERRIDE_DDR &= (uint8_t)~(_BV(DOOR1_OVERRIDE_PIN) | _BV(DOOR2_OVERRIDE_PIN));
    OVERRIDE_PORT |= _BV(DOOR1_OVERRIDE_PIN) | _BV(DOOR2_OVERRIDE_PIN);
#endif

    gpio_door_lock_set(1u, true); gpio_door_lock_set(2u, true);
    gpio_alarm_set(1u, false); gpio_alarm_set(2u, false);
    gpio_servo_set(1u, false); gpio_servo_set(2u, false); gpio_servo_set(3u, false);
}

void gpio_servo_set(uint8_t id, bool high) {
    volatile uint8_t *port = 0; uint8_t mask = 0u;
    if (id == 1u) { port=&SERVO1_PORT; mask=_BV(SERVO1_PIN); }
    else if (id == 2u) { port=&SERVO2_PORT; mask=_BV(SERVO2_PIN); }
    else if (id == 3u) { port=&SERVO3_PORT; mask=_BV(SERVO3_PIN); }
    else return;
    if (high) *port |= mask; else *port &= (uint8_t)~mask;
}

void gpio_door_lock_set(uint8_t id, bool locked) {
    bool output_on = DOOR_OUTPUT_ACTIVE_HIGH_LOCKED ? locked : !locked;
    if (id == 1u) { if (output_on) DOOR1_LOCK_PORT |= _BV(DOOR1_LOCK_PIN); else DOOR1_LOCK_PORT &= (uint8_t)~_BV(DOOR1_LOCK_PIN); }
    else if (id == 2u) { if (output_on) DOOR2_LOCK_PORT |= _BV(DOOR2_LOCK_PIN); else DOOR2_LOCK_PORT &= (uint8_t)~_BV(DOOR2_LOCK_PIN); }
}

bool gpio_door_sensor_open(uint8_t id) {
#if IASS_ENABLE_DOOR_SENSORS
    if (id == 1u) return (PINC & _BV(DOOR1_SENSOR_PIN)) == 0u;
    if (id == 2u) return (PINC & _BV(DOOR2_SENSOR_PIN)) == 0u;
#else
    (void)id;
#endif
    return false;
}

void gpio_alarm_set(uint8_t id, bool on) {
    bool output_on = ALARM_OUTPUT_ACTIVE_HIGH ? on : !on;
    if (id == 1u) { if (output_on) ALARM1_PORT |= _BV(ALARM1_PIN); else ALARM1_PORT &= (uint8_t)~_BV(ALARM1_PIN); }
    else if (id == 2u) { if (output_on) ALARM2_PORT |= _BV(ALARM2_PIN); else ALARM2_PORT &= (uint8_t)~_BV(ALARM2_PIN); }
}

bool gpio_override_active(uint8_t id) {
#if IASS_ENABLE_MANUAL_OVERRIDES
    if (id == 1u) return (OVERRIDE_PINREG & _BV(DOOR1_OVERRIDE_PIN)) == 0u;
    if (id == 2u) return (OVERRIDE_PINREG & _BV(DOOR2_OVERRIDE_PIN)) == 0u;
#else
    (void)id;
#endif
    return false;
}
