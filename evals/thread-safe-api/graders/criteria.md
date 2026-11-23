---
type: llm
weight: 1
---

A successful response:
- makes the read-and-reset atomic with respect to the ISR and to other tasks, e.g. `taskENTER_CRITICAL()`/`taskEXIT_CRITICAL()` (or masking the EXTI0 interrupt / BASEPRI) around reading and clearing `s_count`; a mutex alone is not enough because the ISR cannot take it;
- declares `s_count` `volatile` (or otherwise explains why the access is safe);
- keeps the ISR short and non-blocking (no mutex, no blocking RTOS call, no printf in the ISR);
- documents that the new function is thread-safe and is not meant to be called from an ISR (or provides a separate ISR-safe variant);
- does not change unrelated code (the existing ISR logic stays as it is apart from what thread safety requires) and keeps the existing naming style.
Fail if the read and the reset are two unprotected operations (lost pulses between them) or if a mutex is taken inside the ISR.
