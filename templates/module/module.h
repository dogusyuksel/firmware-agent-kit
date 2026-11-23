/**
 * @file module.h
 * @brief <One sentence: what this module does.>
 *
 * Thread-safety: all functions may be called from any task unless noted.
 * ISR-safety: only functions ending in _from_isr may be called from interrupts.
 */
#ifndef MODULE_H
#define MODULE_H

#include <stdbool.h>
#include <stdint.h>

typedef enum
{
    MODULE_OK = 0,
    MODULE_ERR_PARAM = -1,
    MODULE_ERR_TIMEOUT = -2,
    MODULE_ERR_STATE = -3
} module_status_t;

/** Create locks and reset state. Call once before the scheduler starts. */
module_status_t module_init(void);

/** Example task-context API: blocks at most timeout_ms waiting for the lock. */
module_status_t module_get_value(uint32_t *out, uint32_t timeout_ms);

/** Called by the owning task after a notification: applies pending events. */
void module_process(void);

/** Example ISR entry point: never blocks; defers work to the owning task. */
void module_event_from_isr(uint32_t value);

#endif /* MODULE_H */
