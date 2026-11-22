/**
 * @file ring_buffer.h
 * @brief Lock-free single-producer / single-consumer byte ring buffer.
 *
 * ISR-safe: rb_put() from exactly one producer context (e.g. an ISR) and rb_get() from exactly
 * one consumer context (e.g. a task). Not safe for multiple producers or consumers.
 */
#ifndef RING_BUFFER_H
#define RING_BUFFER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define RB_CAPACITY 64u /* power of two */

typedef struct
{
    uint8_t buf[RB_CAPACITY];
    volatile uint32_t head; /* written only by the producer */
    volatile uint32_t tail; /* written only by the consumer */
    volatile uint32_t overruns;
} ring_buffer_t;

void rb_init(ring_buffer_t *rb);
bool rb_put(ring_buffer_t *rb, uint8_t byte);
bool rb_get(ring_buffer_t *rb, uint8_t *byte);
size_t rb_count(const ring_buffer_t *rb);

#endif /* RING_BUFFER_H */
