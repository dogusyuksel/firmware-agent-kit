/**
 * @file frame_parser.h
 * @brief Byte-stream parser for frames: 0x7E | len | payload[len] | crc16_hi | crc16_lo.
 *
 * Not thread-safe by itself: one parser instance belongs to one task (single owner).
 */
#ifndef FRAME_PARSER_H
#define FRAME_PARSER_H

#include <stddef.h>
#include <stdint.h>

#define FRAME_SOF 0x7Eu
#define FRAME_MAX_PAYLOAD 32u

typedef enum
{
    FRAME_INCOMPLETE = 0,
    FRAME_OK,
    FRAME_ERR_LENGTH,
    FRAME_ERR_CRC
} frame_status_t;

typedef struct
{
    uint8_t state;
    uint8_t len;
    uint8_t idx;
    uint16_t crc_rx;
    uint8_t payload[FRAME_MAX_PAYLOAD];
} frame_parser_t;

void frame_parser_reset(frame_parser_t *p);
frame_status_t frame_parser_feed(frame_parser_t *p, uint8_t byte);
uint16_t frame_crc16(const uint8_t *data, size_t len);

#endif /* FRAME_PARSER_H */
