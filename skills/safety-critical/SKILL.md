---
name: safety-critical
description: Practices for high-reliability / safety- and mission-critical firmware (spacecraft and satellite software under ECSS-E-ST-40C / ECSS-Q-ST-80C, and similar regimes such as DO-178C, IEC 61508, ISO 26262) - requirements traceability, coding standard and MISRA deviation records, structural coverage incl. MC/DC, defensive programming, FDIR, radiation effects (SEU/SEL) mitigation, watchdog strategy and verification evidence. Use when the project is safety/mission critical, mentions ECSS, satellites, flight software, certification, or asks for traceability, MC/DC or FDIR.
---

# Safety- and mission-critical firmware

The kit helps produce **evidence**; it does not make a project compliant. Compliance is decided by the project's plans (SDP, SVVP, PA plan) and reviews. State this when relevant.

## Requirements traceability
- Every software requirement has an ID (e.g. `SRS-UART-012`). Tag implementation and tests:
  ```c
  /* @req SRS-UART-012 Frame CRC is verified before dispatch */
  bool frame_check_crc(const frame_t *f);

  void test_frame_with_bad_crc_is_rejected(void)  /* @verifies SRS-UART-012 */
  ```
- `python <kit>/tools/trace_check.py --reqs docs/requirements.csv` builds the matrix (requirement -> code locations -> tests) and lists requirements without implementation or without tests, and tags pointing to unknown IDs. Use it in reviews and CI (`/fw-trace`).
- Changing behaviour = changing or adding a requirement first; keep the matrix green.

## Coding standard and MISRA
- Apply MISRA C:2012 (with Amendments) via `fw_analyze.py --misra` (cppcheck addon) plus the kit's EMB/RTOS rules.
- Record every deviation: rule, location, rationale, risk, approver, in `docs/misra-deviations.md` or inline as `/* MISRA deviation D-007: rule 11.4, register access */` with a central table. Never silently suppress.
- Prohibited by most critical-software standards: dynamic allocation after init, recursion, unbounded loops, unchecked return values, implicit conversions that change sign/size, goto-heavy flow, multiple threads touching unprotected data.

## Structural coverage
- Statement/branch coverage: GCC `--coverage` + gcov.
- **MC/DC** (needed at the highest criticality levels): GCC 14+ provides condition coverage `-fcondition-coverage` with `gcov --conditions` (free). Report per decision which conditions were not shown to independently affect the outcome; add tests or justify (defensive code, hardware-only paths).
- Coverage of target-only code: run tests on target with gcov dumped via semihosting/RTT, or argue by analysis; document the method.

## Defensive programming
- Validate all inputs at module boundaries; check every return value; range-check indices before use.
- Default branches in every `switch`; assert impossible states and route them to FDIR, not to `while(1)` silently.
- Critical variables: store with redundancy (value + bitwise complement, or triple copies with voting) and check before use.
- Control-flow monitoring for critical sequences (signature/checkpoint counters).
- Stack canaries / MPU guard regions; periodic RAM and flash CRC checks (flash image CRC at boot and in background).

## FDIR (Fault Detection, Isolation and Recovery)
- Define fault classes, detection mechanisms (watchdogs, plausibility checks, CRC, timeouts, telemetry limits) and recovery actions per level (retry -> reset peripheral -> switch to redundant unit -> safe mode -> processor reset).
- Keep a persistent fault/event log (noinit RAM or flash) with timestamps and reset cause; expose via telemetry.
- Safe mode: minimal, well-tested configuration that keeps communication and power-safe state.
- Use the `mermaid-diagrams` skill to document the FDIR state machine.

## Radiation effects (space)
- SEU (bit flips): EDAC/ECC memories (enable and handle correctable/uncorrectable error interrupts), periodic **scrubbing** of RAM and configuration registers, TMR or complement-checked critical variables, CRC on configuration tables, re-write peripheral configuration periodically.
- SEFI/latch-up: external watchdog independent of the MCU clock, current monitoring with power cycling by a supervisor, timeouts on every hardware wait.
- Program memory: dual images with CRC and a robust boot selector.
- Commercial MCUs (STM32, SAMV71) are not rad-hard; the SAMV71 family has radiation-tolerant variants (SAMV71Q21RT) - mitigation is an architecture topic; record assumptions.

## Watchdog strategy
Windowed or independent watchdog kicked only by a supervisor that verifies every critical task reported progress within its deadline (never from an ISR or timer). Log watchdog resets and count them for FDIR escalation.

## Verification evidence checklist (map to the project's plan)
Requirements trace matrix - unit test reports - coverage (statement/branch/MC/DC) with justifications - static analysis reports with dispositions - MISRA deviation list - stack/heap worst-case analysis - timing/WCET analysis - code review records (`/fw-review` outputs) - configuration (pinned tool versions) - problem reports.
