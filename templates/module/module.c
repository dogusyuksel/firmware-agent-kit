#include "module.h"

#include <stddef.h>

#include "osal.h" /* project RTOS abstraction; replace with the project lock API */

static osal_mutex_t s_lock;
static volatile uint32_t s_pending; /* written by the ISR, read by the task */
static uint32_t s_value;            /* protected by s_lock */
static bool s_ready;

module_status_t module_init(void)
{
    s_pending = 0u;
    s_value = 0u;
    if (osal_mutex_create(&s_lock) != OSAL_OK)
    {
        return MODULE_ERR_STATE;
    }
    s_ready = true;
    return MODULE_OK;
}

module_status_t module_get_value(uint32_t *out, uint32_t timeout_ms)
{
    if (out == NULL)
    {
        return MODULE_ERR_PARAM;
    }
    if (!s_ready)
    {
        return MODULE_ERR_STATE;
    }
    if (osal_mutex_lock(s_lock, timeout_ms) != OSAL_OK)
    {
        return MODULE_ERR_TIMEOUT;
    }
    *out = s_value;
    osal_mutex_unlock(s_lock);
    return MODULE_OK;
}

void module_process(void)
{
    uint32_t v = s_pending;

    if (osal_mutex_lock(s_lock, 10u) == OSAL_OK)
    {
        s_value = v;
        osal_mutex_unlock(s_lock);
    }
}

void module_event_from_isr(uint32_t value)
{
    bool woken = false;

    s_pending = value; /* single word: atomic on Cortex-M */
    osal_notify_from_isr(&woken);
    osal_yield_from_isr(woken);
}
