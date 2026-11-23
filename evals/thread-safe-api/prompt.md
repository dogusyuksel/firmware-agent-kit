---
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

STM32F4 with FreeRTOS. This module counts pulses in an EXTI interrupt. Add a public function `uint32_t pulse_get_and_reset(void)` that application tasks call to read the count and reset it to zero. Show the final code of the whole module.

```c
/* pulse.c */
#include "pulse.h"
#include "stm32f4xx.h"

static uint32_t s_count;

void EXTI0_IRQHandler(void)
{
    EXTI->PR = EXTI_PR_PR0;
    s_count++;
}
```
