---
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

I'm on an STM32F4 with FreeRTOS. Complete this UART interrupt handler so every received byte is pushed into `rx_queue` (a FreeRTOS queue of uint8_t) and the `comm_task` waiting on that queue runs as soon as possible. Show the final handler code and anything else I must configure so it works reliably.

```c
extern QueueHandle_t rx_queue;

void USART2_IRQHandler(void)
{
    if (USART2->SR & USART_SR_RXNE)
    {
        uint8_t b = (uint8_t)USART2->DR;
        /* TODO */
    }
}
```
