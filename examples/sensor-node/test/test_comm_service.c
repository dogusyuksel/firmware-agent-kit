#include "unity.h"

#include "comm_service.h"
#include "frame_parser.h"
#include "mock_osal.h"
#include "ring_buffer.h"

void setUp(void)
{
    osal_memory_barrier_Ignore();
    osal_mutex_create_IgnoreAndReturn(OSAL_OK);
    TEST_ASSERT_EQUAL_INT(0, comm_init());
}

void tearDown(void)
{
}

static void rx_frame(const uint8_t *payload, uint8_t len, bool corrupt)
{
    uint8_t f[FRAME_MAX_PAYLOAD + 4u];
    uint16_t crc;

    f[0] = FRAME_SOF;
    f[1] = len;
    for (uint8_t i = 0u; i < len; i++)
    {
        f[2u + i] = payload[i];
    }
    crc = frame_crc16(&f[1], (size_t)len + 1u);
    f[2u + len] = (uint8_t)(crc >> 8);
    f[3u + len] = (uint8_t)(corrupt ? (uint8_t)~crc : (uint8_t)crc);
    for (uint8_t i = 0u; i < (uint8_t)(len + 4u); i++)
    {
        comm_rx_byte_from_isr(f[i]);
    }
}

/* @verifies SN-COM-001 */
void test_isr_byte_notifies_task_and_yields(void)
{
    osal_notify_from_isr_ExpectAnyArgs();
    osal_yield_from_isr_ExpectAnyArgs();
    comm_rx_byte_from_isr(0x7Eu);
}

/* @verifies SN-COM-002 */
void test_stats_count_good_and_bad_frames(void)
{
    const uint8_t payload[] = {1u, 2u};
    comm_stats_t st;

    osal_notify_from_isr_Ignore();
    osal_yield_from_isr_Ignore();
    osal_mutex_lock_IgnoreAndReturn(OSAL_OK);
    osal_mutex_unlock_Ignore();

    rx_frame(payload, 2u, false);
    rx_frame(payload, 2u, true);
    comm_process();

    TEST_ASSERT_EQUAL_INT(0, comm_get_stats(&st, 5u));
    TEST_ASSERT_EQUAL_UINT32(1u, st.frames_ok);
    TEST_ASSERT_EQUAL_UINT32(1u, st.frames_bad);
}

void test_get_stats_times_out_when_lock_busy(void)
{
    comm_stats_t st;

    osal_mutex_lock_ExpectAndReturn(NULL, 5u, OSAL_TIMEOUT);
    TEST_ASSERT_EQUAL_INT(-1, comm_get_stats(&st, 5u));
}

void test_get_stats_rejects_null(void)
{
    TEST_ASSERT_EQUAL_INT(-2, comm_get_stats(NULL, 5u));
}
