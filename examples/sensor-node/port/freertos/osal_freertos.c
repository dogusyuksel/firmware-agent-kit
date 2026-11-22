/* FreeRTOS implementation of osal.h for the target build (not compiled in host tests). */
#include "osal.h"

#include "FreeRTOS.h"
#include "semphr.h"
#include "task.h"

static StaticSemaphore_t s_mutex_storage;
static TaskHandle_t s_comm_task;

/* Init-time only: call before enabling the UART interrupt. */
void osal_register_comm_task(TaskHandle_t task)
{
    s_comm_task = task;
}

osal_status_t osal_mutex_create(osal_mutex_t *mutex)
{
    SemaphoreHandle_t h = xSemaphoreCreateMutexStatic(&s_mutex_storage);

    if (h == NULL)
    {
        return OSAL_ERROR;
    }
    *mutex = (osal_mutex_t)h;
    return OSAL_OK;
}

osal_status_t osal_mutex_lock(osal_mutex_t mutex, uint32_t timeout_ms)
{
    if (xSemaphoreTake((SemaphoreHandle_t)mutex, pdMS_TO_TICKS(timeout_ms)) != pdTRUE)
    {
        return OSAL_TIMEOUT;
    }
    return OSAL_OK;
}

void osal_mutex_unlock(osal_mutex_t mutex)
{
    (void)xSemaphoreGive((SemaphoreHandle_t)mutex);
}

void osal_notify_from_isr(bool *higher_priority_woken)
{
    BaseType_t woken = pdFALSE;

    if (s_comm_task != NULL)
    {
        vTaskNotifyGiveFromISR(s_comm_task, &woken);
    }
    *higher_priority_woken = (woken != pdFALSE);
}

void osal_yield_from_isr(bool higher_priority_woken)
{
    portYIELD_FROM_ISR(higher_priority_woken ? pdTRUE : pdFALSE);
}

uint32_t osal_ms(void)
{
    return (uint32_t)(xTaskGetTickCount() * portTICK_PERIOD_MS);
}

void osal_memory_barrier(void)
{
    __asm volatile("dmb" ::: "memory");
}
