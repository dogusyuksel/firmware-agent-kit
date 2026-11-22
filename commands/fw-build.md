---
description: Build the firmware with the project's configured command, triage warnings/errors and report flash/RAM usage
argument-hint: "[clean | release | extra build args]"
---

Build the firmware. Arguments: $ARGUMENTS

1. Read `.claude/firmware.json`. Use its `build` command (and `clean` first if the arguments contain "clean"). If there is no config, detect the build command (CMake/Make/IDE headless build), tell the user which one you are using and suggest `/fw-init`.
2. Run the build. Capture all output.
3. If it fails: identify the **first** real error (later errors are often cascades), open the relevant source, explain the cause and propose (or, if it is clearly within the current task, apply) the fix. Rebuild until clean or until a decision is needed from the user.
4. Warnings: list new/relevant warnings grouped by type. Treat these as likely bugs in firmware: `-Wimplicit-function-declaration`, `-Wint-conversion`, `-Wincompatible-pointer-types`, `-Warray-bounds`, `-Wstringop-overflow`, `-Wmaybe-uninitialized`, `-Wshift-count-overflow`, `-Wdouble-promotion`, `-Wstack-usage`. Do not fix warnings in vendor code.
5. Linker errors: `region ... overflowed` -> summarise using the `memory-footprint` skill; `undefined reference` -> missing source/library or wrong name; `multiple definition` -> header definitions / `-fno-common`.
6. Report: result, the size line from the size hook (flash/RAM, delta, % used), and any follow-ups.
