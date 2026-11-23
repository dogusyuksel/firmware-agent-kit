---
description: Create or update a project-specific conventions skill (.claude/skills/<project>-conventions/SKILL.md) so the generic kit follows this codebase's style, layering, error handling, concurrency and hardware facts
argument-hint: "[optional notes, e.g. 'errors are hal_status_t, locks via os_mutex_*']"
---

Create a project overlay for the generic kit. User notes: $ARGUMENTS

The kit's skills stay generic; this file holds what is specific to this project. It is loaded automatically like any project skill and wins over kit defaults when they differ.

1. **Gather facts** (read-only, cheap; `<kit>` = `${CLAUDE_PLUGIN_ROOT}` or the plugin directory found with Glob):
   - `python3 <kit>/tools/style_probe.py` - naming, prefixes, braces, indentation, error returns, file header;
   - `.claude/firmware.json`, `CLAUDE.md`, `.claude/fw-notes.md` if present;
   - Grep only, never whole files: status/error type (`*_status_t`, `int` with negative codes, `HAL_StatusTypeDef`), lock API (OSAL, `xSemaphore*`, `osMutex*`, critical sections), logging macro, assert macro, IRQ priority definitions, folder layering (`app/`, `drivers/`, `bsp/`, `port/`, generated folders);
   - an existing small module that represents the house style (name it as the reference example).
2. **Ask once** (AskUserQuestion) only for what the code cannot answer: forbidden APIs, rules the team wants enforced, deviations from the kit defaults.
3. **Write** `.claude/skills/<project>-conventions/SKILL.md` from `<kit>/templates/project-conventions.md`:
   - fill every section with facts and file references, under ~60 lines;
   - drop sections that do not apply; never invent conventions the code does not show;
   - if the file exists, show a diff and merge, keeping manual edits.
4. Show the result and tell the user to commit it so teammates get the same behaviour. Re-run `/fw-customize` after large refactors.

Do not change any source file.
