#include "frame.h"
#include "../drivers/uart.h"
#include <string.h>

typedef enum {
    RX_WAIT_START,
    RX_VERSION,
    RX_SEQUENCE,
    RX_DEVICE,
    RX_COMMAND,
    RX_FLAGS,
    RX_LENGTH,
    RX_PAYLOAD,
    RX_CRC_H,
    RX_CRC_L,
    RX_END
} rx_state_t;

static rx_state_t state;
static frame_t current;
static uint8_t index;
static uint8_t crc_h;
static uint8_t crc_l;
static uint16_t checksum_fault_count;

#define FRAME_QUEUE_DEPTH 4u
static volatile frame_t ready_queue[FRAME_QUEUE_DEPTH];
static volatile uint8_t ready_head;
static volatile uint8_t ready_tail;

static uint16_t crc16_update(uint16_t crc, uint8_t data) {
    crc ^= (uint16_t)data << 8;
    for (uint8_t i = 0u; i < 8u; ++i)
        crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u) : (uint16_t)(crc << 1);
    return crc;
}

uint16_t frame_crc16(const frame_t *f) {
    uint16_t crc = 0xFFFFu;
    crc = crc16_update(crc, f->version);
    crc = crc16_update(crc, f->sequence);
    crc = crc16_update(crc, f->device_id);
    crc = crc16_update(crc, f->command);
    crc = crc16_update(crc, f->flags);
    crc = crc16_update(crc, f->length);
    for (uint8_t i = 0u; i < f->length; ++i) crc = crc16_update(crc, f->payload[i]);
    return crc;
}

uint16_t frame_checksum_fault_count(void) { return checksum_fault_count; }

void frame_init(void) {
    state = RX_WAIT_START;
    ready_head = 0u;
    ready_tail = 0u;
    checksum_fault_count = 0u;
    memset(&current, 0, sizeof(current));
}

static void publish_current(void) {
    uint8_t next_head = (uint8_t)((ready_head + 1u) & (FRAME_QUEUE_DEPTH - 1u));
    bool is_full = (next_head == ready_tail);
    if (current.flags & FLAG_PRIORITY_EMERGENCY) {
        /* A safety-critical frame (emergency stop) must never be the one
         * that gets dropped. If the queue is full, evict the single oldest
         * buffered frame to make room -- better to lose a stale
         * already-superseded command than the stop request -- then insert
         * at the front so it's the very next frame popped, ahead of
         * whatever's left. Moving tail backward on a power-of-two circular
         * buffer is a valid front-insert as long as we've just confirmed
         * there's a free slot. */
        if (is_full) ready_tail = (uint8_t)((ready_tail + 1u) & (FRAME_QUEUE_DEPTH - 1u));
        ready_tail = (uint8_t)((ready_tail - 1u) & (FRAME_QUEUE_DEPTH - 1u));
        ready_queue[ready_tail] = current;
        return;
    }
    if (is_full) return; /* bounded queue: drop newest non-priority frame on overflow */
    ready_queue[ready_head] = current;
    ready_head = next_head;
}

void frame_poll(void) {
    uint8_t b;
    while (uart_read_byte(&b)) {
        switch (state) {
        case RX_WAIT_START:
            if (b == START_BYTE) state = RX_VERSION;
            break;
        case RX_VERSION:
            current.version = b; state = RX_SEQUENCE; break;
        case RX_SEQUENCE:
            current.sequence = b; state = RX_DEVICE; break;
        case RX_DEVICE:
            current.device_id = b; state = RX_COMMAND; break;
        case RX_COMMAND:
            current.command = b; state = RX_FLAGS; break;
        case RX_FLAGS:
            current.flags = b; state = RX_LENGTH; break;
        case RX_LENGTH:
            current.length = b;
            if (current.length > FRAME_MAX_PAYLOAD) {
                /* A length this large can never be followed by a valid CRC
                 * for a real frame -- treat it as noise, not a fault worth
                 * counting (a genuinely corrupted length byte on an
                 * otherwise valid frame is caught by the CRC check below;
                 * this branch only guards the payload buffer). */
                state = RX_WAIT_START;
            } else {
                index = 0u; state = current.length ? RX_PAYLOAD : RX_CRC_H;
            }
            break;
        case RX_PAYLOAD:
            current.payload[index++] = b;
            if (index >= current.length) state = RX_CRC_H;
            break;
        case RX_CRC_H:
            crc_h = b; state = RX_CRC_L; break;
        case RX_CRC_L:
            crc_l = b; state = RX_END; break;
        case RX_END: {
            uint16_t received = (uint16_t)(((uint16_t)crc_h << 8) | crc_l);
            if (b == END_BYTE) {
                if (received == frame_crc16(&current)) {
                    publish_current();
                } else if (checksum_fault_count < 0xFFFFu) {
                    ++checksum_fault_count;
                }
            }
            state = RX_WAIT_START;
            break;
        }
        default:
            state = RX_WAIT_START;
            break;
        }
    }
}

bool frame_pop(frame_t *out) {
    if (ready_tail == ready_head) return false;
    *out = ready_queue[ready_tail];
    ready_tail = (uint8_t)((ready_tail + 1u) & (FRAME_QUEUE_DEPTH - 1u));
    return true;
}

void frame_send(const frame_t *f) {
    uart_write_byte(START_BYTE);
    uart_write_byte(f->version);
    uart_write_byte(f->sequence);
    uart_write_byte(f->device_id);
    uart_write_byte(f->command);
    uart_write_byte(f->flags);
    uart_write_byte(f->length);
    for (uint8_t i = 0u; i < f->length; ++i) uart_write_byte(f->payload[i]);
    uint16_t crc = frame_crc16(f);
    uart_write_byte((uint8_t)(crc >> 8));
    uart_write_byte((uint8_t)crc);
    uart_write_byte(END_BYTE);
}

void frame_send_ack(const frame_t *request, uint8_t error) {
    frame_t response = {0};
    response.version = PROTOCOL_VERSION;
    response.sequence = request->sequence;
    response.device_id = DEVICE_CONTROLLER_ID;
    response.command = error ? MSG_NACK : MSG_ACK;
    response.flags = 0u;
    response.length = 12u;
    response.payload[0] = request->command;
    response.payload[1] = error ? RESULT_ERROR : RESULT_OK;
    response.payload[2] = error;
    response.payload[3] = request->sequence;
    /* Echo transaction/correlation identifiers when supplied. */
    for (uint8_t i = 0u; i < 8u && (uint8_t)(i + 10u) < request->length; ++i)
        response.payload[4u + i] = request->payload[i];
    frame_send(&response);
}

void frame_send_fault(uint8_t fault_code, uint32_t uptime_ms) {
    frame_t f = {0};
    f.version = PROTOCOL_VERSION;
    f.sequence = 0u;
    f.device_id = DEVICE_CONTROLLER_ID;
    f.command = MSG_FAULT;
    f.flags = FLAG_PRIORITY_HIGH;
    f.length = 5u;
    f.payload[0] = fault_code;
    f.payload[1] = (uint8_t)(uptime_ms >> 24);
    f.payload[2] = (uint8_t)(uptime_ms >> 16);
    f.payload[3] = (uint8_t)(uptime_ms >> 8);
    f.payload[4] = (uint8_t)uptime_ms;
    frame_send(&f);
}
