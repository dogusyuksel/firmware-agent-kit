#!/usr/bin/env python3
"""Requirements traceability: requirement IDs -> implementing code -> verifying tests.

Tags in sources (any comment style):
  @req   <ID>[, <ID>...]   implementation of a requirement
  @verifies <ID>[, ...]    test that verifies a requirement (in test files)
Requirements list (optional): CSV with an 'id' column (and optional 'title'), or a Markdown/text
file - any token matching --id-regex is taken as an ID.

  python trace_check.py --reqs docs/requirements.csv            # matrix summary + gaps
  python trace_check.py --reqs docs/srs.md --matrix trace.csv   # also write the full matrix
  python trace_check.py                                         # tags only (no requirements file)
Exit code 1 if requirements lack implementation/tests or tags reference unknown IDs.
"""

import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fwlib import is_protected, load_config, rel  # noqa: E402

SRC_EXT = (".c", ".h", ".cpp", ".hpp", ".cc", ".s", ".S", ".robot", ".py")
SKIP = {".git", "build", "node_modules", "managed_components", ".venv", "venv", "out"}


def load_reqs(path, id_rx):
    reqs = {}
    if path.lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8-sig") as f:
            rd = csv.DictReader(f)
            key = next((k for k in rd.fieldnames or [] if k.strip().lower() in ("id", "req", "requirement", "req_id")), None)
            title = next((k for k in rd.fieldnames or [] if k.strip().lower() in ("title", "name", "summary", "text")), None)
            for row in rd:
                if key and row.get(key, "").strip():
                    reqs[row[key].strip()] = (row.get(title) or "").strip() if title else ""
    else:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                for m in id_rx.finditer(line):
                    reqs.setdefault(m.group(0), line.strip()[:80])
    return reqs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reqs", help="requirements file (.csv with an id column, or .md/.txt)")
    ap.add_argument("--id-regex", default=r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+\b")
    ap.add_argument("--matrix", help="write the full trace matrix to this CSV")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    proj = os.path.abspath(args.root)
    cfg, _ = load_config(proj)
    id_rx = re.compile(args.id_regex)
    tag_rx = re.compile(r"@(req|verifies)\b[:\s]+((?:" + args.id_regex + r")(?:\s*,\s*" + args.id_regex + r")*)")
    impl, tests = {}, {}
    for root, dirs, files in os.walk(proj):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith("build")]
        for f in files:
            if not f.endswith(SRC_EXT):
                continue
            p = os.path.join(root, f)
            rp = rel(p, proj)
            if is_protected(rp, cfg):
                continue
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    for n, line in enumerate(fh, 1):
                        for m in tag_rx.finditer(line):
                            for rid in id_rx.findall(m.group(2)):
                                (impl if m.group(1) == "req" else tests).setdefault(rid, []).append("{}:{}".format(rp, n))
            except OSError:
                continue

    reqs = load_reqs(args.reqs, id_rx) if args.reqs else {}
    all_ids = sorted(set(reqs) | set(impl) | set(tests))
    no_impl = [r for r in reqs if r not in impl]
    no_test = [r for r in reqs if r not in tests]
    unknown = sorted((set(impl) | set(tests)) - set(reqs)) if reqs else []

    if args.matrix:
        with open(args.matrix, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "title", "implemented_in", "verified_by"])
            for r in all_ids:
                w.writerow([r, reqs.get(r, ""), "; ".join(impl.get(r, [])), "; ".join(tests.get(r, []))])

    print("requirements: {} | with code: {} | with tests: {} | tags: {} impl, {} verify".format(
        len(reqs) if reqs else "n/a (no --reqs)", sum(1 for r in all_ids if r in impl),
        sum(1 for r in all_ids if r in tests), sum(len(v) for v in impl.values()), sum(len(v) for v in tests.values())))
    for label, items in (("NOT IMPLEMENTED (no @req tag)", no_impl), ("NOT VERIFIED (no @verifies tag)", no_test),
                         ("UNKNOWN IDs referenced in tags", unknown)):
        if items:
            print("{} [{}]: {}".format(label, len(items), ", ".join(items[:40]) + (" ..." if len(items) > 40 else "")))
    if not reqs:
        orphans = [r for r in impl if r not in tests]
        if orphans:
            print("implemented but not verified [{}]: {}".format(len(orphans), ", ".join(sorted(orphans)[:40])))
    if args.matrix:
        print("matrix written to " + args.matrix)
    return 1 if (no_impl or no_test or unknown) else 0


if __name__ == "__main__":
    sys.exit(main())
