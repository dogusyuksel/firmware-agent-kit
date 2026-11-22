#!/usr/bin/env python3
"""Heuristic linter for bare-metal C pitfalls (EMB-xxx rules). RTOS rules live in rtos_check.py.

Not a compiler, not MISRA: it catches classic embedded bugs that generic linters miss.
Used by the PostToolUse hook and by fw_analyze.py.

  python fw_lint.py [--all-lines] file.c [...]   # default: only lines changed vs git HEAD
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cparse import CFile, Finding  # noqa: E402
from fwlib import git_changed_lines, load_config  # noqa: E402
import rtos_check  # noqa: E402

RAW_REG_RE = re.compile(
    r"\*\s*\(\s*(?!volatile)(?:const\s+)?(?:u?int(?:8|16|32|64)_t|unsigned(?:\s+(?:int|long|char|short))?|int|long)\s*\*\s*\)\s*\(?\s*0x[0-9A-Fa-f]{5,}")
POLL_RE = re.compile(r"\bwhile\s*\(([^;{}]*)\)\s*(?:;|\{\s*\})")
TICK_CMP_RE = re.compile(r"\b(\w*[Gg]et_?[Tt]ick\w*|millis|micros|xTaskGetTickCount|osKernelGetTickCount|esp_timer_get_time)\s*\(\s*\)\s*[<>]=?")
LOCAL_ARRAY_RE = re.compile(
    r"^\s*(?!static\b)(?:const\s+)?(u?int(8|16|32|64)_t|char|unsigned\s+char|float|double|int|uint)\s+\w+\s*\[\s*(\d+)\s*\]", re.M)
ELEM_SIZE = {"8": 1, "16": 2, "32": 4, "64": 8}


def _file_scope_nonvolatile_vars(code):
    names, depth, start = set(), 0, 0
    for i, ch in enumerate(code):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            start = i + 1
        elif ch == ";" and depth == 0:
            stmt = "\n".join(l for l in code[start:i].splitlines() if not l.lstrip().startswith("#")).strip()
            start = i + 1
            if not stmt or "(" in stmt.split("=")[0]:
                continue
            if re.search(r"\b(volatile|const|typedef|enum|return|_Atomic|extern\s+\"C\")\b|^\s*struct\s+\w+\s*$", stmt):
                continue
            m = re.search(r"\b([A-Za-z_]\w*)\s*(\[[^\]]*\])*\s*(=.*)?$", stmt, re.S)
            if m and len(stmt.split()) >= 2:
                names.add(m.group(1))
    return names


def lint_source(src, cfg, extra_isr=None):
    lcfg = cfg.get("lint", {})
    cf = CFile(src, lcfg.get("isr_functions", []), extra_isr)
    code = cf.code
    out = []

    def add(rule, sev, idx, msg, end_idx=None):
        out.append(Finding(rule, sev, cf.line(idx), cf.line(end_idx) if end_idx is not None else cf.line(idx), msg))

    for m in re.finditer(r"\bgets\s*\(", code):
        if "gets" in cf.funcs and cf.funcs["gets"].start <= m.start() <= cf.funcs["gets"].body_start:
            continue
        add("EMB-001", "error", m.start(), "gets() is unbounded - never use it.")
    for m in re.finditer(r"\b(strcpy|strcat|sprintf|vsprintf)\s*\(", code):
        add("EMB-002", "warn", m.start(), "{}() is unbounded; use the n-variant with an explicit size.".format(m.group(1)))
    if lcfg.get("forbid_dynamic_alloc", True):
        for m in re.finditer(r"(?<![\w.>])(malloc|calloc|realloc|free)\s*\(", code):
            add("EMB-003", "error", m.start(), "{}() - dynamic allocation is forbidden here (fragmentation/non-determinism). "
                "Use static/pool allocation or FreeRTOS static APIs, or set lint.forbid_dynamic_alloc=false.".format(m.group(1)))
    for m in RAW_REG_RE.finditer(code):
        add("EMB-004", "error", m.start(), "Raw hardware address dereferenced without 'volatile'. Use the CMSIS device header or a volatile pointer.")
    for m in POLL_RE.finditer(code):
        cond = m.group(1)
        if re.search(r"->|\bREG\w*|&\s*\(?\s*[A-Z_0-9]+|\b[A-Z][A-Z0-9_]*_(SR|ISR|STAT\w*)\b", cond) and \
                not re.search(r"timeout|tmo|deadline|retr|--", cond, re.I):
            add("EMB-005", "warn", m.start(), "Busy-wait on a hardware flag without a timeout - add a bounded timeout and error path.")
    for m in TICK_CMP_RE.finditer(code):
        add("EMB-006", "warn", m.start(), "Direct tick/time comparison breaks at wraparound. Use '(uint32_t)(now - start) >= timeout'.")
    for m in LOCAL_ARRAY_RE.finditer(code):
        if not cf.func_at(m.start()):
            continue
        t, bits, count = m.group(1), m.group(2), int(m.group(3))
        size = count * (ELEM_SIZE.get(bits) or (8 if t == "double" else 1 if "char" in t else 4))
        if size >= 256:
            add("EMB-007", "warn", m.start(), "{}-byte local array on the stack (task/ISR stacks are small). Make it static or "
                "check the stack budget (-fstack-usage / uxTaskGetStackHighWaterMark).".format(size))

    for name in cf.esp_registered:
        if name in cf.funcs and "IRAM_ATTR" not in cf.funcs[name].prefix:
            add("EMB-010", "warn", cf.funcs[name].start, "ISR handler '{}' has no IRAM_ATTR - it crashes if it runs while the "
                "flash cache is disabled (required with ESP_INTR_FLAG_IRAM).".format(name))

    globals_nv = _file_scope_nonvolatile_vars(code)
    forbidden = lcfg.get("isr_forbidden_calls", [])
    for name, why in cf.isr.items():
        f = cf.funcs[name]
        b0, body = f.body_start, cf.body(f)
        for fn in forbidden:
            for c in re.finditer(r"(?<![\w.>])" + re.escape(fn) + r"\s*\(", body):
                add("EMB-011", "error", b0 + c.start(), "{}() in {} '{}' - blocking/non-reentrant. Set a flag, push to a ring "
                    "buffer or notify a task.".format(fn, why, name))
        for c in re.finditer(r"\b(float|double)\b|\b\d+\.\d*f?\b", body):
            add("EMB-012", "warn", b0 + c.start(), "Floating point in {} '{}' - FPU context cost (ESP32: FPU not allowed in "
                "ISRs). Prefer fixed-point.".format(why, name))
            break
        reported = set()
        for g in globals_nv:
            w = re.search(r"(?<![\w.>])" + re.escape(g) + r"\s*(\[[^\]]*\])?\s*(\+\+|--|[-+*/|&^]?=(?!=))|(\+\+|--)\s*"
                          + re.escape(g) + r"\b", body)
            if w and g not in reported:
                reported.add(g)
                add("EMB-013", "warn", b0 + w.start(), "'{}' is modified in {} '{}' but not volatile. If other code reads it, "
                    "make it volatile and protect multi-word RMW (critical section / atomic).".format(g, why, name))
    return out


def lint_file(path, cfg, changed="git", rtos=True, rtos_cfg=None, extra_isr=None):
    """Return (new, preexisting) findings incl. RTOS rules. changed: 'git' | None (all) | set of lines."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        src = f.read()
    findings = lint_source(src, cfg, extra_isr)
    if rtos:
        findings += rtos_check.check_source(src, cfg, rtos_cfg, extra_isr)
    if changed == "git":
        changed = git_changed_lines(path)
    findings.sort(key=lambda x: (x.sev != "error", x.line))
    return [f for f in findings if f.touches(changed)], [f for f in findings if not f.touches(changed)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--all-lines", action="store_true", help="report findings on unchanged lines too")
    ap.add_argument("--no-rtos", action="store_true")
    args = ap.parse_args()
    cfg, _ = load_config(os.getcwd())
    rc = 0
    for p in args.files:
        new, old = lint_file(p, cfg, None if args.all_lines else "git", rtos=not args.no_rtos)
        for f in new:
            if f.sev == "info":
                continue
            print("{}:{}: {}: [{}] {}".format(p, f.line, f.sev, f.rule, f.msg))
            rc |= f.sev == "error"
        if old:
            print("{}: {} pre-existing finding(s) on unchanged lines (use --all-lines)".format(p, len(old)))
    return 1 if rc else 0


if __name__ == "__main__":
    sys.exit(main())
