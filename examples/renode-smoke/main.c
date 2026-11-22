/* Minimal bare-metal STM32F407 firmware for the Renode smoke test: prints a banner on USART2
 * and echoes "version" requests. Register addresses: RM0090 (RCC 0x40023800, USART2 0x40004400). */
#include <stdint.h>

#define REG(addr) (*(volatile uint32_t *)(addr))
#define RCC_APB1ENR REG(0x40023840u)
#define USART2_SR REG(0x40004400u)
#define USART2_DR REG(0x40004404u)
#define USART2_BRR REG(0x40004408u)
#define USART2_CR1 REG(0x4000440Cu)
#define SR_RXNE (1u << 5)
#define SR_TXE (1u << 7)

extern uint32_t _estack;
void Reset_Handler(void);

__attribute__((section(".isr_vector"), used)) void (*const g_vectors[])(void) = {
    (void (*)(void))&_estack,
    Reset_Handler,
};

static void uart_putc(char c)
{
    uint32_t guard = 100000u;

    while (((USART2_SR & SR_TXE) == 0u) && (guard-- > 0u))
    {
    }
    USART2_DR = (uint32_t)(uint8_t)c;
}

static void uart_puts(const char *s)
{
    while (*s != '\0')
    {
        uart_putc(*s++);
    }
}

void Reset_Handler(void)
{
    char line[16];
    uint32_t n = 0u;

    RCC_APB1ENR |= (1u << 17);            /* USART2EN */
    USART2_BRR = 0x8Bu;                   /* 115200 @ 16 MHz HSI */
    USART2_CR1 = (1u << 13) | (1u << 3) | (1u << 2); /* UE | TE | RE */
    uart_puts("fw: boot ok\r\n");
    for (;;)
    {
        if ((USART2_SR & SR_RXNE) != 0u)
        {
            char c = (char)(USART2_DR & 0xFFu);
            if ((c == '\r') || (c == '\n'))
            {
                line[n] = '\0';
                if ((n == 7u) && (line[0] == 'v') && (line[6] == 'n'))
                {
                    uart_puts("v0.3.1\r\n");
                }
                n = 0u;
            }
            else if (n < (sizeof line - 1u))
            {
                line[n++] = c;
            }
        }
    }
}
