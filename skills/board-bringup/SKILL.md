---
name: board-bringup
description: Step-by-step bring-up of a new or custom MCU board or a new MCU port - power, debug connection, first blink, clock tree, UART console, then peripherals one by one, with a recorded checklist. Use when starting firmware for new hardware, porting to a different MCU, or when "nothing works" on a fresh board.
---

# Board bring-up

Go in strict order. Each step proves the layer below it. Do not move on with an unexplained anomaly. Keep a running log (`docs/bringup.md`) with date, board revision, measurements and results - offer to create it.

## 0. Gather facts first
- MCU exact part number (package matters for pins), board schematic revision, crystal/oscillator frequencies, power rails, debug connector pinout, boot pins.
- Reference manual, datasheet, errata, and the schematic. Record their paths in `.claude/firmware.json` `datasheets`.
- If anything is unknown, ask the user rather than assume (e.g. HSE 8 MHz vs 25 MHz silently breaks every baud rate).

## 1. Power and reset (hardware, before firmware)
- Rails measured at the MCU pins, ripple acceptable, NRST high, BOOT pins at intended levels, current draw sane (no short, no hot parts).

## 2. Debug connection
- Probe connects and reads the IDCODE / DBGMCU ID: `openocd ... -c "init; exit"`, `pyocd list`, `probe-rs info`, `st-info --probe`.
- Read and record device ID, flash size register, silicon revision (affects errata).

## 3. Minimal firmware: run from reset clock
- Startup + linker script for the exact part (flash/RAM sizes from the datasheet).
- `main` toggles one GPIO (LED or test pad) with a crude delay on the **reset clock** (HSI/internal RC). No PLL yet.
- Verify with scope/LED. Also step in GDB: reach `main`, check SP is in RAM, `.data` initialised.

## 4. Clock tree
- Configure HSE -> PLL -> SYSCLK carefully: flash wait states **before** raising the frequency, voltage scaling/regulator mode, bus prescalers within limits, timeouts on every ready flag with fallback to HSI.
- Output SYSCLK/N on the MCO pin and measure it. Re-run the blinky with a timer-based delay to confirm the timing.
- Record final clock values in one header (`clock_config.h`) - every driver derives dividers from these constants.

## 5. Console
- UART TX at a conservative baud (115200). Print a banner with build version, reset cause (RCC CSR flags - then clear them), device ID. Then add RX with an IRQ ring buffer.
- Alternative: RTT if no UART is routed.

## 6. Fault safety net
- Fault handlers that capture state (see `hardfault-debug`), watchdog (initially off during debugging, freeze in debug via DBGMCU), assert macro, stack painting.

## 7. Peripherals one at a time
For each: clock, pins, minimal register config, loopback or known-good device, scope/logic-analyser capture, then interrupt/DMA versions. Typical order: timers -> GPIO inputs/EXTI -> SPI/I2C sensors (read WHO_AM_I first) -> ADC (check reference voltage and sampling time) -> DMA -> USB/CAN/Ethernet -> low power.
I2C failing? Check pull-ups exist and the address is 7-bit vs 8-bit shifted. SPI garbage? Check CPOL/CPHA and CS timing on the analyser.

## 8. Close-out
- Update the bring-up log, list known hardware issues/rework, and add regression checks (self-test command, host tests for drivers' logic).
- Fill in `.claude/firmware.json` (build/flash/elf/memory) if not done - `/fw-init`.
