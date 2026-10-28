#include "uart.h"
#include "config.h"
#include <avr/io.h>
#include <avr/interrupt.h>

#define RX_SIZE 128u
#define TX_SIZE 128u

static volatile uint8_t rx_buf[RX_SIZE];
static volatile uint8_t rx_head, rx_tail;
static volatile uint8_t tx_buf[TX_SIZE];
static volatile uint8_t tx_head, tx_tail;

void uart_init(void) {
    uint16_t ubrr = (uint16_t)((F_CPU / (16UL * UART_BAUD)) - 1UL);
    UBRR0H = (uint8_t)(ubrr >> 8);
    UBRR0L = (uint8_t)ubrr;
    UCSR0A = 0;
    UCSR0B = _BV(RXEN0) | _BV(TXEN0) | _BV(RXCIE0);
    UCSR0C = _BV(UCSZ01) | _BV(UCSZ00);
}

ISR(USART_RX_vect) {
    uint8_t next = (uint8_t)((rx_head + 1u) % RX_SIZE);
    uint8_t b = UDR0;
    if (next != rx_tail) {
        rx_buf[rx_head] = b;
        rx_head = next;
    }
}

ISR(USART_UDRE_vect) {
    if (tx_tail == tx_head) {
        UCSR0B &= (uint8_t)~_BV(UDRIE0);
    } else {
        UDR0 = tx_buf[tx_tail];
        tx_tail = (uint8_t)((tx_tail + 1u) % TX_SIZE);
    }
}

bool uart_read_byte(uint8_t *byte) {
    bool ok = false;
    uint8_t s = SREG;
    cli();
    if (rx_tail != rx_head) {
        *byte = rx_buf[rx_tail];
        rx_tail = (uint8_t)((rx_tail + 1u) % RX_SIZE);
        ok = true;
    }
    SREG = s;
    return ok;
}

void uart_write_byte(uint8_t byte) {
    uint8_t next;
    uint8_t s = SREG;
    cli();
    next = (uint8_t)((tx_head + 1u) % TX_SIZE);
    if (next != tx_tail) {
        tx_buf[tx_head] = byte;
        tx_head = next;
        UCSR0B |= _BV(UDRIE0);
    }
    SREG = s;
}

void uart_write_buffer(const uint8_t *data, uint8_t len) {
    for (uint8_t i = 0; i < len; ++i) uart_write_byte(data[i]);
}
