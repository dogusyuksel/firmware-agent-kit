#!/usr/bin/env python3
"""clang-format only the lines you changed (vs git HEAD), so diffs stay minimal.

  python fw_format.py                 # format changed lines of all changed C/C++ files
  python fw_format.py src/uart.c      # changed lines of given files
  python fw_format.py --check         # report only (CI / pre-commit)
  python fw_format.py --whole new.c   # whole file (only for new files or when asked)
Requires clang-format and a .clang-format in the project (never imposes a style).
Vendor paths from .claude/firmware.json guard.protected_paths are skipped.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fwlib import C_EXTS, git_changed_files, is_protected, load_config, rel  # noqa: E402
from fwfmt import format_file  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--whole", action="store_true")
    args = ap.parse_args()
    proj = os.getcwd()
    cfg, _ = load_config(proj)
    files = args.files or [f for f in git_changed_files(proj) if f.lower().endswith(C_EXTS)]
    files = [f for f in files if not is_protected(rel(os.path.abspath(f), proj), cfg)]
    if not files:
        print("no changed C/C++ files")
        return 0
    bad = 0
    for f in files:
        status, detail = format_file(f, None if args.whole else "git", check=args.check)
        if status == "skipped" and "not installed" in detail:
            print("clang-format not installed (free/open source) - see: python tools/fw_doctor.py --for format")
            return 2
        if status != "clean":
            print("{:<13} {} {}".format(status, rel(f, proj), detail))
        bad += status == "needs-format"
    print("{} file(s) checked{}".format(len(files), ", {} need formatting".format(bad) if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
