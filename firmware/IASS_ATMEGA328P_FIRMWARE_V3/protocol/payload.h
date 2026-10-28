#ifndef IASS_PAYLOAD_H
#define IASS_PAYLOAD_H
#include <stdint.h>
#include <stdbool.h>
#include "frame.h"
bool payload_u8(const frame_t *f, uint8_t index, uint8_t *value);
bool payload_u16(const frame_t *f, uint8_t index, uint16_t *value);
bool payload_u32(const frame_t *f, uint8_t index, uint32_t *value);
#endif
