/* Native test-only stand-in for actuators/servo.c. The real servo.c drives
 * hardware timer ISRs to generate RC pulses -- inherently AVR-specific and
 * not meaningfully unit-testable without simulating interrupts. This mock
 * gives command_dispatch/servo_handlers something real to call so the
 * *command handling* (validation, routing, ACK/error codes) gets exercised
 * end-to-end, which is what this test suite is actually checking. */
#include "../../actuators/servo.h"
#include <string.h>

static uint8_t angle[3], target[3];

void servo_init(void) { memset(angle, 90, sizeof(angle)); memset(target, 90, sizeof(target)); }
bool servo_set_target(uint8_t id, uint8_t a) {
    if (id < 1 || id > 3 || a > 180) return false;
    target[id - 1] = a; return true;
}
void servo_stop(uint8_t id) { if (id >= 1 && id <= 3) target[id - 1] = angle[id - 1]; }
void servo_home_all(void) { for (uint8_t i = 1; i <= 3; ++i) servo_set_target(i, 90); }
void servo_stop_all(void) { for (uint8_t i = 1; i <= 3; ++i) servo_stop(i); }
uint8_t servo_get_angle(uint8_t id) { return (id < 1 || id > 3) ? 0 : angle[id - 1]; }
uint8_t servo_get_target(uint8_t id) { return (id < 1 || id > 3) ? 0 : target[id - 1]; }
uint8_t servo_is_moving(uint8_t id) { return (id < 1 || id > 3) ? 0 : (angle[id - 1] != target[id - 1]); }
void servo_tick_1ms(void) { for (uint8_t i = 0; i < 3; ++i) { if (angle[i] < target[i]) ++angle[i]; else if (angle[i] > target[i]) --angle[i]; } }
void servo_timer1_isr(void) {}
