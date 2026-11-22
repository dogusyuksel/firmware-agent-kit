---
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
---

In our STM32H7 + FreeRTOS firmware, switch UART3 reception from per-byte interrupts to circular DMA with idle-line detection, feeding the existing `comm_task` through a stream buffer. Go ahead.
