---
description: Build (if needed) and program the firmware to the connected board with the configured flash command, then verify it runs
argument-hint: "[--no-build] [elf/hex path override]"
---

Program the target. Arguments: $ARGUMENTS

1. Read `.claude/firmware.json`. Required: `flash` command. If it is missing, do not improvise a destructive command - propose one using an installed open-source tool (OpenOCD, pyOCD, probe-rs, st-flash, esptool/idf.py, bossac, edbg) per the `flash-debug` skill, and ask the user to confirm (then offer to save it with `/fw-init`).
2. Unless `--no-build` is given, run the build first and stop on failure. Check that the ELF/HEX that will be flashed is the one just built (timestamp).
3. Show the exact command you are about to run, then run it. The kit's guard hook will ask for confirmation on erase/option-byte operations and block irreversible ones - never try to bypass it.
4. Parse the output: probe found? target ID? programmed and verified? Report clearly. On connection failure follow the "Probe cannot connect" ladder in the `flash-debug` skill, starting with non-destructive steps.
5. After success, if a console is configured (UART port in `notes`, or RTT), offer to capture the boot banner to confirm the new firmware runs.
