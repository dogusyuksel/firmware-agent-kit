---
description: Plan and execute an approved firmware restructure/refactor step by step (baseline, mechanical moves, build/analysis/size check per step, handoff notes)
argument-hint: "<goal, e.g. 'extract a HAL layer from drivers/ and add an OSAL over FreeRTOS'>"
---

Restructure goal: $ARGUMENTS

Follow the `restructure` skill strictly:
1. Check preconditions: clean git state, build green, baseline size (map file) and, if the project has tests, their status recorded.
2. Produce the plan (current and target structure, move list, numbered steps, out-of-scope list, risks). **Stop and wait for approval.**
3. Once approved, record the baseline: build, map file, analysis findings and the project's existing tests (if any).
4. Execute one step at a time:
   - one commit per step; never mix mechanical moves with logic changes;
   - after each step, build, run the project's existing tests (if any), run `fw_analyze.py` on the touched files, and compare sizes against the baseline map;
   - stop on any unexpected difference and report it.
5. Update `.claude/fw-notes.md` after every step.
6. At the end, run `/fw-review` on the whole range and give a summary.

No AI attribution in commit messages. Do not push unless the user asks.
