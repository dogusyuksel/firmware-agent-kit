"""PostToolUse(Bash): after a build, report flash/RAM usage and the delta vs the last build.

History is kept in <project>/.claude/fw-size-history.jsonl (add it to .gitignore
or commit it - your choice). Budgets come from .claude/firmware.json
(memory.flash_kb / memory.ram_kb) or, if absent, from the map file's
"Memory Configuration" table.
"""

import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from fwlib import load_config, post_tool_context, project_dir, read_input, rel, tool  # noqa: E402

BUILD_RE = re.compile(
    r"\b(make|ninja|cmake\s+--build|west\s+(build|flash)|scons|pio\s+run|meson\s+compile|headless-build)\b"
)
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".cache"}


def find_elf(proj, cfg):
    if cfg.get("elf"):
        p = os.path.join(proj, cfg["elf"])
        return p if os.path.isfile(p) else None
    best, best_m = None, 0
    base_depth = proj.rstrip("\\/").count(os.sep)
    for root, dirs, files in os.walk(proj):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if root.count(os.sep) - base_depth >= 4:
            dirs[:] = []
        for f in files:
            if f.endswith((".elf", ".axf", ".out")):
                p = os.path.join(root, f)
                m = os.path.getmtime(p)
                if m > best_m:
                    best, best_m = p, m
    return best


def size_of(elf, cfg):
    size = tool(cfg, "size")
    if not size:
        return None
    r = subprocess.run([size, "-B", "-d", elf], capture_output=True, text=True, timeout=20)
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    if r.returncode != 0 or len(lines) < 2:
        return None
    text, data, bss = (int(x) for x in lines[1].split()[:3])
    return {"text": text, "data": data, "bss": bss, "flash": text + data, "ram": data + bss}


def map_regions(map_path):
    """Parse 'Memory Configuration' from a GNU ld map -> (flash_bytes, main RAM bytes = largest RAM region)."""
    flash = ram = 0
    try:
        with open(map_path, "r", encoding="utf-8", errors="replace") as f:
            in_cfg = False
            for line in f:
                if line.startswith("Memory Configuration"):
                    in_cfg = True
                    continue
                if in_cfg and line.startswith("Linker script and memory map"):
                    break
                m = re.match(r"^(\S+)\s+0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)", line) if in_cfg else None
                if not m or m.group(1) == "*default*":
                    continue
                name, length = m.group(1).upper(), int(m.group(3), 16)
                if "FLASH" in name or "ROM" in name:
                    flash += length
                elif "RAM" in name:
                    ram = max(ram, length)   # .data/.bss live in the main RAM; RAM2/CCM are separate
    except OSError:
        pass
    return flash or None, ram or None


def last_entry(hist_path, elf_rel):
    last = None
    try:
        with open(hist_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("elf") == elf_rel:
                    last = e
    except OSError:
        pass
    return last


def fmt_delta(d):
    return "+{}".format(d) if d > 0 else str(d)


def main():
    payload = read_input()
    if payload.get("tool_name") != "Bash":
        return 0
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    proj = project_dir(payload)
    cfg, _ = load_config(proj)

    is_build = bool(BUILD_RE.search(cmd)) or bool(cfg.get("build") and cfg["build"].strip() in cmd)
    if not is_build:
        return 0

    elf = find_elf(proj, cfg)
    if not elf:
        return 0
    elf_rel = rel(elf, proj)
    mtime = os.path.getmtime(elf)
    hist = os.path.join(proj, ".claude", "fw-size-history.jsonl")
    prev = last_entry(hist, elf_rel)
    if prev and prev.get("mtime") == mtime:
        return 0  # ELF unchanged: build failed or was a no-op
    if time.time() - mtime > 600 and prev:
        return 0  # stale artifact, not produced by this build

    s = size_of(elf, cfg)
    if not s:
        return 0

    mem = cfg.get("memory") or {}
    flash_total = (mem.get("flash_kb") or 0) * 1024 or None
    ram_total = (mem.get("ram_kb") or 0) * 1024 or None
    if not (flash_total and ram_total):
        map_path = os.path.join(proj, cfg["map"]) if cfg.get("map") else os.path.splitext(elf)[0] + ".map"
        mf, mr = map_regions(map_path)
        flash_total, ram_total = flash_total or mf, ram_total or mr

    entry = dict(s, ts=int(time.time()), elf=elf_rel, mtime=mtime)
    os.makedirs(os.path.dirname(hist), exist_ok=True)
    with open(hist, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    budget = cfg.get("size_budget") or {}
    parts, block, notes = [], False, []
    for key, total, warn_k, max_k in (("flash", flash_total, "flash_pct_warn", "flash_pct_max"),
                                       ("ram", ram_total, "ram_pct_warn", "ram_pct_max")):
        txt = "{} {} B".format(key.upper(), s[key])
        if prev:
            txt += " ({} B)".format(fmt_delta(s[key] - prev.get(key, 0)))
        if total:
            pct = 100.0 * s[key] / total
            txt += " = {:.1f}% of {} KB".format(pct, total // 1024)
            if pct >= budget.get(max_k, 100):
                block = True
                notes.append("{} usage {:.1f}% exceeds the hard budget {}%.".format(key.upper(), pct, budget.get(max_k)))
            elif pct >= budget.get(warn_k, 100):
                notes.append("{} usage {:.1f}% is above the warning level {}%.".format(key.upper(), pct, budget.get(warn_k)))
        parts.append(txt)

    msg = "firmware-agent-kit size [{}]: {}  (text={} data={} bss={})".format(
        elf_rel, " | ".join(parts), s["text"], s["data"], s["bss"])
    if prev:
        growth = s["flash"] - prev.get("flash", 0)
        if growth > 2048:
            notes.append("Flash grew by {} B in one build - check for accidental printf/float/library pulls "
                         "(use the memory-footprint skill).".format(growth))
    if notes:
        msg += "\n" + "\n".join("  - " + n for n in notes)
    post_tool_context(msg, block=block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
