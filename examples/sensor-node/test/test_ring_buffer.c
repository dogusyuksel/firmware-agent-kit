#include "unity.h"

#include "mock_osal.h"
#include "ring_buffer.h"

static ring_buffer_t rb;

void setUp(void)
{
    osal_memory_barrier_Ignore();
    rb_init(&rb);
}

void tearDown(void)
{
}

/* @verifies SN-RB-001 */
void test_bytes_come_out_in_fifo_order(void)
{
    uint8_t b = 0u;

    TEST_ASSERT_TRUE(rb_put(&rb, 1u));
    TEST_ASSERT_TRUE(rb_put(&rb, 2u));
    TEST_ASSERT_EQUAL_UINT32(2u, rb_count(&rb));
    TEST_ASSERT_TRUE(rb_get(&rb, &b));
    TEST_ASSERT_EQUAL_UINT8(1u, b);
    TEST_ASSERT_TRUE(rb_get(&rb, &b));
    TEST_ASSERT_EQUAL_UINT8(2u, b);
    TEST_ASSERT_FALSE(rb_get(&rb, &b));
}

/* @verifies SN-RB-002 */
void test_full_buffer_rejects_and_counts_overrun(void)
{
    for (uint32_t i = 0u; i < RB_CAPACITY; i++)
    {
        TEST_ASSERT_TRUE(rb_put(&rb, (uint8_t)i));
    }
    TEST_ASSERT_FALSE(rb_put(&rb, 0xAAu));
    TEST_ASSERT_EQUAL_UINT32(1u, rb.overruns);
    TEST_ASSERT_EQUAL_UINT32(RB_CAPACITY, rb_count(&rb));
}

void test_indices_survive_wraparound(void)
{
    uint8_t b = 0u;

    rb.head = 0xFFFFFFFEu;
    rb.tail = 0xFFFFFFFEu;
    TEST_ASSERT_TRUE(rb_put(&rb, 7u));
    TEST_ASSERT_TRUE(rb_put(&rb, 8u));
    TEST_ASSERT_TRUE(rb_put(&rb, 9u));
    TEST_ASSERT_EQUAL_UINT32(3u, rb_count(&rb));
    TEST_ASSERT_TRUE(rb_get(&rb, &b));
    TEST_ASSERT_EQUAL_UINT8(7u, b);
}
