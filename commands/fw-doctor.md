---
description: Show which free/open-source tools the kit can use on this machine, and install missing ones after confirmation
argument-hint: "[--for analysis|build|flash|test|itest|docs|format|container|esp32] [--install]"
---

Run `python "${CLAUDE_PLUGIN_ROOT}/tools/fw_doctor.py" --missing $ARGUMENTS` (drop `--missing` if the user wants the full table).

- Summarise what is missing and what each tool would enable, grouped by area.
- If the user wants installs, list the exact commands. Every tool is free and open source, and the license is shown. Ask for confirmation once for the whole list, then run `python <kit>/tools/fw_doctor.py --install <tool>` per tool.
- Some installs require admin rights or a new terminal so PATH picks them up; say so.
- For tools without an automatic install (download links, WSL-only tools), give the link and suggest the matching container instead (`fw_container.py`).
- Never install proprietary software.
