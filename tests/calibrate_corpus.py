#!/usr/bin/env python3
"""False-positive calibration: run the kit's checkers on official RTOS example code.

Sparse-clones (read-only, scripts are never executed) FreeRTOS demos, ESP-IDF examples and
STM32CubeF4 FreeRTOS applications into a work directory and prints findings per rule.
Well-maintained vendor examples should produce no error-level findings; investigate any that appear.

  python tests/calibrate_corpus.py [--dir /tmp/fwkit-corpus] [--show RTOS-011,RTOS-070]
Network access and git are required. Not part of the unit test run.
"""

import argparse
import collections
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import fw_lint  # noqa: E402
import rtos_check  # noqa: E402
from fwlib import DEFAULT_CONFIG  # noqa: E402

CORPUS = [
    ("freertos", "https://github.com/FreeRTOS/FreeRTOS.git",
     ["FreeRTOS/Demo/Common/Minimal", "FreeRTOS/Demo/CORTEX_M4F_STM32F407ZG-SK",
      "FreeRTOS/Demo/CORTEX_M7_SAMV71_Xplained_AtmelStudio"]),
    ("esp-idf", "https://github.com/espressif/esp-idf.git",
     ["examples/system/freertos", "examples/peripherals/gpio", "examples/peripherals/uart",
      "examples/peripherals/timer_group", "examples/system/esp_timer"]),
    ("cubef4", "https://github.com/STMicroelectronics/STM32CubeF4.git",
     ["Projects/STM32F4-Discovery/Applications/FreeRTOS", "Projects/STM32446E_EVAL/Applications/FreeRTOS"]),
]


def fetch(workdir):
    for name, url, paths in CORPUS:
        dst = os.path.join(workdir, name)
        if os.path.isdir(dst):
            continue
        subprocess.check_call(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse", url, dst])
        subprocess.check_call(["git", "-C", dst, "sparse-checkout", "set"] + paths)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=os.path.join(tempfile.gettempdir(), "fwkit-corpus"))
    ap.add_argument("--show", default="", help="comma-separated rule IDs to print samples for")
    args = ap.parse_args()
    os.makedirs(args.dir, exist_ok=True)
    fetch(args.dir)

    cfg = dict(DEFAULT_CONFIG)
    cfg["lint"] = dict(cfg["lint"], forbid_dynamic_alloc=False)
    counts, samples, nfiles = collections.Counter(), collections.defaultdict(list), 0
    for root, _, files in os.walk(args.dir):
        if os.sep + ".git" in root:
            continue
        for f in files:
            if not f.endswith(".c"):
                continue
            p = os.path.join(root, f)
            nfiles += 1
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                src = fh.read()
            for x in fw_lint.lint_source(src, cfg) + rtos_check.check_source(src, cfg, {}):
                counts[(x.rule, x.sev)] += 1
                if len(samples[x.rule]) < 8:
                    samples[x.rule].append("{}:{}: {}".format(os.path.relpath(p, args.dir), x.line, x.msg[:140]))
    print("files: {}".format(nfiles))
    for (rule, sev), n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print("{:>5}  {} {}".format(n, rule, sev))
    errors = sum(n for (r, s), n in counts.items() if s == "error")
    for r in [x for x in args.show.split(",") if x]:
        print("\n== " + r)
        for s in samples.get(r, []):
            print("  " + s)
    print("\nerror-level findings: {}".format(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
