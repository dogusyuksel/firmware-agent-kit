---
description: Static analysis (kit lint + RTOS rules + cppcheck/MISRA + clang-tidy, optional Frama-C) of changed or all firmware sources, one compact report
argument-hint: "[files] [--all] [--misra] [--tools ...] [--sarif out.sarif]"
---

Run `python "${CLAUDE_PLUGIN_ROOT}/tools/fw_analyze.py" $ARGUMENTS` (if the variable is not expanded, locate `fw_analyze.py` in the firmware-agent-kit plugin with Glob).

- Default scope is changed files and changed lines. `--all` covers the whole project, including the project-level RTOS rules (FreeRTOSConfig.h, NVIC priorities, heap scheme).
- If notes say tools are missing, tell the user which free/open-source tools would add coverage. Use `python <kit>/tools/fw_doctor.py --for analysis` for the install commands. Ask once whether to install them; if not, continue without them.
- Present results grouped by severity, merging duplicates. Verify each error against the code before presenting it.
- Explain RTOS-xxx findings using `<kit>/docs/RTOS_RULES.md`.
- Do not fix anything unless the user asks.
- Findings in code outside the current task go under "Noticed (not changed)".
