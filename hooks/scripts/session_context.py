"""SessionStart: compact project facts + working rules for firmware repos (silent elsewhere)."""

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from fwlib import emit, is_protected, load_config, project_dir, read_input, tool, which  # noqa: E402

TOOLS = [
    "cppcheck", "clang-format", "clang-tidy",
    "cmake", "ninja", "make", "bear", "pdftotext",
]
MARKERS = [
    (re.compile(r"(\.ld|\.icf|\.sct)$"), None),
    (re.compile(r"startup_\w+\.(s|S|c)$"), None),
    (re.compile(r"\.ioc$"), "stm32"),
    (re.compile(r"^stm32\w+\.h$", re.I), "stm32"),
    (re.compile(r"^(same70|samv7[01]|sams70)\w*\.h$", re.I), "samv71"),
    (re.compile(r"\.(cproject|uvprojx|ewp)$"), None),
    (re.compile(r"^FreeRTOSConfig\.h$"), "freertos"),
    (re.compile(r"^cmsis_os2?\.h$"), "cmsis-rtos2"),
]
NOTES_REL = ".claude/fw-notes.md"
NOTES_MAX = 4000
SKIP = {".git", "node_modules", ".venv", "venv", "build", "Debug", "Release", "out", "managed_components", ".pio"}

RULES = """Working rules (firmware-agent-kit):
- Non-trivial change (several files, new module, or anything touching ISRs, RTOS objects/priorities, clocks, linker script, flash layout)? First present a short plan (files, steps, risks, how it will be verified - /fw-plan format) and wait for approval. One-line fixes need no plan.
- Change only what was asked, with the fewest changed lines. No drive-by refactors, renames, reformatting, comment rewrites or include reordering.
- Existing project: new code must look like the surrounding code (naming, formatting, error handling, comments, file layout) - run style_probe.py instead of reading many files. New project: use the kit conventions (embedded-c skill). A project `*-conventions` skill (/fw-customize) overrides kit defaults.
- Public (non-static) functions must be thread-safe (mutex / critical section / single-owner task) and document whether they are ISR-safe.
- Other bugs/risks you notice: do NOT fix them unasked. End your reply with "Noticed (not changed):" + one line each (file:line - issue).
- Save tokens: Grep/Glob before Read; read line ranges of big files; skip vendor/generated code; pipe long tool output through tail/grep; prefer the kit scripts (build_info.py, pdf_search.py, map_analyzer.py, fw_analyze.py) over reading raw compile_commands/PDF/map files; delegate long PDF work to the datasheet-analyst agent.
- Never guess hardware facts (registers, pins, IRQ priorities, strapping): cite the device header, reference manual or schematic.
- A needed tool is missing? Show its install command (fw_doctor.py lists it) and ask once whether the user wants it. Never install it yourself: the user runs the command, then continue with the tool; if declined, skip that step and say so.
- After code changes, if a build command is configured, build once and report new warnings/errors; do not leave the build broken.
- Never run flash, erase or debug commands on hardware yourself; show them and let the user run them."""


def scan(proj, cfg, limit=10):
    found, tags = [], set()
    base = proj.rstrip("\\/").count(os.sep)
    for root, dirs, files in os.walk(proj):
        dirs[:] = [d for d in dirs if d not in SKIP]
        if root.count(os.sep) - base >= 4:
            dirs[:] = []
        for f in files:
            for rx, tag in MARKERS:
                if rx.search(f):
                    if tag:
                        tags.add(tag)
                    relp = os.path.relpath(os.path.join(root, f), proj).replace("\\", "/")
                    if len(found) < limit and not is_protected(relp, cfg):
                        found.append(relp)
                    break
    for f in ("CMakeLists.txt", "Makefile", "makefile"):
        p = os.path.join(proj, f)
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as fh:
                    txt = fh.read(200000)
            except OSError:
                continue
            if re.search(r"arm-none-eabi|mcpu=cortex", txt):
                found.append(f + " (cross toolchain)")
    return found, tags


def gcc_version(cfg):
    gcc = tool(cfg, "gcc")
    if not gcc or not (cfg.get("toolchain_prefix") or "").strip():
        return None
    try:
        r = subprocess.run([gcc, "--version"], capture_output=True, text=True, timeout=10)
        return r.stdout.splitlines()[0].strip() if r.stdout else None
    except Exception:
        return None


def main():
    payload = read_input()
    proj = project_dir(payload)
    cfg, cfg_path = load_config(proj)
    markers, tags = scan(proj, cfg)
    if not cfg_path and not markers and not tags and not os.path.isfile(os.path.join(proj, NOTES_REL)):
        return 0

    out = ["[firmware-agent-kit] firmware project."]
    if cfg.get("_config_error"):
        out.append("WARNING: bad config: " + cfg["_config_error"])
    family = cfg.get("family") or next((t for t in ("samv71", "stm32") if t in tags), None)
    rtos = (cfg.get("rtos") or {}).get("type") or ("freertos" if "freertos" in tags else None)
    facts = []
    if family:
        facts.append("family={} (mcu-family skill, {}.md)".format(family, family))
    if rtos:
        api = (cfg.get("rtos") or {}).get("api") or ("cmsis-rtos2" if "cmsis-rtos2" in tags else "native")
        facts.append("rtos={}/{} (freertos skill)".format(rtos, api))
    if facts:
        out.append(", ".join(facts))
    if cfg_path:
        for k in ("mcu", "core", "build", "elf", "compile_commands"):
            if cfg.get(k):
                out.append("{}: {}".format(k, cfg[k]))
        if cfg.get("datasheets"):
            out.append("docs: " + ", ".join(cfg["datasheets"]))
    else:
        out.append("No .claude/firmware.json - suggest /fw-init.")
    if markers:
        out.append("markers: " + ", ".join(markers))
    v = gcc_version(cfg)
    out.append("cc: " + (v or "{}gcc NOT on PATH".format(cfg.get("toolchain_prefix") or "")))
    have = [t for t in TOOLS if which(t)]
    out.append("tools: " + (", ".join(have) if have else "none of the common ones"))
    out.append("Guard hooks deny irreversible target ops and ask before erase/option-byte/GPNVM writes; never bypass them.")
    out.append(RULES)
    notes = os.path.join(proj, NOTES_REL)
    if os.path.isfile(notes):
        try:
            with open(notes, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            if len(text) > NOTES_MAX:
                text = text[:NOTES_MAX] + "\n... (truncated - read {} for the rest)".format(NOTES_REL)
            out.append("Project handoff notes ({}) - continue from here; update them with /fw-handoff:\n{}".format(NOTES_REL, text.strip()))
        except OSError:
            pass
    emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n".join(out)}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
