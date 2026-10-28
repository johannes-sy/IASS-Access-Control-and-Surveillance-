/* Native (x86) test-only stand-ins for the AVR-register-backed drivers, so
 * the protocol/dispatch/handler/actuator logic can be exercised with a
 * normal host compiler and normal asserts instead of only "it compiled for
 * AVR". Never linked into the firmware itself -- see tests/native/README. */
#include "../../drivers/uart.h"
#include "../../drivers/gpio.h"
#include "../../drivers/timer.h"
#include <string.h>

#define MOCK_BUF 512
static uint8_t rx_buf[MOCK_BUF]; static int rx_head, rx_tail;
static uint8_t tx_buf[MOCK_BUF]; static int tx_len;
static uint32_t mock_now;

void uart_init(void) { rx_head = rx_tail = 0; tx_len = 0; }
bool uart_read_byte(uint8_t *b) {
    if (rx_tail == rx_head) return false;
    *b = rx_buf[rx_tail]; rx_tail = (rx_tail + 1) % MOCK_BUF; return true;
}
void uart_write_byte(uint8_t b) { if (tx_len < MOCK_BUF) tx_buf[tx_len++] = b; }
void uart_write_buffer(const uint8_t *d, uint8_t n) { for (uint8_t i = 0; i < n; ++i) uart_write_byte(d[i]); }

/* Test-only helpers (not part of the real driver API). */
void mock_uart_inject(const uint8_t *data, int len) {
    for (int i = 0; i < len; ++i) { rx_buf[rx_head] = data[i]; rx_head = (rx_head + 1) % MOCK_BUF; }
}
int mock_uart_tx_len(void) { return tx_len; }
const uint8_t *mock_uart_tx_buf(void) { return tx_buf; }
void mock_uart_tx_clear(void) { tx_len = 0; }

static bool servo_state[4];
static bool door_state[3];
static bool alarm_state[3];
void gpio_init(void) { memset(servo_state, 0, sizeof(servo_state)); memset(door_state, 0, sizeof(door_state)); memset(alarm_state, 0, sizeof(alarm_state)); }
void gpio_servo_set(uint8_t id, bool high) { if (id < 4) servo_state[id] = high; }
void gpio_door_lock_set(uint8_t id, bool locked) { if (id < 3) door_state[id] = locked; }
bool gpio_door_sensor_open(uint8_t id) { (void)id; return false; }
void gpio_alarm_set(uint8_t id, bool on) { if (id < 3) alarm_state[id] = on; }
bool gpio_override_active(uint8_t id) { (void)id; return false; }

void timer_init(void) { mock_now = 0; }
uint32_t timer_millis(void) { return mock_now; }
void mock_timer_set(uint32_t v) { mock_now = v; }
