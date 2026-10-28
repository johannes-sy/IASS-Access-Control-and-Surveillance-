#include "servo.h"
#include "config.h"
#include "drivers/gpio.h"
#include <avr/io.h>
#include <avr/interrupt.h>

static volatile uint8_t angle[3] = { SERVO_HOME_DEG, SERVO_HOME_DEG, SERVO_HOME_DEG };
static volatile uint8_t target[3] = { SERVO_HOME_DEG, SERVO_HOME_DEG, SERVO_HOME_DEG };
static volatile uint8_t moving[3];
static volatile uint8_t pulse_index;
static volatile uint8_t pulse_phase;

static uint16_t angle_to_ticks(uint8_t a) {
    /* Timer1 prescaler 8 => 0.5 us/tick; 1000..2000 us pulse. */
    return (uint16_t)(2000u + ((uint32_t)a * 2000u) / 180u);
}

void servo_init(void) {
    for (uint8_t i=0u;i<3u;++i) { angle[i]=SERVO_HOME_DEG; target[i]=SERVO_HOME_DEG; moving[i]=0u; }
    pulse_index=0u; pulse_phase=0u;
}

bool servo_set_target(uint8_t id, uint8_t a) {
    if (id < 1u || id > 3u || a > SERVO_MAX_DEG) return false;
    uint8_t s=SREG; cli(); target[id-1u]=a; moving[id-1u]=(angle[id-1u]!=a); SREG=s; return true;
}

void servo_stop(uint8_t id) {
    if (id < 1u || id > 3u) return;
    uint8_t s=SREG; cli(); target[id-1u]=angle[id-1u]; moving[id-1u]=0u; SREG=s;
}

void servo_home_all(void) { for (uint8_t i=1u;i<=3u;++i) (void)servo_set_target(i,SERVO_HOME_DEG); }
void servo_stop_all(void) { for (uint8_t i=1u;i<=3u;++i) servo_stop(i); }
uint8_t servo_get_angle(uint8_t id) { return (id<1u||id>3u)?0u:angle[id-1u]; }
uint8_t servo_get_target(uint8_t id) { return (id<1u||id>3u)?0u:target[id-1u]; }
uint8_t servo_is_moving(uint8_t id) { return (id<1u||id>3u)?0u:moving[id-1u]; }

void servo_tick_1ms(void) {
    static uint8_t divider=0u;
    if (++divider < SERVO_STEP_MS) return;
    divider=0u;
    for (uint8_t i=0u;i<3u;++i) {
        if (angle[i] < target[i]) ++angle[i];
        else if (angle[i] > target[i]) --angle[i];
        moving[i]=(angle[i]!=target[i]);
    }
}

void servo_timer1_isr(void) {
    if (pulse_phase == 0u) {
        TCNT1=0u; pulse_index=0u; pulse_phase=1u;
        gpio_servo_set(1u,true);
        OCR1A=(uint16_t)(angle_to_ticks(angle[0])-1u);
        return;
    }
    gpio_servo_set((uint8_t)(pulse_index+1u),false);
    ++pulse_index;
    if (pulse_index < 3u) {
        gpio_servo_set((uint8_t)(pulse_index+1u),true);
        OCR1A=(uint16_t)(angle_to_ticks(angle[pulse_index])-1u);
    } else {
        pulse_phase=0u;
        OCR1A=39999u;
    }
}
