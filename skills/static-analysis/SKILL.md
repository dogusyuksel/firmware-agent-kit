---
name: static-analysis
description: Static and dynamic analysis of firmware with free/open-source tools - the kit's fw_analyze (embedded lint + RTOS rules), cppcheck with the MISRA C:2012 addon, clang-tidy, Frama-C (EVA/WP), clang-format, plus leak/memory checks (ASan/UBSan, valgrind, FreeRTOS heap/stack monitoring) and SARIF for CI. Use when asked to analyse, audit, check MISRA compliance, find leaks or set up analysis in CI.
---

# Static and dynamic analysis

## One command first
```sh
python <kit>/tools/fw_analyze.py                    # changed files, changed lines (cheap; default)
python <kit>/tools/fw_analyze.py --all              # whole project incl. project-level RTOS rules
python <kit>/tools/fw_analyze.py --misra src/x.c    # + MISRA C:2012 (cppcheck addon)
python <kit>/tools/fw_analyze.py --all --sarif analysis.sarif
```
It runs whatever is installed, uses `compile_commands.json` for include paths/defines, de-duplicates, and prints one compact list. Missing tools are reported as notes: ask the user once whether to install them (`tools/fw_doctor.py --for analysis`), otherwise skip. Prefer this over running tools by hand (less output, fewer tokens).

Report pre-existing findings in untouched code to the user; fix only what the task covers.

Tools are found on PATH, in standard Windows install folders, or inside WSL (called through `wsl.exe` with path translation). Reviewed false positives are suppressed in code with a reason: `fwkit-ignore EMB-002: <why>` (kit rules), `cppcheck-suppress <id>`, `NOLINT(<check>)`. Integer-to-float narrowing warnings from clang-tidy are disabled by default (lossless for typical ADC/sensor widths).

## Tools and what they are good at
| Tool | Finds | Notes |
|---|---|---|
| kit lint + `rtos_check.py` | ISR misuse, RTOS API rules (RTOS-xxx), volatile/timeout/stack issues (EMB-xxx) | heuristic, no build needed |
| cppcheck | UB, null deref, leaks, out-of-bounds, uninitialised vars | `--platform=unix32` approximates 32-bit MCUs; suppress inline with `// cppcheck-suppress id` |
| cppcheck `--addon=misra` | MISRA C:2012 rule IDs | rule *texts* are copyrighted: point `analysis.misra_rules_file` at your licensed text file, or output shows only IDs |
| clang-tidy | clang static analyzer (path-sensitive), bugprone, cert | cross-compile flags: `--extra-arg=--target=arm-none-eabi`; GCC-only flags may need `-Wno-unknown-warning-option` (fw_analyze adds them) |
| Frama-C EVA | proves absence of runtime errors (overflow, div by 0, invalid pointer) or lists alarms | slow, run on selected modules; needs stubs for hardware registers; WP proves ACSL contracts |
| clang-format | style drift | changed lines only (`tools/fw_format.py`); never reformat whole legacy files unasked |
| GCC itself | `-Wall -Wextra -Wshadow -Wconversion -Wdouble-promotion -Wformat=2 -Wnull-dereference -fanalyzer` (GCC 12+ `-fanalyzer` is decent for C) | free and already installed |

## MISRA workflow
1. Agree the scope with the user: mandatory/required/advisory, deviations process.
2. `fw_analyze.py --misra --all` (or per module). Group findings by rule; most noise comes from a few rules (10.x essential types, 11.x pointer casts, 15.5 single exit, 21.x stdlib).
3. Fix in new/changed code; for legacy code record deviations (rule, location, rationale) instead of mass edits.
4. Suppress only with a documented reason: `// cppcheck-suppress misra-c2012-11.4 ; register access`.

## Frama-C quick start
```sh
frama-c -eva -eva-precision 1 -machdep gcc_x86_32 -cpp-extra-args="-Iinc -DUNIT_TEST" src/crc.c src/parser.c
# hardware registers: provide a stub header where peripherals are plain volatile structs
```
Start with pure modules (parsers, CRC, ring buffers, state machines). Use the `frama-c` container on Windows.

## Leaks and memory errors (dynamic)
- Host unit tests with sanitizers: `-fsanitize=address,undefined -fno-omit-frame-pointer` (Ceedling `:flags:` / CMake). LeakSanitizer is part of ASan on Linux.
- Valgrind memcheck on Linux host tests: `valgrind --leak-check=full --error-exitcode=1 ./test_x`.
- On target (FreeRTOS): track `xPortGetFreeHeapSize()` and `xPortGetMinimumEverFreeHeapSize()` over time (a falling minimum after steady state = leak), `uxTaskGetStackHighWaterMark()` per task, `configUSE_MALLOC_FAILED_HOOK`, `configCHECK_FOR_STACK_OVERFLOW 2`. ESP-IDF: heap tracing (`heap_trace_start`) and `heap_caps_check_integrity_all`.
- Ownership review: every `pvPortMalloc`/create has exactly one matching free/delete on every path (the RTOS rules flag mismatches and double frees).

## CI
Run `fw_analyze.py --all --sarif analysis.sarif` in the `arm-dev` container and upload the SARIF (GitHub code scanning, or a SARIF viewer in the IDE). Fail the job on `error` severity only; ratchet warnings down over time.
