# STM32 reference

## Generated code (CubeMX / CubeIDE)
- Edit only between `/* USER CODE BEGIN x */` and `/* USER CODE END x */`; everything else is regenerated from the `.ioc`. The kit's edit guard asks before edits outside these blocks.
- Peripheral/clock/pin changes belong in the `.ioc` (tell the user to regenerate) - do not hand-edit `MX_*_Init` outside user blocks.
- Never modify `Drivers/STM32xx_HAL_Driver` or `Drivers/CMSIS`; wrap instead.
- Generated Makefile/CMake: read with `tools/build_info.py`; CubeIDE managed builds need the CMake export or `bear`.

## HAL, LL, registers
- HAL: portable, heavy, blocking APIs use `HAL_GetTick` timeouts. LL: thin inline register wrappers. Registers via `stm32xxxx.h` `_Msk/_Pos` macros. Mixing is fine per peripheral.
- `HAL_*Callback` functions (`HAL_UART_RxCpltCallback`, `HAL_GPIO_EXTI_Callback`, `HAL_TIM_PeriodElapsedCallback`, ...) run **in interrupt context** when started with `_IT`/`_DMA` APIs -> ISR rules apply (FromISR APIs only, no blocking, no printf).
- HAL handle structs are not thread-safe: one owner task per peripheral, or protect with a mutex.
- `HAL_UART_Receive_IT` one byte at a time is fragile; prefer `HAL_UARTEx_ReceiveToIdle_DMA` with a circular buffer.

## FreeRTOS on STM32
- **HAL timebase must not be SysTick** when FreeRTOS owns SysTick: CubeMX SYS > Timebase Source = TIM6/TIM7 (`stm32xx_hal_timebase_tim.c`).
- Priority grouping 4 (`HAL_NVIC_SetPriorityGrouping(NVIC_PRIORITYGROUP_4)`), `configPRIO_BITS 4`, `configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY 5` (Cube default): IRQs calling FromISR APIs need `HAL_NVIC_SetPriority(x, >=5, 0)`.
- Cube wraps FreeRTOS in CMSIS-RTOS2 (`cmsis_os2.c`); `osDelay` is in ticks.
- newlib + FreeRTOS: enable `configUSE_NEWLIB_REENTRANT` / Cube's "newlib reentrant" option, or avoid printf/malloc in tasks.

## Clocks, flash, power
- Raise flash wait states (`FLASH->ACR LATENCY`) and voltage scaling **before** increasing SYSCLK; lower them after decreasing.
- Every `RCC` ready-flag wait needs a timeout; fall back to HSI on HSE failure (CSS).
- Read back an RCC enable register after enabling a peripheral clock before using it (errata on several families).

## Memory, DMA, cache (F7/H7)
- H7: DMA1/DMA2 cannot reach DTCM (0x20000000); put DMA buffers in AXI SRAM / SRAM1-3 via linker sections; BDMA only reaches SRAM4.
- D-cache: clean before TX DMA, invalidate after RX DMA, 32-byte aligned buffers sized in whole cache lines, or an MPU non-cacheable region.
- CCM RAM (F3/F4/G4) is CPU-only: no DMA.

## Option bytes, boot, protection
- BOOT0 pin + option bytes select boot (flash / system bootloader / SRAM). System bootloader = UART/USB DFU recovery path.
- RDP Level 1 -> 0 performs a mass erase; **Level 2 is permanent** (the kit denies it). WRP/PCROP also lock regions.

## Family differences that bite
- M0/M0+ (F0, G0, L0, C0): no BASEPRI (critical sections mask all), no unaligned access, no hardware divide on M0, 2 priority bits.
- G4/L4/L5/U5/H5: several flash/DMA/MUX differences (DMAMUX request IDs), TrustZone on L5/U5/H5 (secure/non-secure projects).
- Check the errata sheet for the exact silicon revision (`DBGMCU->IDCODE`).
