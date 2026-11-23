# RTOS rule catalogue

Rules for FreeRTOS on Cortex-M (**V**) and the CMSIS-RTOS2 wrapper (**C**).

**Detection** levels:
- **Auto**: checked per file by `tools/rtos_check.py` and the edit hook.
- **Project**: needs FreeRTOSConfig.h, NVIC calls in other files or the build tree. Run `rtos_check.py --project` or `fw_analyze.py --all`.
- **Review**: can't be checked statically. The `firmware-reviewer` agent uses these as a checklist.

All checks are heuristics, so false positives are possible. Suppress a finding by explaining it in review. Don't contort the code to satisfy the checker.

ISR context covers:
- `*_IRQHandler` and `*_Handler` functions;
- STM32 `HAL_*Callback` functions;
- `vApplicationTickHook`;
- functions matching `lint.isr_functions` in `.claude/firmware.json`;
- any function called from one of the above (in the same file; across files in `--project` mode).

Timer-callback context covers functions passed to `xTimerCreate*` / `osTimerNew`.

## Source keys
FR = https://www.freertos.org/Documentation/02-Kernel

| Key | Source |
|---|---|
| TS | https://www.freertos.org/Why-FreeRTOS/FAQs/Troubleshooting |
| CM | FR/03-Supported-devices/04-Demos/ARM-Cortex/RTOS-Cortex-M3-M4 |
| CFG | FR/03-Supported-devices/02-Customization |
| MEM | FR/02-Kernel-features/09-Memory-management/01-Memory-management |
| STK | FR/02-Kernel-features/09-Memory-management/02-Stack-usage-and-stack-overflow-checking |
| IDLE | FR/02-Kernel-features/01-Tasks-and-co-routines/15-Idle-task |
| IMPL | FR/02-Kernel-features/01-Tasks-and-co-routines/05-Implementing-a-task |
| TD | FR/04-API-references/01-Task-creation/03-vTaskDelete |
| CRIT | FR/04-API-references/04-RTOS-kernel-control/01-taskENTER_CRITICAL_taskEXIT_CRITICAL |
| SUSP | FR/04-API-references/04-RTOS-kernel-control/05-vTaskSuspendAll |
| MTX | FR/02-Kernel-features/02-Queues-mutexes-and-semaphores/04-Mutexes |
| RMTX | FR/02-Kernel-features/02-Queues-mutexes-and-semaphores/05-Recursive-mutexes |
| BSEM | FR/02-Kernel-features/02-Queues-mutexes-and-semaphores/02-Binary-semaphores |
| Q | FR/02-Kernel-features/02-Queues-mutexes-and-semaphores/01-Queues |
| QSI | FR/04-API-references/06-Queues/04-xQueueSendFromISR |
| TMR | FR/02-Kernel-features/05-Software-timers/01-Software-timers |
| TSTART | FR/04-API-references/11-Software-timers/04-xTimerStart |
| EG | FR/02-Kernel-features/06-Event-groups |
| EGISR | FR/04-API-references/12-Event-groups-or-flags/06-xEventGroupSetBitsFromISR |
| TN | FR/02-Kernel-features/03-Direct-to-task-notifications/01-Task-notifications |
| SB | FR/02-Kernel-features/04-Stream-and-message-buffers/01-RTOS-stream-and-message-buffers |
| HOOK | FR/02-Kernel-features/12-Hook-functions |
| K-FH | https://github.com/FreeRTOS/FreeRTOS-Kernel/blob/main/include/FreeRTOS.h |
| K-PORT | FreeRTOS-Kernel `portable/GCC/ARM_CM4F/port.c` (`vPortValidateInterruptPriority`, PRIGROUP assert) |
| K-M7 | https://github.com/FreeRTOS/FreeRTOS-Kernel/blob/main/portable/GCC/ARM_CM7/ReadMe.txt |
| OS2 | https://arm-software.github.io/CMSIS_6/latest/RTOS2/usingOS2.html (ISR-callable functions, init order) |
| OS2-M | https://arm-software.github.io/CMSIS_6/latest/RTOS2/group__CMSIS__RTOS__MutexMgmt.html |
| CFR | https://arm-software.github.io/CMSIS-FreeRTOS/main/page_technical_data.html |

## Automatically checked rules

| ID | Sev | Rule | Fl. | Detection | Source |
|---|---|---|---|---|---|
| RTOS-001 | error | No blocking API / `taskYIELD` in `main()` before `vTaskStartScheduler()`/`osKernelStart()` (also via called helpers) | V C | Auto | TS, OS2 |
| RTOS-003 | error | No `vTaskDelete(NULL)`/`vTaskSuspend(NULL)` before the scheduler runs | V C | Auto | TS |
| RTOS-008 | warn | Check `xTaskCreate*`/`osThreadNew` result | V C | Auto | TC |
| RTOS-009 | warn | Stack depth sane (in words) | V | Auto | TC |
| RTOS-010 | error | Task priority < `configMAX_PRIORITIES` | V | Auto + config | CFG |
| RTOS-011 | error | ISR context calls only `...FromISR` variants | V | Auto | TS |
| RTOS-014 | error | No mutex (or `osMutex*`) in ISR context | V C | Auto | MTX, OS2-M |
| RTOS-015 | error | No blocking/heap/create/delete/yield API in ISR context | V C | Auto | TS |
| RTOS-016 | warn | `xHigherPriorityTaskWoken` collected but no `portYIELD_FROM_ISR()` | V | Auto | QSI |
| RTOS-017 | error | `xHigherPriorityTaskWoken` initialised to `pdFALSE` | V | Auto | QSI |
| RTOS-018 | error/warn | IRQ whose handler calls RTOS APIs has priority >= `configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY` and is set explicitly (default 0 is invalid) | V C | Project | CM, TS |
| RTOS-019 | warn | IRQ using RTOS APIs enabled before the scheduler starts | V C | Project | TS |
| RTOS-020 | error | Priority grouping: all bits preemption (`NVIC_PRIORITYGROUP_4`) | V C | Project | CM, K-PORT |
| RTOS-021 | error | `NVIC_SetPriority` gets unshifted values (no `configMAX_SYSCALL_*`, no value > 2^bits-1) | V C | Project | CM |
| RTOS-022 | warn | Dynamic object handle checked for NULL after creation | V C | Auto | TC |
| RTOS-024 | warn | Send/receive/take results checked when the timeout is finite (ISR sends too) | V C | Auto | derived |
| RTOS-027 | warn | Binary semaphore not used as a lock (priority inversion) - use a mutex | V C | Auto | BSEM, MTX |
| RTOS-029 | error/warn | Mutex released on every path (no `return` while held) | V C | Auto | MTX |
| RTOS-030 | error | Recursive mutexes only with `...Recursive` APIs and vice versa | V | Auto | RMTX |
| RTOS-037 | error | No blocking call in timer callbacks | V C | Auto | TMR |
| RTOS-040 | warn | `xTimerStart/Stop/Reset/ChangePeriod` results checked (command queue full) | V | Auto | TSTART |
| RTOS-041 | error | Timer period not 0 | V | Auto | TMR |
| RTOS-043 | error | Timer callbacks do not issue timer commands with a block time | V | Auto | TMR |
| RTOS-044 | error | Critical sections balanced; no `return` inside | V | Auto | CRIT |
| RTOS-046 | error | No blocking/context-switching API inside critical sections | V | Auto | CRIT, TS |
| RTOS-047 | warn | No loops inside critical sections (latency) | V | Auto | CRIT |
| RTOS-049 | error | `vTaskSuspendAll`/`xTaskResumeAll` balanced | V | Auto | SUSP |
| RTOS-050 | error | No blocking API while the scheduler is suspended | V | Auto | SUSP |
| RTOS-055 | error | Non-recursive mutex not taken twice by the same function | V C | Auto | MTX |
| RTOS-057 | warn | `configCHECK_FOR_STACK_OVERFLOW` enabled | V | Project | STK |
| RTOS-058 | warn | `pvPortMalloc` result checked | V | Auto | MEM |
| RTOS-059 | error | No heap mixing (`pvPortMalloc`/`free`, `malloc`/`vPortFree`), no double free | V | Auto | MEM |
| RTOS-062 | error/warn | Task parameter does not point to a caller's stack (main's MSP stack is reused) | V C | Auto | TS |
| RTOS-063 | warn | Self-deleting task does not hold a mutex | V C | Auto | TD, CFR |
| RTOS-070 | warn | Task loop blocks somewhere (no starvation of lower priorities / idle) | V C | Auto | IDLE |
| RTOS-071 | warn | Task function never returns | V C | Auto | IMPL |
| RTOS-073 | warn | Watchdog not fed from ISR/timer context | all | Auto | derived |
| RTOS-087 | warn | ISR does not use handles that a task creates (IRQ may fire first) | V C | Auto | derived |
| RTOS-100 | error | No delete/free with heap_1 | V | Project | MEM |
| RTOS-101 | info | Deprecated names (`xTaskHandle`, `portTICK_RATE_MS`, `vSemaphoreCreateBinary`, ...) | V | Auto | K-FH |
| RTOS-102 | warn/info | Raw tick literals; use `pdMS_TO_TICKS()` (not `/ portTICK_PERIOD_MS`) | V C | Auto | TS |
| RTOS-103 | error | Event group bits 24-31 reserved | V C | Auto | EG |
| RTOS-104 | warn | `configASSERT` defined | V C | Project | TS, CFG |
| RTOS-105 | error/warn | Kernel/syscall priority config sane | V | Project | CM, CFG |
| RTOS-106 | warn | STM32 HAL timebase not SysTick when FreeRTOS uses SysTick (CubeMX recommendation) | V C | Project | CubeMX warning (no primary ST doc found) |
| RTOS-107 | warn | newlib reentrancy enabled when printf/malloc are used from tasks | V C | Project | CFG |
| RTOS-108 | error | CMSIS-RTOS2 calls from ISR use timeout 0 | C | Auto | OS2 |
| RTOS-109 | error | CMSIS-RTOS2 objects created after `osKernelInitialize()` | C | Auto | OS2 |
| RTOS-113 | error | `Static*_t` / `StackType_t` buffers for static creation are static/global | V C | Auto | CFG |
| RTOS-114 | info | Malloc-failed hook enabled with dynamic allocation | V | Project | CFG |
| RTOS-116 | info | Cortex-M7 targets: confirm the ARM_CM7/r0p1 port requirement for the core revision | V | Project | K-M7 |
| RTOS-117 | error | Queue APIs receive a pointer to the item, not a value | V | Auto | Q |
| RTOS-118 | error | `xQueueOverwrite` only on length-1 queues | V | Auto | Q |
| RTOS-119 | warn | Stream/message buffer: single writer (and reader) unless serialised | V | Auto | SB |
| RTOS-120 | warn | Public functions that modify shared state are synchronised (thread-safe API) | all | Auto | project policy |
| RTOS-121 | warn | No raw `__disable_irq`/PRIMASK/BASEPRI in RTOS code - use kernel critical sections | V | Auto | TS |
| RTOS-123 | warn/error | CMSIS mutex attributes explicit (`osMutexPrioInherit`); no `osMutexRobust` on CMSIS-FreeRTOS; `osDelayUntil` absolute | C | Auto | OS2-M, CFR |
| RTOS-124 | info | Avoid deleting other tasks (resources not released) | V | Auto | TD |
| RTOS-126 | warn | One event-flag set per ISR (each posts to the timer queue) | V C | Auto | EGISR, CFR |
| RTOS-127 | error | Idle hook never blocks | V | Auto | IDLE, HOOK |

## Review-only rules (checklist for `firmware-reviewer`)

**Lifecycle and memory**
- No object deleted while tasks may be blocked on it.
- Clear handles after delete; no use-after-delete.
- A deleted task's own allocations are released first.
- heap_2 is not used with varying-size create/delete.
- heap_5 has `vPortDefineHeapRegions()` called before the first allocation.
- `configTOTAL_HEAP_SIZE` covers all objects plus the idle and timer tasks; `vTaskStartScheduler()` returns if it does not.
- Code after `vTaskStartScheduler()` is treated as an error path.
- Worst-case stack and heap are verified (high-water marks, `xPortGetMinimumEverFreeHeapSize()`).

**ISR and priorities**
- `portYIELD_FROM_ISR` uses the same variable that was passed to the FromISR calls.
- No `*FromISR` calls from task context.
- No ISR large-stack usage (MSP is not covered by task stack checks).
- SVC, PendSV and SysTick are mapped to the port handlers.
- Cortex-M0: there is no BASEPRI, so critical sections mask everything.

**Synchronisation**
- Global lock ordering.
- Only the owner gives a mutex.
- Recursive mutex take/give counts balance.
- `portMAX_DELAY` is infinite only with `INCLUDE_vTaskSuspend=1`.
- Queue sets: receive only from the member returned by `xQueueSelectFromSet`; no mutexes in queue sets.
- Shared variables are protected (`volatile` is not synchronisation); 64-bit and other non-atomic data are accessed atomically.

**Queues, notifications, buffers**
- Queue item size matches the type sent; pointer payloads outlive the receive.
- A queue overflow policy is defined.
- Task notifications have one known receiver.
- Notification index 0 is not shared with stream buffers.
- Notification bits are not cleared by accident.
- Message-buffer capacity includes the length prefix.

**Timers**
- `configTIMER_QUEUE_LENGTH` and `configTIMER_TASK_PRIORITY` are sized for bursts and ISR deferrals.
- Timer callbacks are short.

**Tasks and timing**
- Periodic tasks use `xTaskDelayUntil`, with the wake time initialised once.
- Priorities are documented with rationale.
- Priority inversion analysed.
- Deadlines, WCET and jitter monitored for critical tasks.
- The watchdog is fed only when all tasks report health.
- Power management keeps task and interrupt synchronisation intact.
- Initialisation-order dependencies are documented.
- Fault recovery releases task resources.

**Configuration**
- `configUSE_MUTEXES`, `configUSE_RECURSIVE_MUTEXES`, `configUSE_TIMERS` and the `INCLUDE_*` macros match the APIs used.
- 16-bit ticks limit event groups to 8 bits.
- With `configSUPPORT_STATIC_ALLOCATION`, the idle and timer task memory callbacks are provided.
- CMSIS-FreeRTOS requirements are met: `configMAX_PRIORITIES == 56`, no optimised task selection, the required `INCLUDE_*` macros enabled.
- CMSIS-FreeRTOS limitations are respected:
  - message priority is ignored;
  - joinable threads are not supported;
  - `osEventFlagsWait` cannot be called from an ISR.
- With static allocation through the CMSIS wrapper, all memory blocks are supplied.

## Calibration
`tests/calibrate_corpus.py` runs all checkers on official example code: FreeRTOS `Demo/Common/Minimal` plus the STM32F407 and SAMV71 demos, and STM32CubeF4 FreeRTOS applications.

Target: **zero error-level findings** on this corpus. Warnings that remain there are real findings or policy findings:
- unchecked `xTaskCreate` / queue return values in demo code;
- vendor `SystemInit` busy-waits without timeouts;
- demo status functions that are not thread-safe.

The false-positive patterns found during calibration are frozen in the `RTOS_FP_REGRESSION` test. Run the script after changing any rule.

## Related research
- Chopra, Pai, D'Souza, "Data Races and Static Analysis for Interrupt-Driven Kernels", ESOP 2019 - https://link.springer.com/chapter/10.1007/978-3-030-17184-1_25
- Tulsyan, Pai, D'Souza, "Static Race Detection for RTOS Applications", FSTTCS 2020 - https://arxiv.org/abs/2010.02642
- SDRacer: interrupt race detection - https://arxiv.org/abs/2305.17869
- FreeRTOS kernel MISRA C:2012 notes (kernel only, not application usage) - https://github.com/FreeRTOS/FreeRTOS-Kernel/blob/main/MISRA.md
- No ready-made FreeRTOS API-misuse rule set was found in cppcheck, clang-tidy or semgrep; this catalogue fills that gap heuristically.
