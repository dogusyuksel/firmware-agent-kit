---
type: llm
weight: 1
---

A successful response:
- uses `xQueueSendFromISR` (not `xQueueSend`) inside the ISR;
- declares `BaseType_t` higher-priority-woken variable initialised to `pdFALSE`, passes its address, and calls `portYIELD_FROM_ISR(...)` with it at the end;
- handles or at least checks the send result (queue full / overrun) rather than ignoring it silently;
- states that the USART2 IRQ priority must be numerically >= `configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY` (or equivalent wording about configMAX_SYSCALL_INTERRUPT_PRIORITY) and must be set explicitly (default 0 is not allowed);
- does not call blocking APIs, printf or HAL_Delay in the ISR.
Fail if the handler uses a non-FromISR queue API or omits the priority requirement entirely.
