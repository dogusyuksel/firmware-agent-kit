#!/usr/bin/env python3
"""Check which tools firmware-agent-kit can use on this machine and how to install the missing ones.

Linux only (Debian/Ubuntu commands; on Windows run the kit inside WSL). Every tool listed is
free and open source.

  python fw_doctor.py                 # table of everything
  python fw_doctor.py --for analysis  # only tools needed by one area
  python fw_doctor.py --missing       # only missing tools
  python fw_doctor.py --json
"""

import argparse
import json
import shutil
import subprocess
import sys

# name: (commands to probe, license, areas, purpose, install command on Debian/Ubuntu)
TOOLS = {
    "python": (["python3"], "PSF-2.0", ["core"], "runs all kit hooks and scripts", "sudo apt install -y python3"),
    "git": (["git"], "GPL-2.0", ["core"], "changed-line detection, diffs for review", "sudo apt install -y git"),
    "arm-none-eabi-gcc": (["arm-none-eabi-gcc"], "GPL-3.0", ["build"], "Cortex-M cross compiler",
                          "sudo apt install -y gcc-arm-none-eabi libnewlib-arm-none-eabi"),
    "cmake": (["cmake"], "BSD-3-Clause", ["build"], "build system", "sudo apt install -y cmake"),
    "ninja": (["ninja"], "Apache-2.0", ["build"], "fast CMake generator", "sudo apt install -y ninja-build"),
    "make": (["make"], "GPL-3.0", ["build"], "Makefile projects", "sudo apt install -y make"),
    "bear": (["bear"], "GPL-3.0", ["build"], "compile_commands.json for Make projects", "sudo apt install -y bear"),
    "cppcheck": (["cppcheck"], "GPL-3.0", ["analysis"], "static analysis + MISRA C:2012 addon", "sudo apt install -y cppcheck"),
    "clang-tidy": (["clang-tidy"], "Apache-2.0 WITH LLVM-exception", ["analysis"], "static analysis (clang-analyzer, bugprone, cert)",
                   "sudo apt install -y clang-tidy"),
    "clang-format": (["clang-format"], "Apache-2.0 WITH LLVM-exception", ["format"], "C formatter (changed lines only)",
                     "sudo apt install -y clang-format"),
    "pdftotext": (["pdftotext"], "GPL-2.0", ["docs"], "fast datasheet/schematic page search (poppler)", "sudo apt install -y poppler-utils"),
    "pypdf": ([], "BSD-3-Clause", ["docs"], "pure-Python fallback for PDF search", "python3 -m pip install --user pypdf"),
    "mmdc": (["mmdc"], "MIT", ["docs"], "render Mermaid diagrams to SVG/PNG (optional)",
             "npm install -g @mermaid-js/mermaid-cli   (needs Node.js: sudo apt install -y nodejs npm)"),
}

AREAS = sorted({a for t in TOOLS.values() for a in t[2]})


def probe(name, cmds):
    if name == "pypdf":
        try:
            import pypdf  # noqa: F401
            return "pypdf", getattr(pypdf, "__version__", "")
        except ImportError:
            return None, None
    for c in cmds:
        p = shutil.which(c)
        if not p:
            continue
        ver = ""
        for flag in ("--version", "-version", "version"):
            try:
                r = subprocess.run([p, flag], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
                txt = (r.stdout or r.stderr).strip().splitlines()
                if txt:
                    ver = txt[0][:70]
                    break
            except Exception:
                continue
        return c, ver
    return None, None


def install_cmd(spec):
    return spec[4]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--for", dest="area", choices=AREAS)
    ap.add_argument("--missing", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = []
    for name, spec in TOOLS.items():
        if args.area and args.area not in spec[2]:
            continue
        found, ver = probe(name, spec[0])
        if args.missing and found:
            continue
        rows.append({"tool": name, "installed": bool(found), "version": ver or "", "license": spec[1],
                     "areas": spec[2], "purpose": spec[3], "install": None if found else install_cmd(spec)})
    if args.json:
        print(json.dumps(rows, indent=1))
        return 0
    for r in rows:
        mark = "ok " if r["installed"] else "-- "
        print("{}{:<18} {:<11} {}".format(mark, r["tool"], ",".join(r["areas"]), r["version"] if r["installed"] else r["purpose"]))
        if not r["installed"]:
            print("   {:<18} install ({}): {}".format("", r["license"], r["install"]))
    miss = sum(1 for r in rows if not r["installed"])
    print("\n{} missing of {}. All listed tools are free and open source.".format(miss, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
