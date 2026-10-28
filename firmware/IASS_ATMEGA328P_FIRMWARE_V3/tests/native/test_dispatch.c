/* Native (x86) integration test of the wire protocol + command dispatch +
 * handler layer, run with a normal host compiler against real firmware
 * source files (protocol .c files, handlers/ modules, actuators/alarm.c,
 * actuators/door_lock.c, system/state.c, system/state_watch.c) linked
 * against tests/native/mock_*.c instead of the AVR-register-backed
 * drivers/servo. This is what "verified by actually building and running,
 * not just written" means for MCU-side code that can't run natively as a
 * whole program -- the parts that don't depend on real timer/UART hardware
 * (which is everything this refactor actually changed) get exercised for
 * real, byte-for-byte over the same frame_send()/frame_poll() the AVR build
 * uses.
 *
 * Build: see tests/native/Makefile. Run: build/native_test (exits non-zero
 * on any failed check).
 */
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "../../protocol/frame.h"
#include "../../protocol/command_dispatch.h"
#include "../../handlers/handlers.h"
#include "../../handlers/system_handlers.h"
#include "../../actuators/servo.h"
#include "../../actuators/door_lock.h"
#include "../../actuators/alarm.h"
#include "../../system/state.h"
#include "../../system/state_watch.h"
#include "../../drivers/uart.h"
#include "../../drivers/gpio.h"
#include "../../drivers/timer.h"
#include "../../include/config.h"

extern void mock_uart_inject(const uint8_t *data, int len);
extern int mock_uart_tx_len(void);
extern const uint8_t *mock_uart_tx_buf(void);
extern void mock_uart_tx_clear(void);
extern void mock_timer_set(uint32_t v);

static int failures;
#define CHECK(cond, msg) do { \
    if (!(cond)) { fprintf(stderr, "FAIL: %s (%s:%d)\n", msg, __FILE__, __LINE__); ++failures; } \
    else { printf("ok:   %s\n", msg); } \
} while (0)

static void write_u32(uint8_t *p, uint32_t v) { p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16); p[2]=(uint8_t)(v>>8); p[3]=(uint8_t)v; }

/* Builds a rich meta block (transaction, correlation, issued_ms, ttl_ms)
 * exactly as command_dispatch.c expects at payload offset 0. */
static uint8_t build_meta(uint8_t *payload, uint32_t transaction, uint32_t correlation, uint32_t issued_ms, uint16_t ttl_ms) {
    write_u32(payload + 0, transaction);
    write_u32(payload + 4, correlation);
    write_u32(payload + 8, issued_ms);
    payload[12] = (uint8_t)(ttl_ms >> 8);
    payload[13] = (uint8_t)ttl_ms;
    return 14u;
}

/* Round-trips a frame through frame_send() -> mock UART -> frame_poll() ->
 * frame_pop(), exactly as a real byte stream from the host would arrive. */
static bool round_trip(const frame_t *in, frame_t *out) {
    mock_uart_tx_clear();
    frame_send(in);
    mock_uart_inject(mock_uart_tx_buf(), mock_uart_tx_len());
    mock_uart_tx_clear();
    frame_poll();
    return frame_pop(out);
}

static void reset_all(void) {
    gpio_init(); servo_init(); door_lock_init(); alarm_init();
    state_init(0u); frame_init(); command_dispatch_init(); handlers_register_all(); state_watch_init();
    mock_timer_set(0u);
    mock_uart_tx_clear();
}

static void test_crc_round_trip(void) {
    reset_all();
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = 7u; f.device_id = DEVICE_CONTROLLER_ID; f.command = CMD_HEARTBEAT;
    frame_t out;
    bool ok = round_trip(&f, &out);
    CHECK(ok, "frame round-trips through frame_send/frame_poll/frame_pop");
    CHECK(out.command == CMD_HEARTBEAT && out.sequence == 7u, "round-tripped frame preserves command/sequence");
}

static void test_corrupted_crc_rejected(void) {
    reset_all();
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = 1u; f.device_id = DEVICE_CONTROLLER_ID; f.command = CMD_HEARTBEAT;
    mock_uart_tx_clear();
    frame_send(&f);
    uint8_t bytes[32]; int n = mock_uart_tx_len();
    memcpy(bytes, mock_uart_tx_buf(), (size_t)n);
    bytes[n - 3] ^= 0xFFu; /* flip a CRC byte */
    mock_uart_tx_clear();
    mock_uart_inject(bytes, n);
    frame_poll();
    frame_t out;
    CHECK(!frame_pop(&out), "frame with corrupted CRC is silently rejected, not parsed");
    CHECK(frame_checksum_fault_count() == 1u, "corrupted frame increments the checksum fault counter");
}

static void test_unlock_door_with_duration(void) {
    reset_all();
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = 2u; f.device_id = DEVICE_CONTROLLER_ID; f.command = CMD_UNLOCK;
    uint8_t off = build_meta(f.payload, 100u, 200u, 0u, 0u);
    f.payload[off] = 1u; /* door_1 */
    write_u32(&f.payload[off + 1], 5000u); /* duration_ms */
    f.length = (uint8_t)(off + 5u);

    frame_t received;
    CHECK(round_trip(&f, &received), "unlock-door frame round-trips");
    uint8_t err = command_dispatch_execute(&received, 0u);
    CHECK(err == ERR_NONE, "UNLOCK dispatches with ERR_NONE");
    CHECK(!door_is_locked_commanded(1u), "door_1 is now commanded unlocked");

    /* Auto-relock after the requested duration. */
    door_lock_tick(5001u);
    CHECK(door_is_locked_commanded(1u), "door_1 auto-relocks after its duration elapses");
}

static void test_alarm_repeat_visit_strobe_only(void) {
    /* This is exactly what decision_security's REPEAT_VISIT_DETECTED path
     * sends: alarm_2 (the LED/strobe channel), mode=STROBE, no siren. */
    reset_all();
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = 3u; f.device_id = DEVICE_CONTROLLER_ID; f.command = CMD_ALARM_TRIGGER;
    uint8_t off = build_meta(f.payload, 300u, 400u, 0u, 0u);
    f.payload[off] = 2u;              /* alarm_2 */
    f.payload[off + 1] = ALARM_STROBE;
    write_u32(&f.payload[off + 2], 5000u);
    f.length = (uint8_t)(off + 6u);

    frame_t received;
    CHECK(round_trip(&f, &received), "alarm-trigger frame round-trips");
    uint8_t err = command_dispatch_execute(&received, 1000u);
    CHECK(err == ERR_NONE, "ALARM_TRIGGER (strobe-only) dispatches with ERR_NONE");
    CHECK(alarm_is_active(2u), "alarm_2 (LED/strobe channel) is active");
    CHECK(alarm_get_mode(2u) == ALARM_STROBE, "alarm_2 mode is STROBE, not SIREN_STROBE");
    CHECK(!alarm_is_active(1u), "alarm_1 (siren/buzzer channel) was not touched");
}

static void test_stale_command_rejected(void) {
    reset_all();
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = 4u; f.device_id = DEVICE_CONTROLLER_ID; f.command = CMD_LOCK;
    uint8_t off = build_meta(f.payload, 500u, 0u, /*issued_ms=*/0u, /*ttl_ms=*/100u);
    f.payload[off] = 1u;
    f.length = (uint8_t)(off + 1u);

    frame_t received;
    CHECK(round_trip(&f, &received), "lock frame round-trips");
    uint8_t err = command_dispatch_execute(&received, /*now=*/5000u); /* 5000 - 0 = 4900ms > ttl 100ms */
    CHECK(err == ERR_STALE_COMMAND, "a command issued at t=0 with ttl=100ms is rejected as stale at t=5000ms");
}

static void test_duplicate_transaction_rejected(void) {
    reset_all();
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = 5u; f.device_id = DEVICE_CONTROLLER_ID; f.command = CMD_LOCK;
    uint8_t off = build_meta(f.payload, 999u, 0u, 0u, 0u);
    f.payload[off] = 2u;
    f.length = (uint8_t)(off + 1u);

    frame_t received;
    round_trip(&f, &received);
    uint8_t first = command_dispatch_execute(&received, 0u);
    uint8_t second = command_dispatch_execute(&received, 1u); /* same transaction id=999 replayed */
    CHECK(first == ERR_NONE, "first LOCK with transaction=999 succeeds");
    CHECK(second == ERR_DUPLICATE, "replaying the same transaction id is rejected as a duplicate");
}

static void test_unsupported_command(void) {
    reset_all();
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = 6u; f.device_id = DEVICE_CONTROLLER_ID; f.command = 0xEEu; /* not registered */
    frame_t received;
    round_trip(&f, &received);
    uint8_t err = command_dispatch_execute(&received, 0u);
    CHECK(err == ERR_UNSUPPORTED, "an unregistered command id returns ERR_UNSUPPORTED, not a crash");
}

static void test_servo_set_via_dispatch(void) {
    reset_all();
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = 8u; f.device_id = DEVICE_CONTROLLER_ID; f.command = CMD_SERVO_SET;
    uint8_t off = build_meta(f.payload, 700u, 0u, 0u, 0u);
    f.payload[off] = 1u; f.payload[off + 1] = 45u;
    f.length = (uint8_t)(off + 2u);
    frame_t received;
    round_trip(&f, &received);
    uint8_t err = command_dispatch_execute(&received, 0u);
    CHECK(err == ERR_NONE, "SERVO_SET dispatches with ERR_NONE");
    CHECK(servo_get_target(1u) == 45u, "servo_1 target angle updated to 45");
}

static void test_state_watch_emits_event_on_unlock(void) {
    reset_all();
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = 9u; f.device_id = DEVICE_CONTROLLER_ID; f.command = CMD_UNLOCK;
    uint8_t off = build_meta(f.payload, 800u, 0u, 0u, 0u);
    f.payload[off] = 1u;
    f.length = (uint8_t)(off + 1u);
    frame_t received;
    round_trip(&f, &received);
    command_dispatch_execute(&received, 0u);

    mock_uart_tx_clear();
    state_watch_poll(0u);
    int tx_len = mock_uart_tx_len();
    CHECK(tx_len > 0, "state_watch_poll emits a frame after an unlock changes door state");
    const uint8_t *b = mock_uart_tx_buf();
    /* byte layout: AA VER SEQ DEV CMD FLAGS LEN payload... */
    CHECK(tx_len > 0 && b[4] == MSG_EVENT, "emitted frame is MSG_EVENT");
    CHECK(tx_len > 0 && b[7] == EVENT_DOOR_STATE, "event subtype is EVENT_DOOR_STATE");
}

static void test_emergency_stop_jumps_queue(void) {
    reset_all();
    /* Enqueue three ordinary servo-set frames, then one EMERGENCY_STOP
     * flagged FLAG_PRIORITY_EMERGENCY. It should come out of frame_pop()
     * first, not last. */
    for (uint8_t i = 0; i < 3; ++i) {
        frame_t f = {0};
        f.version = PROTOCOL_VERSION; f.sequence = i; f.device_id = DEVICE_CONTROLLER_ID; f.command = CMD_SERVO_SET;
        uint8_t off = build_meta(f.payload, 1000u + i, 0u, 0u, 0u);
        f.payload[off] = 1u; f.payload[off + 1] = 10u;
        f.length = (uint8_t)(off + 2u);
        mock_uart_tx_clear(); frame_send(&f);
        mock_uart_inject(mock_uart_tx_buf(), mock_uart_tx_len());
        mock_uart_tx_clear();
        frame_poll();
    }
    frame_t estop = {0};
    estop.version = PROTOCOL_VERSION; estop.sequence = 99u; estop.device_id = DEVICE_CONTROLLER_ID;
    estop.command = CMD_EMERGENCY_STOP; estop.flags = FLAG_PRIORITY_EMERGENCY;
    build_meta(estop.payload, 2000u, 0u, 0u, 0u);
    estop.length = 14u;
    mock_uart_tx_clear(); frame_send(&estop);
    mock_uart_inject(mock_uart_tx_buf(), mock_uart_tx_len());
    mock_uart_tx_clear();
    frame_poll();

    frame_t out;
    bool got = frame_pop(&out);
    CHECK(got && out.command == CMD_EMERGENCY_STOP, "EMERGENCY_STOP-flagged frame is popped first, ahead of 3 earlier-queued frames");
}

static void test_identify_reports_capabilities_and_counts(void) {
    reset_all();
    frame_t f = {0};
    f.version = PROTOCOL_VERSION; f.sequence = 11u; f.device_id = DEVICE_CONTROLLER_ID; f.command = CMD_IDENTIFY;
    uint8_t off = build_meta(f.payload, 1100u, 0u, 0u, 0u);
    f.length = off;
    frame_t received;
    round_trip(&f, &received);
    mock_uart_tx_clear();
    command_dispatch_execute(&received, 0u);
    const uint8_t *b = mock_uart_tx_buf();
    int n = mock_uart_tx_len();
    CHECK(n > 0 && b[4] == MSG_IDENTIFY, "IDENTIFY produces an MSG_IDENTIFY response");
    /* payload starts at byte 7: 'I' 'A' 'S' 'S' version caps num_servo num_door num_alarm */
    CHECK(n > 0 && b[7] == 'I' && b[8] == 'A' && b[9] == 'S' && b[10] == 'S', "IDENTIFY payload starts with the IASS magic");
    CHECK(n > 0 && b[13] == DEVICE_COUNT_SERVOS, "IDENTIFY reports servo count");
    CHECK(n > 0 && b[14] == DEVICE_COUNT_DOORS, "IDENTIFY reports door count");
    CHECK(n > 0 && b[15] == DEVICE_COUNT_ALARMS, "IDENTIFY reports alarm count");
}

int main(void) {
    test_crc_round_trip();
    test_corrupted_crc_rejected();
    test_unlock_door_with_duration();
    test_alarm_repeat_visit_strobe_only();
    test_stale_command_rejected();
    test_duplicate_transaction_rejected();
    test_unsupported_command();
    test_servo_set_via_dispatch();
    test_state_watch_emits_event_on_unlock();
    test_emergency_stop_jumps_queue();
    test_identify_reports_capabilities_and_counts();

    if (failures) { fprintf(stderr, "\n%d CHECK(S) FAILED\n", failures); return 1; }
    printf("\nALL CHECKS PASSED\n");
    return 0;
}
