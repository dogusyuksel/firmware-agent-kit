---
name: restructure
description: Safely restructure or refactor an existing firmware codebase on explicit request - target architecture plan, characterization tests first, mechanical moves separated from logic changes, build/test/size check after every step, generated-code boundaries, multi-session progress tracking. Use when the user asks to reorganize folders/modules, extract a HAL/BSP/OSAL layer, split a large file, port the structure to another MCU, or clean up architecture.
---

# Restructuring firmware safely

The kit's minimal-diff rule is suspended **only** for the scope the user approved in the plan. Everything outside that scope stays untouched.

## 0. Preconditions
- The user asked for the restructure explicitly. If not, propose it under "Noticed (not changed)" and stop.
- Clean git state (or a dedicated branch); build is green; note baseline flash/RAM (`arm-none-eabi-size`, map file copy) and test status.

## 1. Plan (needs approval)
Produce with `/fw-plan` format plus:
- Current structure (module/dependency `flowchart`) and target structure (see `portable-architecture`).
- Move list: `old path -> new path`, files to split/merge, new interfaces (headers) to introduce.
- Step list where **each step builds and passes tests**. Typical order:
  1. characterization tests for the modules being moved;
  2. pure moves/renames (`git mv`), include-path and build-file updates only;
  3. introduce interfaces/seams with the old implementation behind them;
  4. move logic behind the interfaces;
  5. delete dead code (only code proven unused).
- Out of scope list (vendor code, generated code, unrelated modules).
- Risks: ISR/RTOS context changes, init order, linker sections/`KEEP`, weak symbols, LTO, generated code regeneration.

## 2. Baseline first
Record the current state before changing structure: build output, map file (`map_analyzer.py`), analysis findings, and the project's existing tests if it has any. Preserve what the code *does*, even if odd - behaviour changes are a separate decision.

## 3. Execute in small commits
- One step = one commit with a message that says what moved and that behaviour is unchanged.
- Mechanical commits contain no logic edits (reviewers can verify with `git diff -M --stat` / `git log --follow`).
- After every step: build, existing tests (if any), `fw_analyze.py` on touched files, size comparison:
  `python <kit>/skills/memory-footprint/scripts/map_analyzer.py baseline.map build/app.map` - pure moves should give (near) zero delta; investigate any change.
- Keep generated code where the generator expects it (CubeMX `Core/`, Harmony `config/`); wrap it instead of moving it, or the next regeneration breaks the tree.
- Keep public symbol names stable unless renaming is part of the plan; when renaming, do it in its own commit.
- Watch for: changed init order (constructors, `MX_*_Init` sequence), ISR handler names still matching the vector table, `static` functions that became shared, include cycles, duplicated globals after splitting files.

## 4. Track progress across sessions
Update `.claude/fw-notes.md` (`/fw-handoff`) after each step: done steps with commit SHAs, next step, open issues. Long restructures span sessions - never rely on memory of the conversation.

## 5. Finish
- Run `/fw-review` on the full range (`git diff <base>..HEAD`), full test suite, size report vs baseline.
- Update docs/diagrams (architecture flowchart) and CLAUDE.md firmware section if paths changed.
- Summarise: what moved, what intentionally did not, behaviour changes (should be none unless approved), follow-ups.
