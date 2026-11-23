---
name: freertos
description: FreeRTOS and CMSIS-RTOS2 usage rules for firmware (Cortex-M ports) - ISR-safe APIs, interrupt priorities vs configMAX_SYSCALL_INTERRUPT_PRIORITY, scheduler state, critical sections, mutex vs semaphore, timers, queues/notifications, object lifecycle and heap schemes, task stacks. Use when writing, reviewing or debugging code that uses FreeRTOS or cmsis_os2.
---

# FreeRTOS / CMSIS-RTOS2 rules

The kit checks most of these automatically (`tools/rtos_check.py`, rule IDs `RTOS-xxx`, catalogue in `docs/RTOS_RULES.md`). The hook reports violations on lines you edit. Run project-level checks with `python <kit>/tools/rtos_check.py --project`.

## Execution contexts - know where code runs
| Context | Examples | May block? | API set |
|---|---|---|---|
| Before scheduler | `main()` before `vTaskStartScheduler()`/`osKernelStart()` | No | create objects/tasks only |
| Task | task functions | Yes | normal API |
| Timer service task | software timer callbacks | **No** (stalls all timers) | normal API with timeout 0 |
| ISR | `*_IRQHandler`, STM32 `HAL_*Callback` (IT/DMA mode), vendor driver callbacks, functions they call | Never | `...FromISR` only |
| Critical section / scheduler suspended | between `taskENTER_CRITICAL`/`EXIT`, `vTaskSuspendAll`/`xTaskResumeAll` | Never | no blocking or context-switching calls |

## ISR rules
- Only `...FromISR` APIs (CMSIS-RTOS2: only functions documented ISR-callable, with timeout 0). Never mutexes, delays, heap, create/delete.
- Pattern:
  ```c
  void USART2_IRQHandler(void) {
      BaseType_t woken = pdFALSE;                     /* must start pdFALSE */
      uint8_t b = (uint8_t)USART2->DR;
      (void)xQueueSendFromISR(rx_q, &b, &woken);      /* or xStreamBufferSendFromISR / vTaskNotifyGiveFromISR */
      portYIELD_FROM_ISR(woken);                      /* switch now if a higher-prio task woke */
  }
  ```
- Prefer direct-to-task notifications (fastest, no object) for "ISR wakes one task".
- **Cortex-M priority rule**: any ISR that calls a FreeRTOS API must have a priority numerically >= `configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY` (lower urgency). Reset default priority is 0 = highest = NOT allowed. Set every such IRQ explicitly. ISRs above that level (e.g. motor control) must not call any RTOS API but are never masked by the kernel.
- STM32: use `NVIC_PriorityGroup_4` (all bits preemption) - FreeRTOS assumes no sub-priorities.

## Synchronisation
- Mutex for mutual exclusion (priority inheritance); binary semaphore / notification for signalling. Never use a binary semaphore as a lock (priority inversion).
- Give a mutex on every path (early returns!). Same task must take and give. Recursive mutex only with `...Recursive` APIs.
- Critical sections: a few instructions, no loops, no API calls that block or yield.
- Lock ordering: acquire multiple mutexes in one global order (document it) to avoid deadlock.

## Objects and memory
- Check every dynamic create for NULL (`xQueueCreate`, `xSemaphoreCreate*`, `xTimerCreate`, `pvPortMalloc`) and `xTaskCreate` for `pdPASS`.
- Prefer static allocation for safety-critical code (`configSUPPORT_STATIC_ALLOCATION=1`, `...CreateStatic`); the `Static*_t` buffers and task stacks must be `static`/global, never locals.
- Heap scheme: `heap_1` never frees (no deletes allowed); `heap_4` coalesces (default choice); `heap_5` spans multiple RAM regions; `heap_3` wraps libc malloc. Do not mix `pvPortMalloc`/`free` or `malloc`/`vPortFree`.
- Deleted tasks' memory is freed by the idle task - never starve idle.
- Queues copy items by value: pass `&item`. Sending pointers transfers ownership - the buffer must stay valid until the receiver is done.
- Event groups: bits 24-31 are reserved (32-bit ticks).

## Tasks
- Signature `void task(void *arg)`; must never return: `for (;;) { ... }` or `vTaskDelete(NULL)` at the end.
- Every task loop must block (wait/receive/take/delay); busy loops starve lower priorities and the idle task.
- Periodic work: `xTaskDelayUntil(&last, period)` (no drift), not `vTaskDelay`.
- Stack depth is in **words** (not bytes) on FreeRTOS Cortex-M ports. Measure with `uxTaskGetStackHighWaterMark()`; enable `configCHECK_FOR_STACK_OVERFLOW=2` in development.
- `pvParameters` must point to static/global/heap data. On Cortex-M ports `main()`'s stack (MSP) is reused for interrupts after the scheduler starts.
- Priorities `< configMAX_PRIORITIES`; keep few distinct levels and document them.
- Times: `pdMS_TO_TICKS(ms)`, never raw tick numbers; at tick rates < 1000 Hz small values round to 0.

## Configuration sanity (FreeRTOSConfig.h)
`configASSERT` defined (trap), `configCHECK_FOR_STACK_OVERFLOW 2`, `configUSE_MALLOC_FAILED_HOOK 1`, `configKERNEL_INTERRUPT_PRIORITY` = lowest, `configMAX_SYSCALL_INTERRUPT_PRIORITY` != 0, `configPRIO_BITS` = `__NVIC_PRIO_BITS`, `configUSE_NEWLIB_REENTRANT 1` (or newlib lock hooks) if printf/malloc are used from several tasks, `configTIMER_TASK_PRIORITY` high enough and `configTIMER_QUEUE_LENGTH` sized for ISR deferrals.

## CMSIS-RTOS2 specifics
- `osKernelInitialize()` before creating any object; `osKernelStart()` does not return.
- `osDelay(ticks)` takes ticks, not ms (equal only at 1 kHz).
- From ISR: `osSemaphoreRelease`, `osMessageQueuePut/Get` (timeout 0), `osThreadFlagsSet`, `osEventFlagsSet/Clear`, `osSemaphoreAcquire` (timeout 0) - never `osMutex*`, `osDelay`, waits.
- Create mutexes with `osMutexPrioInherit` (and `osMutexRecursive` only if needed).

## Testing RTOS code
Hide the RTOS behind a thin OSAL (`osal_queue_send(...)`) so business logic stays portable and can run on the host (see `portable-architecture`).
