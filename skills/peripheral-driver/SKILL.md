---
name: peripheral-driver
description: Workflow for writing or fixing register-level peripheral drivers (GPIO, UART, SPI, I2C, timers, ADC, DMA, CAN, USB) on MCUs from the reference manual and device headers. Use when creating a driver, porting one to another MCU, or replacing vendor HAL calls with direct register code.
---

# Register-level peripheral driver workflow

## Golden rule: never invent register facts
Register addresses, bit positions, reset values, clock tree paths and init sequences must come from a source: the vendor device header (`stm32f4xx.h`, `nrf52840.h`, CMSIS-SVD), the reference manual, or the datasheet. If you do not have the source:
1. Search the project for the device header / SVD (`grep -r "USART_CR1_UE" --include=*.h`).
2. Check `.claude/firmware.json` `datasheets` for document paths and read the relevant section (delegate long PDFs to the `datasheet-analyst` agent).
3. Otherwise ask the user for the document. State clearly which values are unverified.

Cite where each non-obvious value came from in a short comment: `/* RM0090 30.6.4: OVER8=0, BRR = fCK / baud */`.

## Step-by-step
1. **Identify the instance and its bus**: which peripheral instance, which bus (AHB/APB1/APB2), bus clock frequency after prescalers.
2. **Clock enable**: enable the peripheral clock in the RCC/CMU/CLOCK block. On STM32 read the register back (or `__DSB()`) after enabling before touching the peripheral (errata on several families).
3. **Reset (optional)**: pulse the peripheral reset bit for a known state when re-initialising.
4. **Pins**: enable the GPIO port clock, set mode (alternate function / analog), AF number from the datasheet's AF table (not the RM), output type (push-pull / open-drain for I2C), speed, pull-ups.
5. **Configure while disabled**: most peripherals require the enable bit (UE, SPE, PE, CEN) to be 0 while writing config registers.
6. **Compute dividers in code with integer math and check the error**: baud, prescalers, timer ARR/PSC. Add a `_Static_assert` or runtime check that the error is within tolerance (UART < 2 %).
7. **Enable**, then wait for ready flags with a timeout.
8. **Interrupts/DMA**: configure the peripheral's IRQ enable bits, then NVIC priority, then `NVIC_EnableIRQ`. Clear pending flags first to avoid an immediate spurious interrupt.
9. **Errata**: check the device errata sheet for the peripheral - many "driver bugs" are documented silicon bugs with workarounds.

## Register access patterns
- Read-modify-write a field: `REG = (REG & ~FIELD_Msk) | (value << FIELD_Pos);`
- Atomic GPIO: use BSRR/BRR (STM32), OUTSET/OUTCLR (nRF), never RMW on ODR from multiple contexts.
- **Write-1-to-clear (W1C)** flags: write only the bit you want to clear: `TIM2->SR = ~TIM_SR_UIF;` (for rc_w0) or `REG = FLAG;` (for W1C) - check which semantics the RM states. A RMW (`REG |= FLAG`) on a W1C register clears *all* pending flags.
- **Read-to-clear** sequences (e.g. STM32 USART: read SR then DR clears ORE; I2C ADDR: read SR1 then SR2). The debugger's register view can clear these behind your back.
- Some registers need specific access width (8/16-bit only on some SPI DR for 8-bit frames: `*(volatile uint8_t *)&SPI1->DR = b;` to avoid sending 16 bits).
- Reserved bits: preserve them (RMW) unless the RM says write 0.

## Driver API shape
```c
typedef enum { DRV_OK = 0, DRV_ERR_TIMEOUT, DRV_ERR_BUSY, DRV_ERR_PARAM, DRV_ERR_HW } drv_status_t;

typedef struct {
    uint32_t baud;
    /* ... config only, no hardware pointers leaked to callers ... */
} uart_cfg_t;

drv_status_t uart_init(uart_id_t id, const uart_cfg_t *cfg);
drv_status_t uart_write(uart_id_t id, const uint8_t *buf, size_t len, uint32_t timeout_ms); /* blocking */
drv_status_t uart_write_async(uart_id_t id, const uint8_t *buf, size_t len, uart_cb_t done); /* IRQ/DMA */
size_t       uart_read(uart_id_t id, uint8_t *buf, size_t max);  /* from RX ring buffer, non-blocking */
void         uart_deinit(uart_id_t id);
```
- Keep a per-instance context struct (`static uart_ctx_t ctx[UART_COUNT]`) holding the register base, ring buffers and state.
- Separate the thin register layer (`uart_ll.h`, static inline) from logic so logic can be unit-tested on the host with a fake register struct.
- Async APIs must define buffer ownership: the caller may not touch `buf` until `done` fires.

## DMA notes
- Buffers must be in DMA-accessible RAM (not CCM/DTCM on many STM32s - check the bus matrix).
- On Cortex-M7 with D-cache: clean cache before TX DMA (`SCB_CleanDCache_by_Addr`), invalidate after RX DMA; buffers 32-byte aligned and sized to whole cache lines - or place them in a non-cacheable MPU region.
- Clear all stream/channel flags before enabling; check transfer-error flags in the ISR.
- Circular RX DMA + idle-line interrupt is the robust pattern for UART receive.
