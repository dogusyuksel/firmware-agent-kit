---
description: Run (or create) host unit tests - Ceedling/Unity/CMock, sanitizers, coverage - locally or in the arm-dev container
argument-hint: "[module or test name] [--coverage] [--container] [--write <module>]"
---

Unit tests. Arguments: $ARGUMENTS

1. Use `test.unit` from `.claude/firmware.json` if set. Otherwise detect the harness: Ceedling `project.yml`, CMake/CTest test targets, or ESP-IDF test apps.
2. With `--write <module>` (or when no test exists for the module the user names), delegate to the `test-engineer` agent and pass it the module and the existing test conventions.
3. Run the tests:
   - Ceedling: `ceedling test:<name>` or `test:all`; with `--coverage`, `ceedling gcov:all`.
   - CMake: `ctest --test-dir <build-test> --output-on-failure`.
   - With `--container` or when Ceedling is missing locally: `python <kit>/tools/fw_container.py run arm-dev -- ceedling test:all`. This needs Podman/Docker; ask before installing anything.
4. Report pass/fail counts, the first failure with its file:line and assertion, and coverage if measured. Diagnose failures. Fix production code only if the user asked for it.
