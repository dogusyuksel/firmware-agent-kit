#!/usr/bin/env python3
"""Infer a C codebase's conventions so new code can match them - without reading dozens of files.

  python style_probe.py              # scan project sources (vendor/generated excluded)
  python style_probe.py src/drivers  # scan one directory
Reports: indentation, brace style, line length, naming per kind (functions, types, macros,
globals, statics), module prefixes, error-return style, comment style, include guards,
typical file header. Output is a short summary to follow when adding code.
"""

import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cparse import CFile  # noqa: E402
from fwlib import is_protected, load_config, rel  # noqa: E402

SKIP = {".git", "build", "node_modules", "managed_components", ".venv", "venv", "out", "Debug", "Release"}


def case_of(name):
    if re.match(r"^[A-Z][A-Z0-9_]*$", name):
        return "UPPER_SNAKE"
    if re.match(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$", name):
        return "lower_snake"
    if re.match(r"^[a-z][a-z0-9]*$", name):
        return "lower"
    if re.match(r"^[a-z]+[A-Z]\w*$", name) and "_" not in name:
        return "camelCase"
    if re.match(r"^[A-Z][a-z0-9]+[A-Z]?\w*$", name) and "_" not in name:
        return "PascalCase"
    if re.match(r"^[A-Z][A-Za-z0-9]*_[A-Za-z0-9_]+$", name):
        return "Prefix_Pascal"
    return "mixed"


def top(counter, n=2):
    total = sum(counter.values()) or 1
    return ", ".join("{} {:.0%}".format(k, v / total) for k, v in counter.most_common(n)) or "-"


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
    proj = os.getcwd()
    cfg, _ = load_config(proj)
    files = []
    for d, dirs, fs in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP and not x.startswith("build")]
        for f in fs:
            p = os.path.join(d, f)
            if f.endswith((".c", ".h")) and not is_protected(rel(p, proj), cfg):
                files.append(p)
    if not files:
        print("no C sources found")
        return 1
    files = sorted(files, key=os.path.getsize, reverse=True)[:120]

    indent, braces_fn, braces_ctl, linelen = collections.Counter(), collections.Counter(), collections.Counter(), []
    fn_case, static_fn_case, type_case, macro_case, glob_case, static_case = (collections.Counter() for _ in range(6))
    prefixes, err_ret, comments, guards, ptr_style = (collections.Counter() for _ in range(5))
    headers = collections.Counter()
    for p in files:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                src = fh.read()
        except OSError:
            continue
        lines = src.splitlines()
        for l in lines:
            m = re.match(r"^( +|\t+)\S", l)
            if m:
                ws = m.group(1)
                indent["tabs" if ws[0] == "\t" else "{} spaces".format(min(len(ws), 8) if len(ws) in (2, 3, 4, 8) else 4)] += 1
            if l.strip():
                linelen.append(len(l.expandtabs(4)))
        braces_fn["next line"] += len(re.findall(r"\)\s*\n\{", src))
        braces_fn["same line"] += len(re.findall(r"^\w[^\n;]*\)\s*\{\s*$", src, re.M))
        braces_ctl["same line"] += len(re.findall(r"\b(if|for|while|switch)\s*\(.*\)\s*\{\s*$", src, re.M))
        braces_ctl["next line"] += len(re.findall(r"\b(if|for|while|switch)\s*\(.*\)\s*\n\s*\{", src))
        comments["// line"] += len(re.findall(r"^\s*//", src, re.M))
        comments["/* block */"] += len(re.findall(r"^\s*/\*(?!\*)", src, re.M))
        comments["/** doxygen */"] += len(re.findall(r"^\s*/\*\*|@brief|\\brief", src, re.M))
        ptr_style["type *name"] += len(re.findall(r"\b\w+ \*\w", src))
        ptr_style["type* name"] += len(re.findall(r"\b\w+\* \w", src))
        if p.endswith(".h"):
            guards["#pragma once" if "#pragma once" in src else "#ifndef guard" if re.search(r"#ifndef\s+\w+_H", src) else "none"] += 1
        head = "\n".join(lines[:3])
        if re.search(r"copyright|license|@file|SPDX", head, re.I):
            headers[re.sub(r"\d{4}", "YYYY", lines[0].strip())[:60]] += 1
        cf = CFile(src)
        for name, f in cf.funcs.items():
            if name == "main":
                continue
            st = "static" in f.prefix.split()
            (static_fn_case if st else fn_case)[case_of(name)] += 1
            if not st:
                m = re.match(r"^([A-Za-z]+)_", name)
                if m:
                    prefixes[m.group(1)] += 1
            ret = f.prefix.split()[-1] if f.prefix.split() else ""
            if re.search(r"_t$|status|err|result|bool|int", ret, re.I):
                err_ret[ret] += 1
        for m in re.finditer(r"typedef\s+(?:struct|enum|union)?[^;{]*(?:\{[^}]*\})?\s*(\w+)\s*;", cf.code):
            type_case["*_t" if m.group(1).endswith("_t") else case_of(m.group(1))] += 1
        for m in re.finditer(r"^\s*#\s*define\s+(\w+)", src, re.M):
            macro_case[case_of(m.group(1))] += 1
        for m in re.finditer(r"^(static\s+)?(?:volatile\s+)?(?:const\s+)?[A-Za-z_]\w*\s+\**(\w+)\s*(?:\[[^\]]*\])?\s*(?:=[^;]*)?;", cf.code, re.M):
            name = m.group(2)
            (static_case if m.group(1) else glob_case)["{}{}".format(
                re.match(r"^(g_|s_|m_|_)?", name).group(1) or "", case_of(re.sub(r"^(g_|s_|m_|_)", "", name)))] += 1

    ll = sorted(linelen)
    p95 = ll[int(len(ll) * 0.95)] if ll else 0
    print("style of {} ({} files)".format(rel(root, proj) or ".", len(files)))
    print("indent        : " + top(indent))
    print("braces        : functions {} | control {}".format(top(braces_fn, 1), top(braces_ctl, 1)))
    print("line length   : p95 {} (max {})".format(p95, ll[-1] if ll else 0))
    print("pointer decl  : " + top(ptr_style, 1))
    print("public funcs  : " + top(fn_case) + ("; module prefixes: " + ", ".join(k + "_" for k, _ in prefixes.most_common(6)) if prefixes else ""))
    print("static funcs  : " + top(static_fn_case))
    print("types         : " + top(type_case))
    print("macros        : " + top(macro_case, 1))
    print("globals       : " + top(glob_case) + "   statics: " + top(static_case))
    print("return types  : " + ", ".join("{} x{}".format(k, v) for k, v in err_ret.most_common(4)))
    print("comments      : " + top(comments, 3))
    print("header guards : " + top(guards, 1))
    if headers:
        print("file header   : " + headers.most_common(1)[0][0])
    print("Match these when adding code; check one neighbouring file of the same module for details.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
