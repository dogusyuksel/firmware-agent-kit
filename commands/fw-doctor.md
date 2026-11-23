---
description: Show which free/open-source tools the kit can use on this machine, and how to install the missing ones
argument-hint: "[--for analysis|build|docs|format]"
---

Run `python "${CLAUDE_PLUGIN_ROOT}/tools/fw_doctor.py" --missing $ARGUMENTS` (drop `--missing` if the user wants the full table).

- Summarise what is missing and what each tool would enable, grouped by area.
- Show the exact install commands (Debian/Ubuntu; every tool is free and open source, license shown). Never run them yourself: the user installs what they want (for example with `! <command>` in the prompt), then re-run `/fw-doctor` to confirm.
- Never install proprietary software.
