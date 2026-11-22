"""clang-format restricted to changed lines (keeps diffs minimal). Stdlib only."""

import os

from fwlib import git_changed_lines, resolve_tool, run, to_ranges


def has_style_file(path):
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.isfile(os.path.join(d, ".clang-format")) or os.path.isfile(os.path.join(d, "_clang-format")):
            return True
        parent = os.path.dirname(d)
        if parent == d:
            return False
        d = parent


def format_file(path, lines="git", check=False):
    """Format `lines` of `path` ('git' = lines changed vs HEAD, None = whole file, or a set).
    Returns (status, detail): status in {'formatted','clean','needs-format','skipped'}."""
    exe, conv = resolve_tool("clang-format")
    if not exe:
        return "skipped", "clang-format not installed"
    if not has_style_file(path):
        return "skipped", "no .clang-format in the project (not imposing a style)"
    if lines == "git":
        lines = git_changed_lines(path)
    args = exe + ["--style=file", "--fallback-style=none"]
    if lines is not None:
        if not lines:
            return "clean", "no changed lines"
        args += ["--lines={}:{}".format(a, b) for a, b in to_ranges(lines)]
    if check:
        rc, _, err = run(args + ["--dry-run", "--Werror", conv(path)], timeout=60)
        return ("clean", "") if rc == 0 else ("needs-format", "{} formatting issue(s)".format(err.count("warning:") or 1))
    with open(path, "rb") as f:
        before = f.read()
    rc, _, err = run(args + ["-i", conv(path)], timeout=60)
    if rc != 0:
        return "skipped", err.strip()[:200]
    with open(path, "rb") as f:
        after = f.read()
    return ("formatted", "") if after != before else ("clean", "")
