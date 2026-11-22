#!/usr/bin/env python3
"""Summarise a GNU ld .map file: biggest objects and symbols by flash/RAM, plus diffs.

Usage:
  python map_analyzer.py build/app.map                 # top 25 objects & symbols
  python map_analyzer.py build/app.map --top 50 --by symbol
  python map_analyzer.py old.map new.map               # what grew/shrank between two builds
Stdlib only. Generate the map with -Wl,-Map=app.map (add -Wl,--cref for cross-refs).
"""

import argparse
import collections
import os
import re
import sys

FLASH_PREFIXES = (".text", ".rodata", ".isr_vector", ".ARM", ".init", ".fini", ".ramfunc", ".glue", ".vfp11")
RAM_ONLY_PREFIXES = (".bss", "COMMON", ".noinit", ".tbss")
DATA_PREFIXES = (".data", ".tdata", ".sdata")

INPUT_ONE_LINE = re.compile(r"^ (\S+)\s+0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)\s+(.+)$")
INPUT_NAME_ONLY = re.compile(r"^ (\.\S+|COMMON)\s*$")
INPUT_CONT = re.compile(r"^\s+0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)\s+(.+)$")


def classify(section):
    if section.startswith(DATA_PREFIXES) or section == ".ramfunc":
        return "data"  # costs flash (init image) and RAM
    if section.startswith(RAM_ONLY_PREFIXES):
        return "bss"
    if section.startswith(FLASH_PREFIXES):
        return "text"
    return None


def short_obj(path):
    path = path.strip().replace("\\", "/")
    m = re.match(r"(.*/)?([^/]+\.a)\((.+)\)$", path)
    if m:
        return "{}({})".format(m.group(2), m.group(3))
    return os.path.basename(path) if "/" in path and len(path) > 60 else path


def symbol_name(section):
    for p in (".text.", ".rodata.", ".data.", ".bss.", ".noinit.", ".ramfunc."):
        if section.startswith(p):
            return section[len(p):]
    return section


def parse(map_path):
    """Return list of (section, size, object)."""
    entries = []
    with open(map_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.startswith("Linker script and memory map"))
    except StopIteration:
        start = 0
    pending = None
    for line in lines[start:]:
        if pending:
            m = INPUT_CONT.match(line)
            if m:
                entries.append((pending, int(m.group(1), 16), int(m.group(2), 16), m.group(3)))
                pending = None
                continue
            pending = None
        m = INPUT_ONE_LINE.match(line)
        if m and (m.group(1).startswith(".") or m.group(1) == "COMMON"):
            entries.append((m.group(1), int(m.group(2), 16), int(m.group(3), 16), m.group(4)))
            continue
        m = INPUT_NAME_ONLY.match(line)
        if m:
            pending = m.group(1)
    out = []
    for sec, addr, size, obj in entries:
        # addr 0 = discarded/unplaced input section (unless your flash really starts at 0)
        if size == 0 or addr == 0 or obj.startswith("load address") or classify(sec) is None:
            continue
        out.append((sec, size, short_obj(obj)))
    return out


def aggregate(entries, by):
    agg = collections.defaultdict(lambda: {"text": 0, "data": 0, "bss": 0})
    for sec, size, obj in entries:
        key = obj if by == "object" else "{}  [{}]".format(symbol_name(sec), obj)
        agg[key][classify(sec)] += size
    return agg


def flash_ram(v):
    return v["text"] + v["data"], v["data"] + v["bss"]


def report(agg, top, title):
    rows = sorted(agg.items(), key=lambda kv: -(flash_ram(kv[1])[0] + flash_ram(kv[1])[1]))
    tot_f = sum(flash_ram(v)[0] for v in agg.values())
    tot_r = sum(flash_ram(v)[1] for v in agg.values())
    print("== {} (total flash {} B, RAM {} B) ==".format(title, tot_f, tot_r))
    print("{:>8} {:>8} {:>8} {:>8}  {}".format("flash", "ram", "data", "bss", "name"))
    for name, v in rows[:top]:
        f_, r_ = flash_ram(v)
        print("{:>8} {:>8} {:>8} {:>8}  {}".format(f_, r_, v["data"], v["bss"], name))
    print()


def diff(a, b, top):
    keys = set(a) | set(b)
    zero = {"text": 0, "data": 0, "bss": 0}
    rows = []
    for k in keys:
        fa, ra = flash_ram(a.get(k, zero))
        fb, rb = flash_ram(b.get(k, zero))
        if fa != fb or ra != rb:
            rows.append((fb - fa, rb - ra, k))
    rows.sort(key=lambda r: -(abs(r[0]) + abs(r[1])))
    print("== diff (new - old) ==")
    print("{:>8} {:>8}  {}".format("dflash", "dram", "name"))
    for df, dr, k in rows[:top]:
        print("{:>+8} {:>+8}  {}".format(df, dr, k))
    print("{:>+8} {:>+8}  TOTAL".format(sum(r[0] for r in rows), sum(r[1] for r in rows)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("maps", nargs="+", help="one map file, or two (old new) to diff")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--by", choices=("object", "symbol", "both"), default="both")
    args = ap.parse_args()

    if len(args.maps) == 2:
        by = "object" if args.by == "object" else "symbol"
        diff(aggregate(parse(args.maps[0]), by), aggregate(parse(args.maps[1]), by), args.top)
        return 0
    entries = parse(args.maps[0])
    if not entries:
        print("No input sections parsed - is this a GNU ld map file?", file=sys.stderr)
        return 1
    if args.by in ("object", "both"):
        report(aggregate(entries, "object"), args.top, "by object file")
    if args.by in ("symbol", "both"):
        report(aggregate(entries, "symbol"), args.top, "by symbol (input section)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
