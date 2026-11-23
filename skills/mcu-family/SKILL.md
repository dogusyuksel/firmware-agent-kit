---
name: mcu-family
description: Family-specific facts for Cortex-M microcontrollers - vendor frameworks and generated code, clocks and flash wait states, NVIC priority bits with FreeRTOS, cache/DMA/TCM, boot modes and protection, reset-time traps. One reference file per family (STM32, SAM V71/E70/S70). Use when code depends on the exact MCU family, its vendor HAL/generator, or its clock, memory or boot setup.
---

# MCU family notes

1. Identify the family: `family` in `.claude/firmware.json`, else device headers (`stm32*.h`, `sam*.h`), linker script or build defines.
2. Read only the matching reference file in this folder:

| Family | File |
|---|---|
| STM32 (all series) | `stm32.md` |
| SAM V71 / V70 / E70 / S70 | `samv71.md` |

3. These files are reminders, not sources. Verify register names and values against the reference manual, datasheet and errata for the exact part and silicon revision (see `hardware-docs`).
4. Family not listed: use the generic checks below plus the vendor documents; do not guess vendor specifics.

## Checks for any Cortex-M family
- Raise flash wait states / voltage scaling **before** increasing the core clock; every clock-ready wait has a timeout.
- `__NVIC_PRIO_BITS` sets FreeRTOS `configPRIO_BITS`; IRQs that call FromISR APIs need a priority numerically >= the max syscall priority.
- Cortex-M0/M0+: no BASEPRI (critical sections mask everything), no unaligned access, 2 priority bits.
- Cortex-M7 (and M33/M55 with cache): clean/invalidate D-cache around DMA, or use an MPU non-cacheable region.
- Know the watchdog state at reset (some families start it enabled).
- Vendor driver and generated code is read-only: wrap it, change generator settings instead of generated files.

## Project customization
- **Add a family:** copy an existing reference file to `<family>.md` with the same section order (generated code/frameworks, clocks and flash, interrupts and RTOS, memory/DMA/cache, boot and protection, pitfalls) and add a row to the table.
- **Project facts** (part number, board, clock tree, pin map, IRQ priorities, memory map) belong in the project's `CLAUDE.md` or `.claude/fw-notes.md`, not in this skill.
