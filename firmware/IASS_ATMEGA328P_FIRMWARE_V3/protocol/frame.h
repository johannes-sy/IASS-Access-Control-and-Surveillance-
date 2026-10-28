#ifndef IASS_FRAME_H
#define IASS_FRAME_H
#include <stdint.h>
#include <stdbool.h>
#include "../include/config.h"

typedef struct {
    uint8_t version;
    uint8_t sequence;
    uint8_t device_id;
    uint8_t command;
    uint8_t flags;
    uint8_t length;
    uint8_t payload[FRAME_MAX_PAYLOAD];
} frame_t;

void frame_init(void);
void frame_poll(void);
bool frame_pop(frame_t *out);
uint16_t frame_crc16(const frame_t *frame);
void frame_send(const frame_t *frame);
void frame_send_ack(const frame_t *request, uint8_t error);
void frame_send_fault(uint8_t fault_code, uint32_t uptime_ms);

/* Count of frames rejected for a bad CRC/malformed shape since boot. Used to
 * populate system_state_t.protocol_faults in telemetry. */
uint16_t frame_checksum_fault_count(void);

#endif
