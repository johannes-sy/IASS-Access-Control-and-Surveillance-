#include "timer.h"
#include "config.h"
#include "actuators/servo.h"
#include "actuators/alarm.h"
#include "actuators/door_lock.h"
#include <avr/io.h>
#include <avr/interrupt.h>
static volatile uint32_t g_ms;
void timer_init(void){
    TCCR0A=_BV(WGM01);TCCR0B=_BV(CS01)|_BV(CS00);OCR0A=249u;TIMSK0=_BV(OCIE0A);
    TCCR1A=0;TCCR1B=_BV(CS11)|_BV(WGM12);OCR1A=39999u;TIMSK1=_BV(OCIE1A);
    TCCR2A=0;TCCR2B=0;
}
ISR(TIMER0_COMPA_vect){++g_ms;servo_tick_1ms();door_lock_tick(g_ms);alarm_tick(g_ms);}
ISR(TIMER1_COMPA_vect){servo_timer1_isr();}
uint32_t timer_millis(void){uint32_t v;uint8_t s=SREG;cli();v=g_ms;SREG=s;return v;}
