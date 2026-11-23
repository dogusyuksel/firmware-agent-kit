#include "ring_buffer.h"

#include "osal.h"

/* The receive buffer stores bytes in FIFO order without locks */
void rb_init(ring_buffer_t *rb)
{
    rb->head = 0u;
    rb->tail = 0u;
    rb->overruns = 0u;
}

/* A full buffer rejects new bytes and counts the overrun */
bool rb_put(ring_buffer_t *rb, uint8_t byte)
{
    uint32_t head = rb->head;

    if ((uint32_t)(head - rb->tail) >= RB_CAPACITY)
    {
        rb->overruns++;
        return false;
    }
    rb->buf[head & (RB_CAPACITY - 1u)] = byte;
    osal_memory_barrier(); /* data before index */
    rb->head = head + 1u;
    return true;
}

bool rb_get(ring_buffer_t *rb, uint8_t *byte)
{
    uint32_t tail = rb->tail;

    if (tail == rb->head)
    {
        return false;
    }
    *byte = rb->buf[tail & (RB_CAPACITY - 1u)];
    osal_memory_barrier();
    rb->tail = tail + 1u;
    return true;
}

size_t rb_count(const ring_buffer_t *rb)
{
    return (size_t)(uint32_t)(rb->head - rb->tail);
}
