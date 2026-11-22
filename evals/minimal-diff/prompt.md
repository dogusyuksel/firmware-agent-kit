---
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
---

Add a `timeout_ms` parameter to `uart_send()` so it gives up and returns -1 if the transmitter stays busy longer than that. Change only what is needed and show the resulting function.

```c
static uint32_t tx_count;

int uart_send(const uint8_t *buf, int len)
{
    for (int i = 0; i <= len; i++)
    {
        while (!(USART1->SR & USART_SR_TXE));
        USART1->DR = buf[i];
        tx_count++;
    }
    return 0;
}
```
