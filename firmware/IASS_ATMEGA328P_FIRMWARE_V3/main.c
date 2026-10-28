#include "include/config.h"
#include "drivers/gpio.h"
#include "drivers/uart.h"
#include "drivers/timer.h"
#include "drivers/interrupts.h"
#include "protocol/frame.h"
#include "protocol/command_dispatch.h"
#include "handlers/handlers.h"
#include "handlers/system_handlers.h"
#include "actuators/servo.h"
#include "actuators/door_lock.h"
#include "actuators/alarm.h"
#include "system/watchdog.h"
#include "system/state.h"
#include "system/state_watch.h"
#include <avr/io.h>

/* main.c's whole job is: init every module, and run the loop. It has no
 * idea what CMD_UNLOCK means -- that lives entirely in
 * protocol/command_dispatch.c (validates the envelope: meta/TTL/duplicate)
 * and handlers directory (one file per hardware domain, each command mapped to
 * one handler function). Extending the command set the host speaks -- a
 * new HardwarePolicy action, a new scenario -- means adding a row to a
 * handler module's _register() call, never editing this file. See
 * docs/COMMAND_ARCHITECTURE.md.
 */

static bool valid_device(uint8_t id) { return id == DEVICE_CONTROLLER_ID || id == BROADCAST_DEVICE_ID; }

static void process_frame(const frame_t *f, uint32_t now) {
    if (!valid_device(f->device_id)) { frame_send_ack(f, ERR_BAD_DEVICE); return; }
    uint8_t err = command_dispatch_execute(f, now);
    frame_send_ack(f, err);
}

static void report_boot_faults(void) {
    uint8_t reason = state_get()->last_reset_reason;
    if (reason & _BV(WDRF)) {
        frame_send_fault(FAULT_WATCHDOG_RESET, state_get()->uptime_ms);
    }
}

int main(void) {
    watchdog_init();
    gpio_init();
    uart_init();
    timer_init();
    servo_init();
    door_lock_init();
    alarm_init();
    state_init(watchdog_reset_reason());
    frame_init();
    command_dispatch_init();
    handlers_register_all();
    state_watch_init();
    interrupts_init();

    state_set_uptime(0u);
    report_boot_faults();

    uint32_t last_telemetry = 0u;
    uint8_t telemetry_sequence = 0u;

    for (;;) {
        uint32_t now = timer_millis();
        state_set_uptime(now);
        frame_poll();
        frame_t f;
        while (frame_pop(&f)) process_frame(&f, now);

        state_check_failsafe(now);
        state_watch_poll(now);

        if ((uint32_t)(now - last_telemetry) >= TELEMETRY_PERIOD_MS) {
            last_telemetry = now;
            system_send_telemetry(telemetry_sequence++);
        }
        watchdog_kick();
    }
}
