#ifndef IASS_GPIO_H
#define IASS_GPIO_H
#include <stdint.h>
#include <stdbool.h>
void gpio_init(void);
void gpio_servo_set(uint8_t id, bool high);
void gpio_door_lock_set(uint8_t id, bool locked);
bool gpio_door_sensor_open(uint8_t id);
void gpio_alarm_set(uint8_t id, bool on);
bool gpio_override_active(uint8_t id);
#endif
