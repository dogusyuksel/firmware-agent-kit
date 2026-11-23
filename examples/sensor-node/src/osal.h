/**
 * @file osal.h
 * @brief Minimal OS abstraction so application code is portable and unit-testable.
 *
 * Implementations: port/freertos/osal_freertos.c (target); a host build can provide its own.
 * Functions ending in _from_isr are ISR-safe; all others are task-only and may block.
 */
#ifndef OSAL_H
#define OSAL_H

#include <stdbool.h>
#include <stdint.h>

typedef struct osal_mutex *osal_mutex_t;

typedef enum
{
    OSAL_OK = 0,
    OSAL_TIMEOUT = -1,
    OSAL_ERROR = -2
} osal_status_t;

osal_status_t osal_mutex_create(osal_mutex_t *mutex);
osal_status_t osal_mutex_lock(osal_mutex_t mutex, uint32_t timeout_ms);
void osal_mutex_unlock(osal_mutex_t mutex);
void osal_notify_from_isr(bool *higher_priority_woken);
void osal_yield_from_isr(bool higher_priority_woken);
uint32_t osal_ms(void);
void osal_memory_barrier(void);

#endif /* OSAL_H */
