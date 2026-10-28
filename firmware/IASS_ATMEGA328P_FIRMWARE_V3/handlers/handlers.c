#include "handlers.h"
#include "system_handlers.h"
#include "servo_handlers.h"
#include "door_handlers.h"
#include "alarm_handlers.h"

void handlers_register_all(void) {
    system_handlers_register();
    servo_handlers_register();
    door_handlers_register();
    alarm_handlers_register();
}
