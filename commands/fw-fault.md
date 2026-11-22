---
description: Analyse a Cortex-M HardFault / crash dump - decode fault registers, map PC/LR to source and find the root cause
argument-hint: "[paste CFSR/HFSR/BFAR/PC/LR... or a crash log]"
---

Analyse this crash: $ARGUMENTS

1. If the user pasted register values or a crash log, extract CFSR, HFSR, MMFAR, BFAR, EXC_RETURN/LR, stacked PC/LR/xPSR, SP.
2. If nothing was pasted, explain how to capture the evidence (GDB commands or the capturing HardFault handler from the `hardfault-debug` skill) and offer to add the handler to the project. If a GDB server is already running, you may read the registers with a batch-mode GDB command (read-only: no `load`, no erase).
3. Delegate the analysis to the `fault-investigator` agent with all evidence plus the ELF path from `.claude/firmware.json`.
4. Present: fault type, location (file:line), root cause with confidence, fix, and how to verify. Propose the fix as a diff; apply only after the user agrees.
