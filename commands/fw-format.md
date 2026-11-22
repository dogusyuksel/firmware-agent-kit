---
description: clang-format only the changed lines (keeps diffs minimal); --check to report only
argument-hint: "[files] [--check] [--whole]"
---

Run `python "${CLAUDE_PLUGIN_ROOT}/tools/fw_format.py" $ARGUMENTS` (locate `fw_format.py` with Glob if the variable is not expanded).

- Requires clang-format and a `.clang-format` in the project. If the project has none, ask whether to add the kit template (`<kit>/templates/.clang-format`) or derive one that matches the existing code (`python <kit>/tools/style_probe.py`). Never impose a style on an existing codebase without asking.
- Only use `--whole` for new files or when the user explicitly asks; reformatting legacy files creates noisy diffs.
- Report which files changed.
