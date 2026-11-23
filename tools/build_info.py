#!/usr/bin/env python3
"""Compact summary of how a firmware project is built - instead of reading huge build files.

Reads compile_commands.json (CMake: -DCMAKE_EXPORT_COMPILE_COMMANDS=ON;
Make: `bear -- make` or `compiledb make`) and scans CMakeLists/Makefiles for linker scripts.

  python build_info.py                      # auto-find compile_commands.json, summary
  python build_info.py -p build/compile_commands.json
  python build_info.py --file src/uart.c    # exact flags for one translation unit
  python build_info.py --includes --defines # full lists (otherwise truncated)
"""

import argparse
import collections
import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fwlib import find_compile_commands, load_config  # noqa: E402

ARCH_PREFIXES = ("-mcpu", "-march", "-mthumb", "-mfpu", "-mfloat-abi", "-mabi", "-mlongcalls", "-mtune")
NOTABLE = ("-ffunction-sections", "-fdata-sections", "-flto", "-fno-common", "-fstack-usage", "-fno-exceptions",
           "-fno-rtti", "-fshort-enums", "-fsigned-char", "-funsigned-char", "-nostdlib", "-ffreestanding")


def split_cmd(entry):
    if "arguments" in entry:
        return list(entry["arguments"])
    cmd = entry.get("command", "")
    try:
        return shlex.split(cmd)
    except ValueError:
        return cmd.split()


def unquote(a):
    """Drop one pair of surrounding quotes; keep quotes that belong to the value (-DVERSION="1.0")."""
    return a[1:-1] if len(a) > 1 and a[0] == a[-1] == '"' else a


def norm_args(args, directory):
    """Return dict of interesting parts of one compile command."""
    info = {"compiler": os.path.basename(args[0]) if args else "?", "defines": [], "includes": [], "arch": [],
            "opt": None, "std": None, "warn": [], "notable": [], "other": []}
    i = 0
    while i < len(args):
        a = unquote(args[i])
        nxt = unquote(args[i + 1]) if i + 1 < len(args) else ""
        if a in ("-D", "-I", "-isystem", "-include", "-o", "-c", "-MF", "-MT", "-MQ"):
            if a == "-D":
                info["defines"].append(nxt)
            elif a in ("-I", "-isystem"):
                info["includes"].append(os.path.normpath(os.path.join(directory, nxt)))
            i += 2
            continue
        if a.startswith("-D"):
            info["defines"].append(a[2:])
        elif a.startswith("-I"):
            info["includes"].append(os.path.normpath(os.path.join(directory, a[2:])))
        elif a.startswith("-isystem"):
            info["includes"].append(os.path.normpath(os.path.join(directory, a[8:])))
        elif a.startswith(ARCH_PREFIXES):
            info["arch"].append(a)
        elif re.match(r"^-O[0-3sgz]?$", a):
            info["opt"] = a
        elif a.startswith("-std="):
            info["std"] = a[5:]
        elif a.startswith("-W") and not a.startswith(("-Wl,", "-Wa,", "-Wp,")):
            info["warn"].append(a)
        elif a in NOTABLE or a.startswith("--specs"):
            info["notable"].append(a)
        i += 1
    return info


def rel(p, root):
    try:
        r = os.path.relpath(p, root)
        return p if r.startswith("..\\..") or r.startswith("../..") else r.replace("\\", "/")
    except ValueError:
        return p


def linker_scripts(proj):
    hits = set()
    for root, dirs, files in os.walk(proj):
        dirs[:] = [d for d in dirs if d not in {".git", "build", "node_modules", "managed_components"}]
        if root.count(os.sep) - proj.count(os.sep) > 3:
            dirs[:] = []
        for f in files:
            if f in ("CMakeLists.txt", "Makefile", "makefile") or f.endswith((".cmake", ".mk")):
                try:
                    with open(os.path.join(root, f), "r", encoding="utf-8", errors="replace") as fh:
                        for m in re.finditer(r"-T\s*\"?([^\s\"\)]+\.ld)|([\w./${}-]+\.ld)\b", fh.read(300000)):
                            hits.add((m.group(1) or m.group(2)) + "  (" + rel(os.path.join(root, f), proj) + ")")
                except OSError:
                    pass
    return sorted(hits)[:8]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-p", "--compile-commands")
    ap.add_argument("--file", help="show flags for one source file")
    ap.add_argument("--includes", action="store_true", help="print all include dirs")
    ap.add_argument("--defines", action="store_true", help="print all defines")
    args = ap.parse_args()

    proj = os.getcwd()
    cfg, _ = load_config(proj)
    cc = args.compile_commands or find_compile_commands(proj, cfg)
    if not cc or not os.path.isfile(cc):
        print("compile_commands.json not found. Generate it:\n"
              "  CMake  : cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON\n"
              "  Make   : bear -- make\n"
              "  STM32CubeIDE: use the CMake export or bear with the headless build")
        ls = linker_scripts(proj)
        if ls:
            print("Linker scripts referenced: " + "; ".join(ls))
        return 1
    with open(cc, "r", encoding="utf-8") as f:
        db = json.load(f)
    entries = [(e, norm_args(split_cmd(e), e.get("directory", "."))) for e in db]
    if not entries:
        print("empty compile database")
        return 1

    if args.file:
        target = os.path.normcase(os.path.abspath(args.file))
        for e, info in entries:
            src = os.path.normcase(os.path.normpath(os.path.join(e.get("directory", "."), e["file"])))
            if src == target or src.endswith(os.path.normcase(os.path.normpath(args.file))):
                print("file    : {}".format(e["file"]))
                for k in ("compiler", "arch", "opt", "std", "notable", "warn"):
                    print("{:<8}: {}".format(k, info[k] if isinstance(info[k], str) or info[k] is None else " ".join(info[k])))
                print("defines : " + " ".join(info["defines"]))
                print("includes:\n  " + "\n  ".join(rel(i, proj) for i in info["includes"]))
                return 0
        print("not in compile database: " + args.file)
        return 1

    n = len(entries)
    count = collections.Counter
    comp, arch, opt, std = count(), count(), count(), count()
    defs, incs, warn, notable = count(), count(), count(), count()
    for _, i in entries:
        comp[i["compiler"]] += 1
        arch[" ".join(sorted(set(i["arch"])))] += 1
        opt[i["opt"]] += 1
        std[i["std"]] += 1
        defs.update(set(i["defines"]))
        incs.update(set(i["includes"]))
        warn.update(set(i["warn"]))
        notable.update(set(i["notable"]))

    def common(c, limit):
        allx = [k for k, v in c.most_common() if v == n]
        some = [k for k, v in c.most_common() if v != n]
        return allx, some, limit

    print("compile db : {} ({} TUs)".format(rel(cc, proj), n))
    print("compiler   : " + ", ".join("{} x{}".format(k, v) for k, v in comp.most_common(3)))
    print("arch       : " + " | ".join("{} x{}".format(k or "-", v) for k, v in arch.most_common(3)))
    print("opt / std  : {} / {}".format(", ".join(k or "(default)" for k in opt), ", ".join(k or "(default)" for k in std)))
    print("notable    : " + " ".join(k for k, _ in notable.most_common()))
    print("warnings   : " + " ".join(k for k, v in warn.most_common() if v == n))
    d_all, d_some, _ = common(defs, 0)
    lim = None if args.defines else 25
    print("defines (all TUs, {}): {}".format(len(d_all), " ".join(d_all[:lim]) + (" ..." if lim and len(d_all) > lim else "")))
    if d_some:
        print("defines (some TUs, {}): {}".format(len(d_some), " ".join(d_some[:lim or None][:10 if lim else None]) + (" ..." if lim and len(d_some) > 10 else "")))
    i_all, i_some, _ = common(incs, 0)
    lim = None if args.includes else 20
    print("include dirs (all TUs, {}):".format(len(i_all)))
    for p in i_all[:lim]:
        print("  " + rel(p, proj))
    if lim and len(i_all) > lim:
        print("  ... {} more (--includes)".format(len(i_all) - lim))
    if i_some:
        print("include dirs (some TUs): {}".format(len(i_some)))
    srcdirs = count(os.path.dirname(rel(os.path.normpath(os.path.join(e.get("directory", "."), e["file"])), proj)) for e, _ in entries)
    print("source dirs: " + ", ".join("{} ({})".format(k or ".", v) for k, v in srcdirs.most_common(12)))
    ls = linker_scripts(proj)
    if ls:
        print("linker     : " + "; ".join(ls))
    return 0


if __name__ == "__main__":
    sys.exit(main())
