#!/usr/bin/env python3
"""Find the pages of a datasheet / reference manual / schematic PDF that matter, before reading them.

Backends (first available): pdftotext (poppler), pypdf, PyMuPDF. All free/open source.

  python pdf_search.py RM0090.pdf "USART_BRR" "oversampling"      # pages + snippets per term
  python pdf_search.py schematic.pdf --regex "PA\\d+|BOOT0|NRST"     # regex search
  python pdf_search.py schematic.pdf --page 3                       # plain text of page 3 (nets, refdes)
  python pdf_search.py big.pdf --toc                                # first lines of each page (outline-ish)
Then read only those pages with the Read tool (pages="12-14"). Image-only (scanned) PDFs have
no text: read the pages visually instead.
"""

import argparse
import re
import shutil
import subprocess
import sys


def pages_pdftotext(path):
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    r = subprocess.run([exe, "-layout", "-enc", "UTF-8", path, "-"], capture_output=True, timeout=300)
    if r.returncode != 0:
        return None
    text = r.stdout.decode("utf-8", errors="replace")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def pages_pypdf(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    return [(p.extract_text() or "") for p in PdfReader(path).pages]


def pages_fitz(path):
    try:
        import fitz
    except ImportError:
        return None
    with fitz.open(path) as doc:
        return [p.get_text() for p in doc]


def load_pages(path):
    for fn in (pages_pdftotext, pages_pypdf, pages_fitz):
        try:
            pages = fn(path)
        except Exception:
            pages = None
        if pages is not None:
            return pages, fn.__name__[6:]
    return None, None


def snippet(text, start, end, ctx):
    s = text[max(0, start - ctx):min(len(text), end + ctx)]
    return re.sub(r"\s+", " ", s).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("terms", nargs="*")
    ap.add_argument("--regex", action="append", default=[], help="regex term (repeatable)")
    ap.add_argument("--page", type=int, help="print text of one page (1-based)")
    ap.add_argument("--toc", action="store_true", help="first non-empty line of every page")
    ap.add_argument("--context", type=int, default=60)
    ap.add_argument("--max", type=int, default=8, help="max snippets per term")
    ap.add_argument("--case", action="store_true", help="case-sensitive")
    args = ap.parse_args()

    pages, backend = load_pages(args.pdf)
    if pages is None:
        print("No PDF text backend. Install one (free/open source): poppler (pdftotext) or `pip install pypdf`. "
              "Or read pages directly with the Read tool.")
        return 2
    if not any(p.strip() for p in pages):
        print("{} pages, no extractable text (scanned/image PDF) - read pages visually with the Read tool.".format(len(pages)))
        return 0

    if args.page:
        if not 1 <= args.page <= len(pages):
            print("page out of range 1..{}".format(len(pages)))
            return 1
        print(re.sub(r"[ \t]+\n", "\n", pages[args.page - 1]).strip())
        return 0
    if args.toc:
        for i, p in enumerate(pages, 1):
            line = next((l.strip() for l in p.splitlines() if l.strip()), "")
            print("p{:<4} {}".format(i, line[:100]))
        return 0

    flags = 0 if args.case else re.I
    queries = [(t, re.compile(re.escape(t), flags)) for t in args.terms] + [(r, re.compile(r, flags)) for r in args.regex]
    if not queries:
        print("{}: {} pages (backend: {}). Give search terms, --page N or --toc.".format(args.pdf, len(pages), backend))
        return 0
    print("{}: {} pages (backend: {})".format(args.pdf, len(pages), backend))
    allpages = set()
    for label, rx in queries:
        hits = [(i, m) for i, p in enumerate(pages, 1) for m in rx.finditer(p)]
        pnums = sorted({i for i, _ in hits})
        allpages.update(pnums)
        print("\n[{}] {} hit(s) on pages: {}".format(label, len(hits), ", ".join(map(str, pnums[:40])) + (" ..." if len(pnums) > 40 else "")))
        shown = set()
        for i, m in hits:
            if i in shown or len(shown) >= args.max:
                continue
            shown.add(i)
            print("  p{}: ...{}...".format(i, snippet(pages[i - 1], m.start(), m.end(), args.context)))
    if allpages:
        print("\nRead with: pages=\"{}\"".format(",".join(map(str, sorted(allpages)[:20]))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
