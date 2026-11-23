---
name: static-analysis
description: Static and dynamic analysis of firmware with free/open-source tools - the kit's fw_analyze (embedded lint + RTOS rules), cppcheck with the MISRA C:2012 addon, clang-tidy, clang-format, plus leak/memory checks (sanitizers, FreeRTOS heap/stack monitoring). Use when asked to analyse, audit, check MISRA compliance or find leaks.
---

# Static and dynamic analysis

## One command first
```sh
python <kit>/tools/fw_analyze.py                    # changed files, changed lines (cheap; default)
python <kit>/tools/fw_analyze.py --all              # whole project incl. project-level RTOS rules
python <kit>/tools/fw_analyze.py --misra src/x.c    # + MISRA C:2012 (cppcheck addon)
```
It runs whatever is installed, uses `compile_commands.json` for include paths/defines, de-duplicates, and prints one compact list. Missing tools are reported as notes: show the install command (`tools/fw_doctor.py --for analysis`) and ask once; the user installs it, otherwise skip. Prefer this over running tools by hand (less output, fewer tokens).

Report pre-existing findings in untouched code to the user; fix only what the task covers.

Tools are found on PATH. Kit findings are heuristics: confirm each against the code before changing anything. Integer-to-float narrowing warnings from clang-tidy are disabled by default (lossless for typical ADC/sensor widths).

## Tools and what they are good at
| Tool | Finds | Notes |
|---|---|---|
| kit lint + `rtos_check.py` | ISR misuse, RTOS API rules (RTOS-xxx), volatile/timeout/stack issues (EMB-xxx) | heuristic, no build needed |
| cppcheck | UB, null deref, leaks, out-of-bounds, uninitialised vars | `--platform=unix32` approximates 32-bit MCUs; suppress inline with `// cppcheck-suppress id` |
| cppcheck `--addon=misra` | MISRA C:2012 rule IDs | rule *texts* are copyrighted: point `analysis.misra_rules_file` at your licensed text file, or output shows only IDs |
| clang-tidy | clang static analyzer (path-sensitive), bugprone, cert | cross-compile flags: `--extra-arg=--target=arm-none-eabi`; GCC-only flags may need `-Wno-unknown-warning-option` (fw_analyze adds them) |
| clang-format | style drift | changed lines only (`tools/fw_format.py`); never reformat whole legacy files unasked |
| GCC itself | `-Wall -Wextra -Wshadow -Wconversion -Wdouble-promotion -Wformat=2 -Wnull-dereference -fanalyzer` (GCC 12+ `-fanalyzer` is decent for C) | free and already installed |

## MISRA workflow
1. Agree the scope with the user: mandatory/required/advisory, deviations process.
2. `fw_analyze.py --misra --all` (or per module). Group findings by rule; most noise comes from a few rules (10.x essential types, 11.x pointer casts, 15.5 single exit, 21.x stdlib).
3. Fix in new/changed code; for legacy code record deviations (rule, location, rationale) instead of mass edits.
4. Suppress only with a documented reason: `// cppcheck-suppress misra-c2012-11.4 ; register access`.

## Leaks and memory errors (dynamic)
- If the project already has host builds or tests: `-fsanitize=address,undefined -fno-omit-frame-pointer` (LeakSanitizer is part of ASan on Linux).
- On target (FreeRTOS): track `xPortGetFreeHeapSize()` and `xPortGetMinimumEverFreeHeapSize()` over time (a falling minimum after steady state = leak), `uxTaskGetStackHighWaterMark()` per task, `configUSE_MALLOC_FAILED_HOOK`, `configCHECK_FOR_STACK_OVERFLOW 2`.
- Ownership review: every `pvPortMalloc`/create has exactly one matching free/delete on every path (the RTOS rules flag mismatches and double frees).
