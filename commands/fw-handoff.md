---
description: Save a compact project/session summary to .claude/fw-notes.md so the next session (or a teammate) continues where this one stopped
argument-hint: "[optional focus, e.g. 'UART DMA refactor']"
---

Update the project handoff notes. Focus: $ARGUMENTS

1. Read the existing `.claude/fw-notes.md` if present (it is also injected at session start).
2. Rewrite it (do not just append) in this exact structure, max ~60 lines, facts only, English:
   ```markdown
   # Firmware handoff notes
   Updated: <YYYY-MM-DD> | Branch: <git branch> | Last commit: <short sha + subject>

   ## Goal / current task
   - ...
   ## State
   - Done: ...            (with file:line or commit refs)
   - In progress: ...     (exact next step)
   ## Decisions (and why)
   - ...
   ## Open issues / risks
   - ...                  (include "Noticed (not changed)" items reported to the user)
   ## How to build / test / flash (only if different from .claude/firmware.json)
   - ...
   ```
3. Keep durable knowledge (decisions, hardware quirks, gotchas) and drop finished trivia. Never include secrets, keys, personal data or AI attribution.
4. Ask the user whether to commit the file (team-shared) or keep it local (add to `.gitignore`).
