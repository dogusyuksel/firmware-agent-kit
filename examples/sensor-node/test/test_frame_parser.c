#include "unity.h"

#include "frame_parser.h"

static frame_parser_t p;

static frame_status_t feed_all(const uint8_t *data, size_t len)
{
    frame_status_t st = FRAME_INCOMPLETE;

    for (size_t i = 0u; i < len; i++)
    {
        st = frame_parser_feed(&p, data[i]);
    }
    return st;
}

static size_t build_frame(uint8_t *out, const uint8_t *payload, uint8_t len)
{
    uint16_t crc;

    out[0] = FRAME_SOF;
    out[1] = len;
    for (uint8_t i = 0u; i < len; i++)
    {
        out[2u + i] = payload[i];
    }
    crc = frame_crc16(&out[1], (size_t)len + 1u);
    out[2u + len] = (uint8_t)(crc >> 8);
    out[3u + len] = (uint8_t)crc;
    return (size_t)len + 4u;
}

void setUp(void)
{
    frame_parser_reset(&p);
}

void tearDown(void)
{
}

/* @verifies SN-FP-003 */
void test_crc16_ccitt_false_check_value(void)
{
    const uint8_t check[] = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};

    TEST_ASSERT_EQUAL_HEX16(0x29B1u, frame_crc16(check, sizeof check));
}

void test_valid_frame_is_accepted(void)
{
    const uint8_t payload[] = {0x10u, 0x20u, 0x30u};
    uint8_t f[8];
    size_t n = build_frame(f, payload, 3u);

    TEST_ASSERT_EQUAL(FRAME_OK, feed_all(f, n));
    TEST_ASSERT_EQUAL_UINT8_ARRAY(payload, p.payload, 3u);
}

void test_corrupted_crc_is_rejected(void)
{
    const uint8_t payload[] = {0x01u};
    uint8_t f[8];
    size_t n = build_frame(f, payload, 1u);

    f[n - 1u] ^= 0xFFu;
    TEST_ASSERT_EQUAL(FRAME_ERR_CRC, feed_all(f, n));
}

/* @verifies SN-FP-002 */
void test_oversized_length_is_rejected(void)
{
    const uint8_t f[] = {FRAME_SOF, (uint8_t)(FRAME_MAX_PAYLOAD + 1u)};

    TEST_ASSERT_EQUAL(FRAME_ERR_LENGTH, feed_all(f, sizeof f));
}

/* @verifies SN-FP-001 */
void test_parser_resynchronises_after_garbage(void)
{
    const uint8_t payload[] = {0x55u};
    uint8_t f[16] = {0x00u, 0x13u, FRAME_SOF, 0x00u}; /* noise, then SOF with invalid length */
    size_t n = build_frame(&f[4], payload, 1u);

    TEST_ASSERT_EQUAL(FRAME_OK, feed_all(f, n + 4u));
}
