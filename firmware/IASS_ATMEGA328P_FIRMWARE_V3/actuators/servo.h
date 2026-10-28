#ifndef IASS_SERVO_H
#define IASS_SERVO_H
#include <stdint.h>
#include <stdbool.h>
void servo_init(void);
bool servo_set_target(uint8_t id, uint8_t angle);
void servo_stop(uint8_t id);
void servo_home_all(void);
void servo_stop_all(void);
uint8_t servo_get_angle(uint8_t id);
uint8_t servo_get_target(uint8_t id);
void servo_tick_1ms(void);
void servo_timer1_isr(void);
uint8_t servo_is_moving(uint8_t id);
#endif
