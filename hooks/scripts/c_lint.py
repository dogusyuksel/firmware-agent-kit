"""PostToolUse(Edit|Write|MultiEdit): embedded/RTOS lint on the lines this edit touched.

- Findings on edited lines: errors block (must fix), warnings are context.
- Findings on untouched lines: summarised as "pre-existing" - Claude must NOT fix
  them unasked, only report them to the user (minimal-diff policy).
- Optional: clang-format the edited lines first (format.on_edit=true + .clang-format present).
"""

import os
import sys
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from fwlib import (git_changed_lines, is_protected, load_config, post_tool_context,  # noqa: E402
                   project_dir, read_input, rel)
from fw_lint import lint_file  # noqa: E402
from rtos_check import _cache, _store, cached_isr_map, load_rtos_config  # noqa: E402
from fwfmt import format_file  # noqa: E402

MAX_NEW = 12
MAX_OLD = 3


def edited_lines(name, ti, path):
    """Line numbers written by this tool call; None = whole file."""
    if name == "Write":
        return git_changed_lines(path)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return set()
    news = [ti.get("new_string", "")] if name == "Edit" else [e.get("new_string", "") for e in ti.get("edits", [])]
    lines = set()
    for new in news:
        if not new:
            continue
        idx = text.find(new)
        while idx >= 0:
            first = text.count("\n", 0, idx) + 1
            lines.update(range(first, first + new.count("\n") + 1))
            if not ti.get("replace_all"):
                break
            idx = text.find(new, idx + 1)
    return lines


def main():
    payload = read_input()
    name = payload.get("tool_name")
    ti = payload.get("tool_input") or {}
    path = ti.get("file_path")
    if not path or not os.path.isfile(path):
        return 0
    proj = project_dir(payload)
    cfg, _ = load_config(proj)
    lcfg = cfg.get("lint", {})
    if not lcfg.get("enabled", True):
        return 0
    if os.path.splitext(path)[1].lower() not in [e.lower() for e in lcfg.get("extensions", [])]:
        return 0
    relpath = rel(path, proj)
    if is_protected(relpath, cfg):
        return 0

    notes = []
    lines = edited_lines(name, ti, path)
    if cfg.get("format", {}).get("on_edit"):
        status, _ = format_file(path, lines)
        if status == "formatted":
            notes.append("clang-format adjusted the edited lines of {} - re-read before editing it again.".format(relpath))
            lines = edited_lines(name, ti, path) if name != "Write" else lines

    try:
        rtos_cfg, _ = load_rtos_config(proj, cfg)
        new, old = lint_file(path, cfg, lines, rtos_cfg=rtos_cfg, extra_isr=cached_isr_map(proj))
        new = [f for f in new if f.sev != "info"]
        old = [f for f in old if f.sev != "info"]
    except Exception as e:
        sys.stderr.write("firmware-agent-kit lint failed: {}\n".format(e))
        return 0
    if not new and not old and not notes:
        return 0

    errors = [f for f in new if f.sev == "error"]
    warns = [f for f in new if f.sev != "error"]
    out = ["firmware-agent-kit lint {}:".format(relpath)] + notes
    out += ["  ERROR " + str(f) for f in errors[:MAX_NEW]]
    out += ["  WARN  " + str(f) for f in warns[: max(0, MAX_NEW - len(errors))]]
    if len(new) > MAX_NEW:
        out.append("  ... {} more on edited lines".format(len(new) - MAX_NEW))
    if old:
        key = "reported:" + str(payload.get("session_id") or "")
        seen = _cache(proj, key, None) or {}
        digest = str(zlib.crc32("\n".join(sorted(f.rule + f.msg for f in old)).encode("utf-8")))
        if seen.get(relpath) == digest:
            old = []        # already listed earlier in this session - do not repeat (tokens)
        else:
            seen[relpath] = digest
            _store(proj, key, seen)
    if old:
        out.append("  {} pre-existing finding(s) on lines you did not touch - do NOT fix unless asked; list them "
                   "under 'Noticed (not changed)' in your reply:".format(len(old)))
        out += ["    " + str(f) for f in old[:MAX_OLD]]
    if errors:
        out.append("Fix the ERROR items in your change (or explain why they are false positives).")
    if len(out) == 1:
        return 0
    post_tool_context("\n".join(out), block=bool(errors))
    return 0


if __name__ == "__main__":
    sys.exit(main())
