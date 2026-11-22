#!/usr/bin/env python3
"""Check which tools firmware-agent-kit can use on this machine and how to install the missing ones.

Every tool listed is free and open source; install hints use OSS package managers
(winget, apt, brew, pip, gem, npm, opam) or upstream releases.

  python fw_doctor.py                 # table of everything
  python fw_doctor.py --for analysis  # only tools needed by one area
  python fw_doctor.py --missing       # only missing tools
  python fw_doctor.py --json
  python fw_doctor.py --install cppcheck   # run the install command for this OS (ask the user first!)
"""

import argparse
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys

# name: (commands to probe, license, areas, purpose, {os: install command})
#   os keys: windows, linux (Debian/Ubuntu apt), mac (Homebrew), any (cross-platform: pip/gem/npm/opam)
TOOLS = {
    "python": (["python3", "python", "py"], "PSF-2.0", ["core"], "runs all kit hooks and scripts",
               {"windows": "winget install -e --id Python.Python.3.12", "linux": "sudo apt install -y python3", "mac": "brew install python"}),
    "git": (["git"], "GPL-2.0", ["core"], "changed-line detection, diffs for review",
            {"windows": "winget install -e --id Git.Git", "linux": "sudo apt install -y git", "mac": "brew install git"}),
    "arm-none-eabi-gcc": (["arm-none-eabi-gcc"], "GPL-3.0", ["build"], "cross compiler for STM32 / SAMV71 (Cortex-M)",
                          {"windows": "winget install -e --id Arm.GnuArmEmbeddedToolchain", "linux": "sudo apt install -y gcc-arm-none-eabi libnewlib-arm-none-eabi",
                           "mac": "brew install --cask gcc-arm-embedded"}),
    "cmake": (["cmake"], "BSD-3-Clause", ["build"], "build system",
              {"windows": "winget install -e --id Kitware.CMake", "linux": "sudo apt install -y cmake", "mac": "brew install cmake"}),
    "ninja": (["ninja"], "Apache-2.0", ["build"], "fast CMake generator",
              {"windows": "winget install -e --id Ninja-build.Ninja", "linux": "sudo apt install -y ninja-build", "mac": "brew install ninja"}),
    "make": (["make", "mingw32-make"], "GPL-3.0", ["build"], "Makefile projects",
             {"windows": "winget install -e --id ezwinports.make", "linux": "sudo apt install -y make", "mac": "xcode-select --install"}),
    "idf.py": (["idf.py"], "Apache-2.0", ["esp32"], "ESP-IDF build/flash/monitor (or use the esp-idf container)",
               {"any": "see https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/ (or: python tools/fw_container.py build esp-idf)"}),
    "openocd": (["openocd"], "GPL-2.0", ["flash"], "flash/debug STM32 & SAMV71 (atsamv driver)",
                {"windows": "download xPack OpenOCD: https://github.com/xpack-dev-tools/openocd-xpack/releases", "linux": "sudo apt install -y openocd", "mac": "brew install open-ocd"}),
    "pyocd": (["pyocd"], "Apache-2.0", ["flash"], "flash/debug via CMSIS-DAP/ST-LINK",
              {"any": "python -m pip install --user pyocd"}),
    "st-flash": (["st-flash"], "BSD-3-Clause", ["flash"], "ST-LINK flashing (stlink-org)",
                 {"windows": "download: https://github.com/stlink-org/stlink/releases", "linux": "sudo apt install -y stlink-tools", "mac": "brew install stlink"}),
    "esptool": (["esptool.py", "esptool"], "GPL-2.0", ["flash", "esp32"], "ESP32 flashing",
                {"any": "python -m pip install --user esptool"}),
    "bossac": (["bossac"], "BSD-3-Clause", ["flash"], "SAM flashing over SAM-BA",
               {"windows": "download: https://github.com/shumatech/BOSSA/releases", "linux": "sudo apt install -y bossa-cli", "mac": "brew install --cask bossa"}),
    "gdb": (["arm-none-eabi-gdb", "gdb-multiarch"], "GPL-3.0", ["flash"], "on-target debugging",
            {"windows": "included with the Arm GNU toolchain", "linux": "sudo apt install -y gdb-multiarch", "mac": "included with gcc-arm-embedded"}),
    "cppcheck": (["cppcheck"], "GPL-3.0", ["analysis"], "static analysis + MISRA C:2012 addon",
                 {"windows": "winget install -e --id Cppcheck.Cppcheck", "linux": "sudo apt install -y cppcheck", "mac": "brew install cppcheck"}),
    "clang-tidy": (["clang-tidy"], "Apache-2.0 WITH LLVM-exception", ["analysis"], "static analysis (clang-analyzer, bugprone, cert)",
                   {"windows": "winget install -e --id LLVM.LLVM", "linux": "sudo apt install -y clang-tidy", "mac": "brew install llvm"}),
    "clang-format": (["clang-format"], "Apache-2.0 WITH LLVM-exception", ["format"], "C formatter (changed lines only)",
                     {"windows": "winget install -e --id LLVM.LLVM", "linux": "sudo apt install -y clang-format", "mac": "brew install clang-format"}),
    "frama-c": (["frama-c"], "LGPL-2.1", ["analysis"], "formal analysis (EVA: runtime errors, WP: proofs)",
                {"windows": "use WSL or the frama-c container: python tools/fw_container.py build frama-c", "linux": "sudo apt install -y frama-c-base  (or: opam install frama-c)",
                 "mac": "opam install frama-c"}),
    "ceedling": (["ceedling"], "MIT", ["test"], "unit tests with Unity + CMock",
                 {"windows": "winget install -e --id RubyInstallerTeam.RubyWithDevKit.3.3 ; gem install ceedling", "linux": "sudo apt install -y ruby && sudo gem install ceedling",
                  "mac": "brew install ruby && gem install ceedling"}),
    "gcovr": (["gcovr"], "BSD-3-Clause", ["test"], "coverage reports for host tests",
              {"any": "python -m pip install --user gcovr"}),
    "valgrind": (["valgrind"], "GPL-2.0", ["test"], "leak/memory checks of host tests (Linux; use ASan elsewhere)",
                 {"linux": "sudo apt install -y valgrind", "windows": "not available - use -fsanitize=address in host tests or the arm-dev container",
                  "mac": "not available on Apple Silicon - use -fsanitize=address"}),
    "renode": (["renode"], "MIT", ["itest"], "simulation / integration tests (Robot Framework via renode-test)",
               {"windows": "download the .msi/.zip: https://github.com/renode/renode/releases (or the renode container)", "linux": "download the .deb: https://github.com/renode/renode/releases",
                "mac": "brew install --cask renode"}),
    "qemu-system-arm": (["qemu-system-arm"], "GPL-2.0", ["itest"], "Cortex-M emulation (limited board set)",
                        {"windows": "winget install -e --id SoftwareFreedomConservancy.QEMU", "linux": "sudo apt install -y qemu-system-arm", "mac": "brew install qemu"}),
    "pdftotext": (["pdftotext"], "GPL-2.0", ["docs"], "fast datasheet/schematic page search (poppler)",
                  {"windows": "winget install -e --id oschwartz10612.Poppler", "linux": "sudo apt install -y poppler-utils", "mac": "brew install poppler"}),
    "pypdf": ([], "BSD-3-Clause", ["docs"], "pure-Python fallback for PDF search", {"any": "python -m pip install --user pypdf"}),
    "mmdc": (["mmdc"], "MIT", ["docs"], "render Mermaid diagrams to SVG/PNG (optional)",
             {"any": "npm install -g @mermaid-js/mermaid-cli   (needs Node.js: winget install -e --id OpenJS.NodeJS.LTS)"}),
    "podman": (["podman", "docker"], "Apache-2.0", ["container"], "run builds/tests/analysis in containers (Podman, or Docker Engine)",
               {"windows": "winget install -e --id RedHat.Podman ; podman machine init ; podman machine start", "linux": "sudo apt install -y podman", "mac": "brew install podman && podman machine init && podman machine start"}),
}

AREAS = sorted({a for t in TOOLS.values() for a in t[2]})


def os_key():
    s = platform.system().lower()
    return "windows" if s.startswith(("win", "cygwin", "msys")) else "mac" if s == "darwin" else "linux"


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
        if c in ("python3", "python", "py"):  # skip the Windows Store stub
            try:
                r = subprocess.run([p, "-c", "import sys;print(sys.version.split()[0])"], capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    continue
                return c, r.stdout.strip()
            except Exception:
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
    hints = spec[4]
    return hints.get(os_key()) or hints.get("any")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--for", dest="area", choices=AREAS)
    ap.add_argument("--missing", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--install", metavar="TOOL", help="run the OS install command for TOOL (only after the user agreed)")
    args = ap.parse_args()

    if args.install:
        spec = TOOLS.get(args.install)
        cmd = spec and install_cmd(spec)
        if not cmd or cmd.startswith(("download", "see ", "use ", "not available", "included")):
            print("No automatic install for {} on {}: {}".format(args.install, os_key(), cmd))
            return 1
        print("+ " + cmd)
        rc = subprocess.call(cmd, shell=True)
        if "pip install --user" in cmd:
            import sysconfig
            try:
                scheme = sysconfig.get_preferred_scheme("user")
            except AttributeError:  # Python < 3.10
                scheme = "nt_user" if os.name == "nt" else "posix_user"
            print("note: pip --user puts commands in {} - add it to PATH if the tool is not found.".format(
                sysconfig.get_path("scripts", scheme)))
        elif cmd.startswith("winget"):
            print("note: open a new terminal (or restart the IDE) so PATH changes take effect.")
        return rc

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
            print("   {:<18} install ({}, {}): {}".format("", os_key(), r["license"], r["install"]))
    miss = sum(1 for r in rows if not r["installed"])
    print("\n{} missing of {}. All listed tools are free and open source.".format(miss, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
