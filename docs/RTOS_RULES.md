# RTOS rule catalogue

Rules for FreeRTOS (vanilla Cortex-M: **V**), the CMSIS-RTOS2 wrapper (**C**) and ESP-IDF FreeRTOS SMP (**E**).

**Detection** levels:
- **Auto**: checked per file by `tools/rtos_check.py` and the edit hook.
- **Project**: needs FreeRTOSConfig.h, NVIC calls in other files, sdkconfig or the build tree. Run `rtos_check.py --project` or `fw_analyze.py --all`.
- **Review**: can't be checked statically. The `firmware-reviewer` agent uses these as a checklist.

All checks are heuristics, so false positives are possible. Suppress a finding by explaining it in review. Don't contort the code to satisfy the checker.

ISR context covers:
- `*_IRQHandler` and `*_Handler` functions;
- STM32 `HAL_*Callback` functions;
- ESP-IDF `IRAM_ATTR` handlers, handlers registered with `gpio_isr_handler_add` / `esp_intr_alloc`, and driver `.on_*` callbacks;
- `vApplicationTickHook`;
- functions matching `lint.isr_functions` in `.claude/firmware.json`;
- any function in the same file called from one of the above.

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
| IDF | https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/freertos_idf.html |
| IDF-ADD | https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/freertos_additions.html |
| IDF-INTR | https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/intr_alloc.html |
| IDF-WDT | https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/wdts.html |
| IDF-START | https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/startup.html |

## Automatically checked rules

| ID | Sev | Rule | Fl. | Detection | Source |
|---|---|---|---|---|---|
| RTOS-001 | error | No blocking API / `taskYIELD` in `main()` before `vTaskStartScheduler()`/`osKernelStart()` (also via called helpers) | V C | Auto | TS, OS2 |
| RTOS-003 | error | No `vTaskDelete(NULL)`/`vTaskSuspend(NULL)` before the scheduler runs | V C | Auto | TS |
| RTOS-008 | warn | Check `xTaskCreate*`/`osThreadNew` result | V C E | Auto | TC |
| RTOS-009 | warn | Stack size sane for the flavour (words on V, bytes on E) | V E | Auto | TC, IDF |
| RTOS-010 | error | Task priority < `configMAX_PRIORITIES` | V | Auto + config | CFG |
| RTOS-011 | error | ISR context calls only `...FromISR` variants | V E | Auto | TS, IDF |
| RTOS-014 | error | No mutex (or `osMutex*`) in ISR context | V C E | Auto | MTX, OS2-M |
| RTOS-015 | error | No blocking/heap/create/delete/yield API in ISR context | V C E | Auto | TS |
| RTOS-016 | warn | `xHigherPriorityTaskWoken` collected but no `portYIELD_FROM_ISR()` | V E | Auto | QSI |
| RTOS-017 | error | `xHigherPriorityTaskWoken` initialised to `pdFALSE` | V E | Auto | QSI |
| RTOS-018 | error/warn | IRQ whose handler calls RTOS APIs has priority >= `configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY` and is set explicitly (default 0 is invalid) | V C | Project | CM, TS |
| RTOS-019 | warn | IRQ using RTOS APIs enabled before the scheduler starts | V C | Project | TS |
| RTOS-020 | error | Priority grouping: all bits preemption (`NVIC_PRIORITYGROUP_4`) | V C | Project | CM, K-PORT |
| RTOS-021 | error | `NVIC_SetPriority` gets unshifted values (no `configMAX_SYSCALL_*`, no value > 2^bits-1) | V C | Project | CM |
| RTOS-022 | warn | Dynamic object handle checked for NULL after creation | V C E | Auto | TC, IDF |
| RTOS-024 | warn | Send/receive/take results checked when the timeout is finite (ISR sends too) | V C E | Auto | derived |
| RTOS-027 | warn | Binary semaphore not used as a lock (priority inversion) - use a mutex | V C E | Auto | BSEM, MTX |
| RTOS-029 | error/warn | Mutex released on every path (no `return` while held) | V C E | Auto | MTX |
| RTOS-030 | error | Recursive mutexes only with `...Recursive` APIs and vice versa | V E | Auto | RMTX, IDF |
| RTOS-037 | error | No blocking call in timer callbacks | V C E | Auto | TMR |
| RTOS-040 | warn | `xTimerStart/Stop/Reset/ChangePeriod` results checked (command queue full) | V E | Auto | TSTART |
| RTOS-041 | error | Timer period not 0 | V E | Auto | TMR |
| RTOS-043 | error | Timer callbacks do not issue timer commands with a block time | V E | Auto | TMR |
| RTOS-044 | error | Critical sections balanced; no `return` inside | V E | Auto | CRIT |
| RTOS-045 | error | ESP-IDF ISRs use `portENTER_CRITICAL_ISR` | E | Auto | IDF |
| RTOS-046 | error | No blocking/context-switching API inside critical sections | V E | Auto | CRIT, TS |
| RTOS-047 | warn | No loops inside critical sections (latency) | V E | Auto | CRIT, IDF-WDT |
| RTOS-049 | error | `vTaskSuspendAll`/`xTaskResumeAll` balanced | V E | Auto | SUSP |
| RTOS-050 | error | No blocking API while the scheduler is suspended | V E | Auto | SUSP |
| RTOS-055 | error | Non-recursive mutex not taken twice by the same function | V C E | Auto | MTX |
| RTOS-057 | warn | `configCHECK_FOR_STACK_OVERFLOW` enabled | V | Project | STK |
| RTOS-058 | warn | `pvPortMalloc` result checked | V E | Auto | MEM |
| RTOS-059 | error | No heap mixing (`pvPortMalloc`/`free`, `malloc`/`vPortFree`), no double free | V E | Auto | MEM |
| RTOS-062 | error/warn | Task parameter does not point to a caller's stack (main's MSP stack is reused) | V C E | Auto | TS |
| RTOS-063 | warn | Self-deleting task does not hold a mutex | V C E | Auto | TD, CFR |
| RTOS-070 | warn | Task loop blocks somewhere (no starvation of lower priorities / idle; ESP task WDT) | V C E | Auto | IDLE, IDF-WDT |
| RTOS-071 | warn | Task function never returns | V C E | Auto | IMPL |
| RTOS-073 | warn | Watchdog not fed from ISR/timer context | all | Auto | derived |
| RTOS-087 | warn | ISR does not use handles that a task creates (IRQ may fire first) | V C E | Auto | derived |
| RTOS-100 | error | No delete/free with heap_1 | V | Project | MEM |
| RTOS-101 | info | Deprecated names (`xTaskHandle`, `portTICK_RATE_MS`, `vSemaphoreCreateBinary`, ...) | V | Auto | K-FH |
| RTOS-102 | warn/info | Raw tick literals; use `pdMS_TO_TICKS()` (not `/ portTICK_PERIOD_MS`) | V C E | Auto | TS |
| RTOS-103 | error | Event group bits 24-31 reserved | V C E | Auto | EG |
| RTOS-104 | warn | `configASSERT` defined | V C | Project | TS, CFG |
| RTOS-105 | error/warn | Kernel/syscall priority config sane | V | Project | CM, CFG |
| RTOS-106 | warn | STM32 HAL timebase not SysTick when FreeRTOS uses SysTick (CubeMX recommendation) | V C | Project | CubeMX warning (no primary ST doc found) |
| RTOS-107 | warn | newlib reentrancy enabled when printf/malloc are used from tasks | V C | Project | CFG |
| RTOS-108 | error | CMSIS-RTOS2 calls from ISR use timeout 0 | C | Auto | OS2 |
| RTOS-109 | error | CMSIS-RTOS2 objects created after `osKernelInitialize()` | C | Auto | OS2 |
| RTOS-110 | error | ESP spinlocks initialised, static/global, passed to `portENTER_CRITICAL(&mux)` | E | Auto | IDF |
| RTOS-112 | warn | ESP SMP: `vTaskSuspendAll` / disabling interrupts is not mutual exclusion | E | Auto | IDF |
| RTOS-113 | error | `Static*_t` / `StackType_t` buffers for static creation are static/global | V C E | Auto | CFG |
| RTOS-114 | info | Malloc-failed hook enabled with dynamic allocation | V | Project | CFG |
| RTOS-115 | warn | `pdMS_TO_TICKS(x)` not rounding to 0 at the configured tick rate (ESP default 100 Hz) | V E | Project | TS, IDF |
| RTOS-116 | info | Cortex-M7 targets: confirm the ARM_CM7/r0p1 port requirement for the core revision | V | Project | K-M7 |
| RTOS-117 | error | Queue APIs receive a pointer to the item, not a value | V E | Auto | Q |
| RTOS-118 | error | `xQueueOverwrite` only on length-1 queues | V E | Auto | IDF |
| RTOS-119 | warn | Stream/message buffer: single writer (and reader) unless serialised | V E | Auto | SB, IDF-ADD |
| RTOS-120 | warn | Public functions that modify shared state are synchronised (thread-safe API) | all | Auto | project policy |
| RTOS-121 | warn | No raw `__disable_irq`/PRIMASK/BASEPRI in RTOS code - use kernel critical sections | V | Auto | TS |
| RTOS-122 | warn | ESP ring buffer items returned (`vRingbufferReturnItem`) | E | Auto | IDF-ADD |
| RTOS-123 | warn/error | CMSIS mutex attributes explicit (`osMutexPrioInherit`); no `osMutexRobust` on CMSIS-FreeRTOS; `osDelayUntil` absolute | C | Auto | OS2-M, CFR |
| RTOS-124 | info/warn | Avoid deleting other tasks (resources not released; SMP core race) | V E | Auto | TD, IDF |
| RTOS-125 | error | No `vTaskStartScheduler()` in ESP-IDF (`app_main` already runs in a task) | E | Auto | IDF-START |
| RTOS-126 | warn | One event-flag set per ISR (each posts to the timer queue) | V C | Auto | EGISR, CFR |
| RTOS-127 | error | Idle hook never blocks | V E | Auto | IDLE, HOOK |

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
- ESP high-priority interrupt levels 4-7 are written in assembly only.
- `ESP_INTR_FLAG_IRAM` handlers only touch IRAM/DRAM (`DRAM_ATTR` const data).

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
- ESP `esp_timer` callbacks are short; with ISR dispatch they follow ISR rules.

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

**ESP-IDF**
- Tasks are pinned where core affinity matters (only core 0 with `CONFIG_FREERTOS_UNICORE`).
- Different spinlocks are not nested.
- Tasks subscribed to the task watchdog reset it and unsubscribe before deletion.
- `app_main` locals are not shared if `app_main` returns.
- FPU is not used in ISRs unless `CONFIG_FREERTOS_FPU_IN_ISR` is set.

## Calibration
`tests/calibrate_corpus.py` runs all checkers on official example code: FreeRTOS `Demo/Common/Minimal` plus the STM32F407 and SAMV71 demos, ESP-IDF FreeRTOS and peripheral examples, and STM32CubeF4 FreeRTOS applications (about 200 files).

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
