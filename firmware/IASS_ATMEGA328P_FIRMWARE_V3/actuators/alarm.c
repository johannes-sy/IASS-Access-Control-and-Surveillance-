#include "alarm.h"
#include "drivers/gpio.h"

static volatile uint8_t active[2];
static volatile alarm_mode_t mode_state[2];
static volatile uint32_t deadline[2];

void alarm_init(void){for(uint8_t i=1u;i<=2u;++i){active[i-1u]=0u;mode_state[i-1u]=ALARM_OFF;deadline[i-1u]=0u;gpio_alarm_set(i,false);}}

bool alarm_trigger(uint8_t id, alarm_mode_t mode, uint32_t duration_ms, uint32_t now){
    if(id<1u||id>2u||mode==ALARM_OFF)return false;
    active[id-1u]=1u;mode_state[id-1u]=mode;deadline[id-1u]=duration_ms?(now+duration_ms):0u;gpio_alarm_set(id,true);return true;
}
bool alarm_clear(uint8_t id){if(id<1u||id>2u)return false;active[id-1u]=0u;mode_state[id-1u]=ALARM_OFF;deadline[id-1u]=0u;gpio_alarm_set(id,false);return true;}
void alarm_clear_all(void){(void)alarm_clear(1u);(void)alarm_clear(2u);}
void alarm_tick(uint32_t now){for(uint8_t i=0u;i<2u;++i)if(active[i]&&deadline[i]!=0u&&(int32_t)(now-deadline[i])>=0)(void)alarm_clear((uint8_t)(i+1u));}
bool alarm_is_active(uint8_t id){return(id<1u||id>2u)?false:active[id-1u]!=0u;}
alarm_mode_t alarm_get_mode(uint8_t id){return(id<1u||id>2u)?ALARM_OFF:mode_state[id-1u];}
