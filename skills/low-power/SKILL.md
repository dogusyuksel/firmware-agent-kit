---
name: low-power
description: Low-power design for bare-metal MCU firmware - sleep/stop/standby modes, WFI/WFE, wake-up sources, clock and peripheral gating, GPIO state in sleep, RTC wake-up, measuring current, and debugging firmware that never sleeps or never wakes. Use when optimising battery life or implementing sleep modes.
---

# Low-power firmware

## Principles
1. **Measure** with a proper tool (Joulescope, Otii, PPK2, uCurrent, or a shunt + scope). Never optimise blind; report uA before/after.
2. Average current = sum(mode current x time in mode). Usually the biggest wins are: sleeping more of the time, the deepest mode that still meets wake-up latency, and fixing leakage on GPIO/external parts.
3. Remove the debugger for real measurements - an attached probe keeps debug domains powered (and `DBGMCU` low-power debug bits keep clocks on).

## Mode selection (generic Cortex-M terms; names vary per vendor)
| Mode | Typical current | Keeps | Wake-up | Wake latency |
|---|---|---|---|---|
| Sleep (`WFI`, SLEEPDEEP=0) | mA | everything, CPU clock stopped | any IRQ | ~cycles |
| Stop / deep sleep (SLEEPDEEP=1) | uA | RAM, registers; most clocks off | EXTI, RTC, LPUART, LPTIM | us (clock restart!) |
| Standby / system off | < 1 uA | backup domain / retention RAM only | WKUP pin, RTC, reset | reset-like (boot again) |

After waking from Stop the system clock is usually the internal RC - **restore the PLL/clock config** before using peripherals with fixed baud/timing.
After Standby, check reset/wake flags at boot to distinguish wake from power-on.

## Entering sleep safely
```c
__disable_irq();
if (!work_pending()) {
    SCB->SCR |= SCB_SCR_SLEEPDEEP_Msk;   /* deep sleep; vendor PWR config before this */
    __DSB();
    __WFI();                             /* pending IRQ wakes the core even with PRIMASK set */
    SCB->SCR &= ~SCB_SCR_SLEEPDEEP_Msk;
    clock_restore_after_stop();
}
__enable_irq();                          /* the waking ISR runs here */
```
This avoids the race where an interrupt arrives between checking for work and sleeping.
`SLEEPONEXIT` is useful for purely interrupt-driven designs.

## Checklist for lowest current
- Unused GPIOs: analog mode (STM32) or disconnected input (nRF) - floating digital inputs leak. Mind pins driving external parts (LED on, pull-up fighting a driven-low pin).
- Peripheral clocks disabled when not used; ADC/DAC/comparators/VREFINT off; USB/PHYs powered down.
- External parts: sensors in their sleep mode, regulators' quiescent current, voltage dividers (use high values or switch them).
- Clocks: lowest frequency that meets deadlines, or race-to-sleep at high frequency - measure both. Regulator low-power/voltage-scaling modes.
- Flash: power-down in sleep options, wait states matched to frequency.
- Debug: `DBGMCU->CR` low-power debug bits cleared in production; SWD pins left in a non-leaking state.
- Timers: use LPTIM/RTC for wake-ups instead of SysTick; disable SysTick in deep sleep (or use tickless mode).

## Debugging power problems
- "Never sleeps": an IRQ keeps pending (uncleared flag), SysTick wakes it every ms, or a peripheral request keeps clocks on. Toggle a GPIO around `__WFI()` and look at it on a scope; read NVIC ISPR registers to find pending interrupts.
- "Never wakes": wake source not routed through EXTI/wake-up controller, wrong edge, its clock is off in that mode, or the IRQ is masked by NVIC rather than PRIMASK.
- Debugger loses connection in deep sleep: expected; enable DBGMCU low-power debug only during development, or connect under reset.
- Current higher than datasheet: compare with the datasheet's exact conditions (temperature, voltage, which clocks/RAM retained), then bisect by disabling subsystems.
