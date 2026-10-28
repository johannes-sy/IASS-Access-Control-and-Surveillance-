#include "payload.h"
bool payload_u8(const frame_t *f, uint8_t i, uint8_t *v) { if (i >= f->length) return false; *v=f->payload[i]; return true; }
bool payload_u16(const frame_t *f, uint8_t i, uint16_t *v) { if ((uint8_t)(i+1u)>=f->length) return false; *v=(uint16_t)(((uint16_t)f->payload[i]<<8)|f->payload[i+1u]); return true; }
bool payload_u32(const frame_t *f, uint8_t i, uint32_t *v) { if ((uint8_t)(i+3u)>=f->length) return false; *v=((uint32_t)f->payload[i]<<24)|((uint32_t)f->payload[i+1u]<<16)|((uint32_t)f->payload[i+2u]<<8)|f->payload[i+3u]; return true; }
