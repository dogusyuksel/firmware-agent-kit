"""PreToolUse(Bash): keep AI attribution out of git history and pull requests.

Denies git commit / tag / gh pr|release commands whose message, body file or author
contains Claude/Anthropic attribution (Co-Authored-By trailers, "Generated with
Claude Code", noreply@anthropic.com). Disable with git.block_ai_attribution=false.
"""

import os
import re
import shlex
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from fwlib import load_config, pre_tool_decision, project_dir, read_input  # noqa: E402

GIT_CMD_RE = re.compile(r"\b(git\s+(commit|tag|notes|merge|rebase)|gh\s+(pr|release|issue)\s+(create|edit|comment|merge))\b", re.I)
ATTRIB_RE = re.compile(
    r"co-authored-by:[^\n]*(claude|anthropic)|noreply@anthropic\.com|generated\s+(with|by)\s+\[?claude|"
    r"claude\.com/claude-code|--author[= ][\"']?[^\"'\n]*claude", re.I)
FILE_OPTS = ("-F", "--file", "--body-file", "--notes-file")


def referenced_files(command, cwd):
    texts = []
    try:
        toks = shlex.split(command, posix=True)
    except ValueError:
        toks = command.split()
    for i, t in enumerate(toks):
        val = None
        if t in FILE_OPTS and i + 1 < len(toks):
            val = toks[i + 1]
        elif any(t.startswith(o + "=") for o in FILE_OPTS):
            val = t.split("=", 1)[1]
        if val and val != "-":
            p = val if os.path.isabs(val) else os.path.join(cwd, val)
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    texts.append(f.read(200000))
            except OSError:
                pass
    return texts


def main():
    payload = read_input()
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not GIT_CMD_RE.search(command):
        return 0
    proj = project_dir(payload)
    cfg, _ = load_config(proj)
    if not (cfg.get("git") or {}).get("block_ai_attribution", True):
        return 0
    cwd = payload.get("cwd") or proj
    for text in [command] + referenced_files(command, cwd):
        m = ATTRIB_RE.search(text)
        if m:
            pre_tool_decision("deny", "AI attribution is not allowed in this project's git history or PRs (found: '{}'). "
                              "Remove Co-Authored-By/Generated-with lines and retry.".format(m.group(0)[:60]))
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
