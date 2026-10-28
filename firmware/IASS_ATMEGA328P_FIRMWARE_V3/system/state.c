#include "state.h"
#include "config.h"
#include "actuators/servo.h"
#include "actuators/door_lock.h"
#include "actuators/alarm.h"

static system_state_t s;

void state_init(uint8_t reset_reason){
    s.uptime_ms=0u;s.last_heartbeat_ms=0u;s.failsafe_active=1u;s.last_reset_reason=reset_reason;s.protocol_faults=0u;
    for(uint8_t i=0u;i<3u;++i){s.servos[i].angle=SERVO_HOME_DEG;s.servos[i].target_angle=SERVO_HOME_DEG;s.servos[i].min_angle=SERVO_MIN_DEG;s.servos[i].max_angle=SERVO_MAX_DEG;s.servos[i].moving=0u;s.servos[i].fault=0u;}
    for(uint8_t i=0u;i<2u;++i){s.doors[i].locked_commanded=1u;s.doors[i].locked_actual=1u;s.doors[i].door_open=0u;s.doors[i].fault=0u;s.doors[i].unlock_deadline_ms=0u;s.alarms[i].active=0u;s.alarms[i].mode=ALARM_OFF;s.alarms[i].deadline_ms=0u;s.alarms[i].fault=0u;}
}

system_state_t *state_get(void){return &s;}
void state_set_uptime(uint32_t now){s.uptime_ms=now;}
void state_set_heartbeat(uint32_t now){
    s.last_heartbeat_ms=now;
    if(s.failsafe_active) (void)alarm_clear(2u);
    s.failsafe_active=0u;
}

void state_apply_failsafe(uint32_t now){
    (void)door_lock_set(1u,true,0u,now);(void)door_lock_set(2u,true,0u,now);servo_home_all();
    /* Physical safety policy: silence the siren but keep the dedicated visual
     * alarm channel asserted. On the current prototype alarm_2 is the strobe
     * simulation output. */
    (void)alarm_clear(1u);(void)alarm_clear(2u);(void)alarm_trigger(2u,ALARM_STROBE,0u,now);
    s.failsafe_active=1u;
}
void state_check_failsafe(uint32_t now){if((uint32_t)(now-s.last_heartbeat_ms)>HEARTBEAT_TIMEOUT_MS&&!s.failsafe_active)state_apply_failsafe(now);}
