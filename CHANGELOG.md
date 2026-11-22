# Changelog

## 0.3.1 - 2026-11-22
- Field-report fixes: application structs with `.on_*` members are no longer treated as ESP-IDF ISR callbacks (only `*_event_callbacks_t`/`*_cbs_t` driver structs); `extern portMUX_TYPE` declarations are not flagged as uninitialised; ISR data protected by a spinlock/critical section is not flagged as missing `volatile`; `strcpy`/`strcat` after a `strlen` check of the source is not flagged.
- `fwkit-ignore <RULE-ID>` suppression comments for reviewed false positives.
- clang-tidy: integer-to-float narrowing warnings disabled by default (also in the template).
- Tools found in standard Windows install folders and inside WSL (run through `wsl.exe` with path translation): fw_analyze, fw_format, fw_doctor.
- Verified locally: the sensor-node Ceedling tests pass (Ceedling 0.31 in WSL); Renode smoke test (`examples/renode-smoke`) passes; fixed `waitForEcho` in the Renode templates; example project.yml compatible with Ceedling 0.31 and 1.0.
- CI runs the Renode smoke test inside the renode image.
- fw_analyze: without a compile DB, project header folders are used as include paths and missing-include diagnostics become one note; clang-tidy `bugprone-signed-bitwise` disabled by default (integer-promotion noise). Verified with clang-tidy 23 and cppcheck 2.22: the example project is finding-free.

## 0.3.0 - 2026-11-22
- Plan-first working rule and `/fw-plan`; `restructure` skill and `/fw-restructure` for approved refactors.
- `safety-critical` skill (ECSS/DO-178C-style evidence, MISRA deviations, MC/DC via GCC `-fcondition-coverage`, FDIR, SEU mitigation) and `tools/trace_check.py` + `/fw-trace` for requirements traceability.
- `bootloader` and `timing-analysis` skills.
- Cross-file ISR reachability in project mode (cached for the edit hook); FreeRTOSConfig.h location cached so hooks stay fast.
- RTOS rules calibrated on ~200 official FreeRTOS/ESP-IDF/STM32Cube example files: zero error-level findings; false-positive patterns frozen as regression tests; `tests/calibrate_corpus.py`.
- `examples/sensor-node` reference project (OSAL, thread-safe API, Ceedling tests, requirement tags).
- `evals/` plugin eval scenarios; CI now runs the example with Ceedling, corpus calibration and Docker image builds.

## 0.2.0 - 2026-11-22
- Targets: new `stm32`, `esp32`, `samv71` skills; `freertos` skill covering FreeRTOS, CMSIS-RTOS2 and ESP-IDF SMP.
- RTOS checker (`tools/rtos_check.py`, ~60 RTOS-xxx rules, per-file and project-level) with a sourced catalogue in `docs/RTOS_RULES.md`; ISR context propagates through helpers, HAL callbacks and ESP handlers.
- Edit hook reports only findings on edited lines; pre-existing issues are listed, not fixed (minimal-diff policy).
- Analysis: `fw_analyze.py` (lint + RTOS + cppcheck/MISRA + clang-tidy + Frama-C, SARIF), `fw_format.py` (changed lines only), `build_info.py`, `pdf_search.py`, `style_probe.py`, `fw_doctor.py` (OSS install hints), `fw_container.py` with arm-dev, esp-idf, renode and frama-c images.
- New skills: static-analysis, portable-architecture, renode-integration, build-systems, hardware-docs, mermaid-diagrams, containers; Ceedling-first host-unit-test; open-source-only flash-debug.
- New agent `test-engineer`; reviewer now checks RTOS rules, thread safety, scope creep and style drift; datasheet analyst reads schematics.
- New commands: /fw-analyze, /fw-format, /fw-test, /fw-itest, /fw-diagram, /fw-docs, /fw-doctor, /fw-handoff.
- Hooks: git guard against AI attribution; ESP secure-boot/flash-encryption and SAMV71 GPNVM/bossac/edbg guards; session handoff notes; working rules injected at session start.

## 0.1.0 - 2026-11-21
- Initial release: 10 skills, 4 agents, 6 commands, 5 hooks (session context, target-operation guard, vendor/CubeMX edit guard, embedded C lint, build size tracker), project config template, test suite.
