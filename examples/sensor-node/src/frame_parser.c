#include "frame_parser.h"

enum
{
    ST_SOF = 0,
    ST_LEN,
    ST_PAYLOAD,
    ST_CRC_HI,
    ST_CRC_LO
};

/* @req SN-FP-003 Frames use CRC-16/CCITT-FALSE over length and payload */
uint16_t frame_crc16(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFFu;

    for (size_t i = 0u; i < len; i++)
    {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (uint8_t bit = 0u; bit < 8u; bit++)
        {
            crc = ((crc & 0x8000u) != 0u) ? (uint16_t)((crc << 1) ^ 0x1021u) : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

void frame_parser_reset(frame_parser_t *p)
{
    p->state = ST_SOF;
    p->len = 0u;
    p->idx = 0u;
    p->crc_rx = 0u;
}

static frame_status_t finish(frame_parser_t *p)
{
    uint8_t buf[FRAME_MAX_PAYLOAD + 1u];
    uint16_t crc;

    buf[0] = p->len;
    for (uint8_t i = 0u; i < p->len; i++)
    {
        buf[i + 1u] = p->payload[i];
    }
    crc = frame_crc16(buf, (size_t)p->len + 1u);
    p->state = ST_SOF;
    return (crc == p->crc_rx) ? FRAME_OK : FRAME_ERR_CRC;
}

/* @req SN-FP-001 The parser resynchronises on the next start-of-frame byte after any error */
/* @req SN-FP-002 Frames longer than FRAME_MAX_PAYLOAD are rejected */
frame_status_t frame_parser_feed(frame_parser_t *p, uint8_t byte)
{
    frame_status_t status = FRAME_INCOMPLETE;

    switch (p->state)
    {
        case ST_SOF:
            if (byte == FRAME_SOF)
            {
                p->state = ST_LEN;
            }
            break;
        case ST_LEN:
            if ((byte == 0u) || (byte > FRAME_MAX_PAYLOAD))
            {
                p->state = ST_SOF;
                status = FRAME_ERR_LENGTH;
            }
            else
            {
                p->len = byte;
                p->idx = 0u;
                p->state = ST_PAYLOAD;
            }
            break;
        case ST_PAYLOAD:
            p->payload[p->idx] = byte;
            p->idx++;
            if (p->idx >= p->len)
            {
                p->state = ST_CRC_HI;
            }
            break;
        case ST_CRC_HI:
            p->crc_rx = (uint16_t)((uint16_t)byte << 8);
            p->state = ST_CRC_LO;
            break;
        case ST_CRC_LO:
            p->crc_rx |= byte;
            status = finish(p);
            break;
        default:
            frame_parser_reset(p);
            break;
    }
    return status;
}
