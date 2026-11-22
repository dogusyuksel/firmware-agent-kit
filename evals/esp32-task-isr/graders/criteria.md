---
type: llm
weight: 1
---

A successful response:
- marks the ISR `IRAM_ATTR` (and explains why with ESP_INTR_FLAG_IRAM / flash cache disabled);
- protects the shared counter correctly for SMP: `portMUX_TYPE` spinlock initialised with `portMUX_INITIALIZER_UNLOCKED`, `portENTER_CRITICAL_ISR`/`portEXIT_CRITICAL_ISR` in the ISR and `portENTER_CRITICAL`/`portEXIT_CRITICAL` in the task (an atomic type is also acceptable), or uses a FromISR notification/queue instead;
- does not call ESP_LOGx/printf inside the ISR;
- creates the task with a stack size given in BYTES (e.g. >= 2048) and does not call `vTaskStartScheduler()`;
- the task blocks (vTaskDelay / xTaskDelayUntil with pdMS_TO_TICKS) rather than busy-waiting.
Fail if the ISR logs, lacks IRAM_ATTR, or the counter is accessed without any protection on a dual-core chip.
