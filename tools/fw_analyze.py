#!/usr/bin/env python3
"""Run the available static analyzers on firmware sources and print ONE compact report (or SARIF).

Tools (each optional, skipped with a note if not installed - all free/open source):
  lint       kit embedded lint (EMB-xxx) + RTOS rules (RTOS-xxx)        always available
  rtos       project-level RTOS rules (FreeRTOSConfig.h, NVIC prio, heap scheme)
  cppcheck   cppcheck (+ --misra: MISRA C:2012 addon)
  clang-tidy clang-analyzer / bugprone / cert checks
  frama-c    Frama-C EVA (run only when asked: slow)
  format     clang-format check of changed lines

  python fw_analyze.py                          # changed files vs HEAD, changed lines only
  python fw_analyze.py --all                    # every project source (vendor excluded), all lines
  python fw_analyze.py src/uart.c --tools cppcheck,clang-tidy --misra
  python fw_analyze.py --all --tools frama-c src/crc.c
  python fw_analyze.py --sarif out.sarif        # for CI / IDE (GitHub code scanning, VS Code SARIF viewer)
"""

import argparse
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fw_lint  # noqa: E402
import rtos_check  # noqa: E402
from build_info import norm_args, split_cmd  # noqa: E402
from fwfmt import format_file  # noqa: E402
from fwlib import (C_EXTS, find_compile_commands, git_changed_files, git_changed_lines, is_protected,  # noqa: E402
                   load_config, rel, run, which)

DEFAULT_TIDY_CHECKS = ("-*,clang-analyzer-*,bugprone-*,cert-*,misc-redundant-expression,"
                       "-bugprone-easily-swappable-parameters,-cert-err33-c,-bugprone-reserved-identifier,"
                       "-cert-dcl37-c,-cert-dcl51-cpp")


class Item(object):
    __slots__ = ("tool", "file", "line", "sev", "rule", "msg")

    def __init__(self, tool, file, line, sev, rule, msg):
        self.tool, self.file, self.line, self.sev, self.rule, self.msg = tool, file, int(line or 1), sev, rule, msg


def load_db(cc):
    if not cc:
        return {}
    try:
        with open(cc, "r", encoding="utf-8") as f:
            db = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    for e in db:
        p = os.path.normcase(os.path.normpath(os.path.join(e.get("directory", "."), e["file"])))
        out[p] = norm_args(split_cmd(e), e.get("directory", "."))
    return out


def flags_for(files, db):
    incs, defs = [], []
    for f in files:
        info = db.get(os.path.normcase(os.path.abspath(f)))
        if info:
            incs += [i for i in info["includes"] if i not in incs]
            defs += [d for d in info["defines"] if d not in defs]
    return incs, defs


def run_lint(files, cfg, rc, extra_isr=None):
    items = []
    for f in files:
        new, _ = fw_lint.lint_file(f, cfg, None, rtos=True, rtos_cfg=rc, extra_isr=extra_isr)
        items += [Item("lint", f, x.line, x.sev, x.rule, x.msg) for x in new if x.sev != "info"]
    return items


def run_rtos_project(proj, cfg):
    findings, _ = rtos_check.check_project(proj, cfg, rtos_check.project_sources(proj, cfg))
    return [Item("rtos", os.path.join(proj, p) if p != "(project)" else p, f.line, f.sev, f.rule, f.msg)
            for p, f in findings if f.sev != "info"]


def run_cppcheck(files, db, cfg, misra):
    exe = which("cppcheck")
    if not exe:
        return None
    incs, defs = flags_for(files, db)
    cmd = [exe, "--enable=warning,style,performance,portability", "--inline-suppr", "--quiet",
           "--platform=unix32", "--suppress=missingIncludeSystem", "--suppress=unmatchedSuppression",
           "--template={file}:{line}:{severity}:{id}:{message}"]
    cmd += ["-I" + i for i in incs[:200]] + ["-D" + d for d in defs[:200]]
    tmp = None
    if misra:
        rules = (cfg.get("analysis") or {}).get("misra_rules_file")
        if rules:
            tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
            json.dump({"script": "misra.py", "args": ["--rule-texts=" + os.path.abspath(rules)]}, tmp)
            tmp.close()
            cmd.append("--addon=" + tmp.name)
        else:
            cmd.append("--addon=misra")
    rc, out, err = run(cmd + files, timeout=900)
    if tmp:
        os.unlink(tmp.name)
    items = []
    for line in (err + "\n" + out).splitlines():
        m = re.match(r"^(.+?):(\d+):(\w+):([\w\-.]+):(.*)$", line.strip())
        if m and m.group(3) != "information":
            sev = "error" if m.group(3) == "error" else "warn"
            rule = m.group(4) if not m.group(4).startswith("misra") else m.group(4).replace("misra-c2012-", "MISRA-")
            items.append(Item("cppcheck", m.group(1), m.group(2), sev, rule, m.group(5).strip()))
    return items


def run_clang_tidy(files, cc, cfg):
    exe = which("clang-tidy")
    if not exe:
        return None
    cmd = [exe, "--quiet"]
    if cc:
        cmd += ["-p", os.path.dirname(cc)]
    if not os.path.isfile(os.path.join(os.getcwd(), ".clang-tidy")):
        cmd += ["--checks=" + ((cfg.get("analysis") or {}).get("clang_tidy_checks") or DEFAULT_TIDY_CHECKS)]
    prefix = cfg.get("toolchain_prefix") or ""
    if "arm-none-eabi" in prefix:
        cmd += ["--extra-arg=--target=arm-none-eabi"]
    cmd += ["--extra-arg=-Wno-unknown-warning-option", "--extra-arg=-Wno-unused-command-line-argument"]
    items = []
    for f in files:
        rc, out, err = run(cmd + [f] + ([] if cc else ["--"]), timeout=600)
        for line in out.splitlines():
            m = re.match(r"^(.+?):(\d+):\d+:\s+(warning|error):\s+(.*?)\s+\[([\w\-.,]+)\]$", line.strip())
            if m:
                items.append(Item("clang-tidy", m.group(1), m.group(2), "error" if m.group(3) == "error" else "warn",
                                  m.group(5), m.group(4)))
    return items


def run_framac(files, db):
    exe = which("frama-c")
    if not exe:
        return None
    incs, defs = flags_for(files, db)
    cpp = " ".join(["-I" + i for i in incs] + ["-D" + d for d in defs])
    cmd = [exe, "-eva", "-eva-precision", "1", "-eva-no-show-progress", "-machdep", "gcc_x86_32"]
    if cpp:
        cmd += ["-cpp-extra-args=" + cpp]
    rc, out, err = run(cmd + files, timeout=1800)
    items = []
    for line in (out + "\n" + err).splitlines():
        m = re.match(r"^\[(eva:alarm|eva|kernel)[^\]]*\]\s+(.+?):(\d+):\s*(Warning|Error)?:?\s*(.*)$", line.strip())
        if m:
            sev = "error" if m.group(4) == "Error" else "warn"
            items.append(Item("frama-c", m.group(2), m.group(3), sev, m.group(1), m.group(5).strip()))
    return items


def to_sarif(items, proj):
    rules = {}
    results = []
    for it in items:
        rid = "{}/{}".format(it.tool, it.rule)
        rules.setdefault(rid, {"id": rid, "shortDescription": {"text": it.rule}})
        results.append({"ruleId": rid, "level": {"error": "error", "warn": "warning"}.get(it.sev, "note"),
                        "message": {"text": it.msg},
                        "locations": [{"physicalLocation": {"artifactLocation": {"uri": rel(it.file, proj)},
                                                            "region": {"startLine": max(1, it.line)}}}]})
    return {"version": "2.1.0", "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [{"tool": {"driver": {"name": "firmware-agent-kit", "informationUri":
                                          "https://github.com/dogusyuksel/firmware-agent-kit", "rules": list(rules.values())}},
                      "results": results}]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true", help="all project sources and all lines")
    ap.add_argument("--all-lines", action="store_true", help="report unchanged lines too")
    ap.add_argument("--tools", help="comma list: lint,rtos,cppcheck,clang-tidy,frama-c,format")
    ap.add_argument("--misra", action="store_true")
    ap.add_argument("--max", type=int, default=40)
    ap.add_argument("--sarif", metavar="FILE")
    args = ap.parse_args()

    proj = os.getcwd()
    cfg, _ = load_config(proj)
    acfg = cfg.get("analysis") or {}
    tools = (args.tools.split(",") if args.tools else list(acfg.get("tools") or ["lint", "cppcheck", "clang-tidy"]))
    if args.all and "rtos" not in tools and not args.tools:
        tools.append("rtos")
    misra = args.misra or acfg.get("misra")

    if args.files:
        files = args.files
    elif args.all:
        files = [p for p in rtos_check.find_files(proj, exts=C_EXTS)]
    else:
        files = git_changed_files(proj)
    files = [f for f in files if f.lower().endswith(C_EXTS) and os.path.isfile(f) and not is_protected(rel(os.path.abspath(f), proj), cfg)]
    if not files and "rtos" not in tools:
        print("No C/C++ files to analyse (no changes vs HEAD). Use --all or pass files.")
        return 0
    srcs = [f for f in files if not f.lower().endswith((".h", ".hpp", ".hh"))]
    cc = find_compile_commands(proj, cfg)
    db = load_db(cc)
    rc_vals, _ = rtos_check.load_rtos_config(proj, cfg)
    if args.all:
        isr_map = rtos_check.global_isr_map(proj, cfg, rtos_check.project_sources(proj, cfg))
        rtos_check._store(proj, "isr_funcs", isr_map)
    else:
        isr_map = rtos_check.cached_isr_map(proj)

    items, notes = [], []
    runners = {
        "lint": lambda: run_lint(files, cfg, rc_vals, isr_map),
        "rtos": lambda: run_rtos_project(proj, cfg),
        "cppcheck": lambda: run_cppcheck(srcs, db, cfg, misra) if srcs else [],
        "clang-tidy": lambda: run_clang_tidy(srcs, cc, cfg) if srcs else [],
        "frama-c": lambda: run_framac(srcs, db) if srcs else [],
    }
    for t in tools:
        t = t.strip()
        if t == "format":
            for f in files:
                st, detail = format_file(f, None if (args.all or args.all_lines) else "git", check=True)
                if st == "needs-format":
                    items.append(Item("format", f, 1, "warn", "clang-format", detail + " (run tools/fw_format.py)"))
                elif st == "skipped":
                    notes.append("format: " + detail)
                    break
            continue
        if t not in runners:
            notes.append("unknown tool: " + t)
            continue
        res = runners[t]()
        if res is None:
            notes.append("{}: not installed - skipped (free/open source; see tools/fw_doctor.py --for analysis)".format(t))
        else:
            items += res

    # keep only changed lines unless asked otherwise
    if not (args.all or args.all_lines):
        cache = {}
        kept = []
        for it in items:
            if it.file == "(project)" or it.tool == "rtos":
                kept.append(it)
                continue
            key = os.path.normcase(os.path.abspath(it.file))
            if key not in cache:
                cache[key] = git_changed_lines(it.file) if os.path.isfile(it.file) else None
            ch = cache[key]
            if ch is None or it.line in ch:
                kept.append(it)
        hidden = len(items) - len(kept)
        items = kept
        if hidden:
            notes.append("{} finding(s) on unchanged lines hidden (pre-existing; --all-lines to show)".format(hidden))

    seen, uniq = set(), []
    for it in sorted(items, key=lambda i: (i.sev != "error", rel(i.file, proj), i.line)):
        k = (rel(it.file, proj), it.line, it.rule)
        if k not in seen:
            seen.add(k)
            uniq.append(it)

    if args.sarif:
        with open(args.sarif, "w", encoding="utf-8") as f:
            json.dump(to_sarif(uniq, proj), f, indent=1)
    counts = {}
    for it in uniq:
        counts[it.tool] = counts.get(it.tool, 0) + 1
    print("analysed {} file(s){}; findings: {}".format(
        len(files), " with " + rel(cc, proj) if cc else " (no compile_commands.json: include paths/defines unknown)",
        ", ".join("{} {}".format(v, k) for k, v in counts.items()) or "none"))
    for it in uniq[:args.max]:
        print("{}:{}: {} [{}:{}] {}".format(rel(it.file, proj), it.line, it.sev, it.tool, it.rule, it.msg[:220]))
    if len(uniq) > args.max:
        print("... {} more (--max N)".format(len(uniq) - args.max))
    for n in notes:
        print("note: " + n)
    if args.sarif:
        print("SARIF written to " + args.sarif)
    return 1 if any(i.sev == "error" for i in uniq) else 0


if __name__ == "__main__":
    sys.exit(main())
