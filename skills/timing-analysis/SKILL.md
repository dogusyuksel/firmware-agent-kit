---
name: timing-analysis
description: Measure and reason about firmware timing - cycle counting with DWT/CCOUNT, GPIO toggling with a logic analyser, ISR latency and duration, FreeRTOS run-time stats and trace hooks, CPU load, stack/time budgets, jitter of periodic tasks, and WCET approaches with open-source tools. Use when the user asks how long something takes, about deadlines, jitter, CPU load, interrupt latency, or a timing/schedulability analysis.
---

# Timing analysis

Measure on the real target with optimisation settings of the release build; simulators (Renode/QEMU) are not cycle-accurate.

## Measuring
| Method | How | Notes |
|---|---|---|
| DWT cycle counter (Cortex-M3/M4/M7: STM32, SAMV71) | `CoreDebug->DEMCR \|= CoreDebug_DEMCR_TRCENA_Msk; DWT->CYCCNT = 0; DWT->CTRL \|= DWT_CTRL_CYCCNTENA_Msk;` then `t0 = DWT->CYCCNT; ...; dt = DWT->CYCCNT - t0;` | wraps at 2^32 cycles (unsigned subtraction handles one wrap); on Cortex-M7 some parts need `DWT->LAR = 0xC5ACCE55` to unlock; not on M0/M0+ |
| ESP32 cycle count | `esp_cpu_get_cycle_count()` (per core), `esp_timer_get_time()` (us) | cycle counts differ per core and frequency scaling (disable DFS while measuring) |
| GPIO toggle + logic analyser / scope | set pin at entry, clear at exit | best for ISR latency, nesting and jitter; sigrok/PulseView are open source |
| FreeRTOS run-time stats | `configGENERATE_RUN_TIME_STATS 1` + a fast counter (DWT or 10-100x tick timer), `vTaskGetRunTimeStats()` / `uxTaskGetSystemState()` | CPU load per task; idle share = free CPU |
| FreeRTOS trace hooks | `traceTASK_SWITCHED_IN/OUT`, `traceISR_ENTER` (port dependent) writing to a RAM ring buffer, dumped via RTT/UART | build your own timeline; keep hooks tiny |

Report: min/avg/max over many runs, conditions (clock, cache on/off, flash wait states, optimisation level).

## What to check
- **ISR budget**: duration of every ISR x worst-case rate. Total ISR load should leave headroom for tasks; long ISRs delay all lower-priority interrupts and the kernel.
- **Interrupt latency**: masking time of critical sections (`taskENTER_CRITICAL`, `__disable_irq`) is the main source; find the longest critical section.
- **Periodic tasks**: use `xTaskDelayUntil`; measure release jitter = actual start - ideal start. Jitter grows with higher-priority load and critical sections.
- **Response time**: event (pin edge) to reaction (output edge) end-to-end with a logic analyser.
- **Cache/flash effects** (SAMV71/STM32F7/H7 caches, STM32 ART accelerator, ESP32 flash cache): measure cold vs warm; place hard real-time code in TCM/RAM (`.ramfunc`, ESP `IRAM_ATTR`) if cold misses break deadlines.

## Schedulability (fixed-priority, FreeRTOS)
For periodic tasks with WCET C_i and period T_i (deadline = period), rate-monotonic priorities (shorter period = higher priority), the response time of task i is the smallest R_i with
`R_i = C_i + B_i + sum over higher-priority j of ceil(R_i / T_j) * C_j` (B_i = longest blocking by lower-priority tasks holding a mutex / critical sections; add ISR load as highest-priority "tasks"). Task meets its deadline if R_i <= T_i. Document assumptions; the inputs (C_i) come from measurement plus margin or from WCET analysis.

## WCET
- Measurement-based: high-water marks under worst-case inputs, with margin (e.g. +20-50 %) - acceptable for many projects if justified.
- Static WCET tools: OTAWA (LGPL, research-grade, ARM support) is open source; commercial tools (aiT, RapiTime) are not - mention only if the user already has them.
- Keep critical code WCET-friendly: bounded loops with fixed maxima, no recursion, no dynamic allocation, avoid data-dependent long paths.
