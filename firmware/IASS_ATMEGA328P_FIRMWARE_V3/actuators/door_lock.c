#include "door_lock.h"
#include "config.h"
#include "drivers/gpio.h"

static volatile uint8_t commanded[2]={1u,1u};
static volatile uint8_t actual[2]={1u,1u};
static volatile uint8_t open_state[2]={0u,0u};
static volatile uint32_t deadline[2];

void door_lock_init(void) {
    gpio_door_lock_set(1u,true); gpio_door_lock_set(2u,true);
    commanded[0]=commanded[1]=1u; actual[0]=actual[1]=1u; deadline[0]=deadline[1]=0u;
}

bool door_lock_set(uint8_t id, bool locked, uint32_t duration_ms, uint32_t now) {
    if (id<1u||id>2u) return false;
    if (!locked && duration_ms==0u) duration_ms=DOOR_DEFAULT_UNLOCK_MS;
    gpio_door_lock_set(id,locked);
    commanded[id-1u]=locked?1u:0u;
    deadline[id-1u]=(!locked)?(now+duration_ms):0u;
    return true;
}

void door_lock_tick(uint32_t now) {
    for (uint8_t i=0u;i<2u;++i) {
        uint8_t id=(uint8_t)(i+1u);
#if IASS_ENABLE_DOOR_SENSORS
        open_state[i]=gpio_door_sensor_open(id)?1u:0u;
#else
        open_state[i]=0u;
#endif
        if (!commanded[i] && deadline[i]!=0u && (int32_t)(now-deadline[i])>=0) {
            gpio_door_lock_set(id,true); commanded[i]=1u; deadline[i]=0u;
        }
#if IASS_ENABLE_MANUAL_OVERRIDES
        if (gpio_override_active(id)) (void)door_lock_set(id,false,DOOR_DEFAULT_UNLOCK_MS,now);
#endif
        /* With no lock-position sensor, commanded state is the best physical
         * state estimate. It is explicitly reported as commanded/known, not
         * falsely presented as sensor-confirmed engagement. */
        actual[i]=commanded[i];
    }
}

bool door_is_locked_commanded(uint8_t id){return (id<1u||id>2u)?true:commanded[id-1u]!=0u;}
bool door_is_open(uint8_t id){return (id<1u||id>2u)?false:open_state[id-1u]!=0u;}
bool door_is_locked_actual(uint8_t id){return (id<1u||id>2u)?false:actual[id-1u]!=0u;}
bool door_override(uint8_t id){return gpio_override_active(id);}
