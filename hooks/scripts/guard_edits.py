"""PreToolUse(Edit|Write|MultiEdit): protect vendor code and generator-owned regions.

1. Paths under vendor/HAL/CMSIS/third_party (configurable) -> ask (or deny/allow).
2. Code-generator files (STM32CubeMX / CubeIDE style) containing
   "USER CODE BEGIN" markers: edits outside a USER CODE block are lost on the
   next regeneration -> ask, explaining why.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from fwlib import load_config, pre_tool_decision, project_dir, read_input, rel  # noqa: E402

BEGIN_RE = re.compile(r"USER CODE BEGIN")
END_RE = re.compile(r"USER CODE END")


def user_code_spans(text):
    """Return [(start, end)] character spans strictly inside USER CODE blocks."""
    spans, start = [], None
    pos = 0
    for line in text.splitlines(True):
        if BEGIN_RE.search(line):
            start = pos + len(line)
        elif END_RE.search(line) and start is not None:
            spans.append((start, pos))
            start = None
        pos += len(line)
    return spans


def inside_user_code(text, spans, needle):
    if not needle:
        return True
    idx = text.find(needle)
    if idx < 0:
        return True  # Edit will fail on its own; not our concern
    while idx >= 0:
        end = idx + len(needle)
        if not any(s <= idx and end <= e for s, e in spans):
            return False
        idx = text.find(needle, idx + 1)
    return True


def main():
    payload = read_input()
    name = payload.get("tool_name")
    ti = payload.get("tool_input") or {}
    path = ti.get("file_path")
    if name not in ("Edit", "Write", "MultiEdit") or not path:
        return 0

    proj = project_dir(payload)
    cfg, _ = load_config(proj)
    guard = cfg.get("guard", {})
    if not guard.get("enabled", True):
        return 0

    relpath = rel(os.path.abspath(path), proj)

    mode = guard.get("vendor_edits", "ask")
    if mode in ("ask", "deny"):
        for p in guard.get("protected_paths", []):
            if p and p.replace("\\", "/") in relpath:
                pre_tool_decision(
                    mode,
                    "{} is vendor/third-party code (matches protected path '{}'). Prefer fixing in "
                    "application code, a wrapper, or a documented patch file; vendor updates will "
                    "overwrite direct edits.".format(relpath, p),
                )
                return 0

    if not os.path.isfile(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return 0
    if not BEGIN_RE.search(text):
        return 0

    spans = user_code_spans(text)
    if name == "Write":
        pre_tool_decision(
            "ask",
            "{} is a code-generator file with USER CODE blocks. A full rewrite may drop "
            "generator-owned sections or user blocks; prefer Edit inside USER CODE BEGIN/END.".format(relpath),
        )
        return 0

    olds = [ti.get("old_string", "")] if name == "Edit" else [e.get("old_string", "") for e in ti.get("edits", [])]
    for old in olds:
        if not inside_user_code(text, spans, old):
            pre_tool_decision(
                "ask",
                "Edit to {} touches code OUTSIDE a 'USER CODE BEGIN/END' block. The code generator "
                "(e.g. STM32CubeMX) will overwrite it on the next regeneration. Move the change into a "
                "USER CODE block or change the .ioc configuration instead.".format(relpath),
            )
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
