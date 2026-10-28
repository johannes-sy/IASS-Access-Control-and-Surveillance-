#ifndef IASS_UART_H
#define IASS_UART_H
#include <stdint.h>
#include <stdbool.h>
void uart_init(void);
bool uart_read_byte(uint8_t *byte);
void uart_write_byte(uint8_t byte);
void uart_write_buffer(const uint8_t *data, uint8_t len);
#endif
