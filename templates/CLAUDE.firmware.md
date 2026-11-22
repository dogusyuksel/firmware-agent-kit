## Firmware project facts

- **Target:** <part number> (<core>, <flash> KB flash / <ram> KB RAM), board <name/rev>, family <stm32|esp32|samv71>
- **RTOS:** <FreeRTOS native | CMSIS-RTOS2 | none>, config `<path to FreeRTOSConfig.h>`, tick <Hz>
- **Clocks:** <crystal> MHz -> SYSCLK <y> MHz; bus clocks <...>
- **Build:** `<build command>` -> `<elf path>`; compile DB `<path>`
- **Flash/debug:** probe <ST-LINK/CMSIS-DAP/EDBG/USB-JTAG>, `<flash command>`, GDB server `<command>`
- **Tests:** unit `<ceedling test:all>`, integration `<renode-test ...>`
- **Console:** <UART/RTT, pins, baud>
- **Docs:** <datasheet, reference manual, errata, schematic paths>

## Rules for this codebase

- Minimal diffs: change only what the task needs; report other issues instead of fixing them.
- Match the existing style of the module you touch (naming, error codes, comments, formatting).
- Public functions are thread-safe and document ISR-safety; ISR-callable functions end in `_from_isr`.
- ISRs only use `...FromISR` RTOS APIs, never block, and defer work to tasks (notifications/queues).
- IRQs that call RTOS APIs have priority >= `configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY`; priorities are defined only in `<irq_prio.h>`.
- No dynamic allocation after init; RTOS objects are created (and checked) before the scheduler starts.
- Every hardware wait has a timeout; every driver function returns a status code.
- Generated code: edit only inside `USER CODE BEGIN/END` (CubeMX) / do not edit Harmony `config/default`; vendor code is never modified.
- Host unit tests must pass before committing; run `/fw-analyze` on changed files.
- Never run mass erase, option-byte, GPNVM, eFuse or RDP commands without explicit approval.
