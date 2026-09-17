"""Extract a 10-page representative sample from the real Rajhi statement PDF.

Local-only tool: reads the real statement, classifies each page as
text-layer vs scanned (OCR needed), then extracts a mixed sample of
``--pages`` pages plus a JSON report.

The outputs land in data/local_sample/ which is GITIGNORED — the real
statement never leaves this machine.

Usage:
    python scripts/extract_sample.py \
        --source "$HOME/Downloads/statement.pdf" \
        --pages 10 \
        --out data/local_sample/sample_10p.pdf
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pypdf import PdfReader, PdfWriter

TEXT_CHAR_THRESHOLD = 100  # fewer chars than this on a page => likely scanned


def classify_pdf(source: str) -> tuple[list[int], list[int], list[int]]:
    """Return (text_pages, scanned_pages, char_counts) for every page."""
    reader = PdfReader(source)
    text_pages: list[int] = []
    scanned_pages: list[int] = []
    char_counts: list[int] = []
    for i, page in enumerate(reader.pages):
        try:
            n = len((page.extract_text() or "").strip())
        except Exception:
            n = 0
        char_counts.append(n)
        (text_pages if n >= TEXT_CHAR_THRESHOLD else scanned_pages).append(i)
    return text_pages, scanned_pages, char_counts


def pick_sample(text_pages: list[int], scanned_pages: list[int],
                n_pages: int) -> list[int]:
    """Alternating mix of text and scanned pages (interleaved by page order)."""
    merged = sorted(text_pages + scanned_pages)
    kind = {p: ("text" if p in set(text_pages) else "scanned") for p in merged}
    picked: list[int] = []
    seen_text = seen_scanned = 0
    for p in merged:
        k = kind[p]
        if k == "text" and seen_text < max(1, n_pages // 2):
            picked.append(p)
            seen_text += 1
        elif k == "scanned" and seen_scanned < max(1, n_pages - n_pages // 2):
            picked.append(p)
            seen_scanned += 1
        if len(picked) == n_pages:
            break
    # top up if one class was missing
    for p in merged:
        if len(picked) == n_pages:
            break
        if p not in picked:
            picked.append(p)
    return sorted(picked)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True)
    ap.add_argument("--pages", type=int, default=10)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    src = Path(args.source)
    if not src.exists():
        raise SystemExit(f"source not found: {src}")

    text_pages, scanned_pages, char_counts = classify_pdf(str(src))
    picked = pick_sample(text_pages, scanned_pages, args.pages)

    reader = PdfReader(str(src))
    writer = PdfWriter()
    for i in picked:
        writer.add_page(reader.pages[i])
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as fh:
        writer.write(fh)

    report = {
        "source": str(src),
        "total_pages": len(reader.pages),
        "text_pages": len(text_pages),
        "scanned_pages": len(scanned_pages),
        "sample_pages": [p + 1 for p in picked],
        "sample_kinds": [
            {"page": p + 1, "kind": "text" if p in set(text_pages) else "scanned",
             "chars": char_counts[p]}
            for p in picked
        ],
    }
    out_report = out_path.with_suffix(".report.json")
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    print(f"OK: sample={out_path} pages={len(picked)}")
    print(f"document: {report['total_pages']} pages -> {report['text_pages']} text, "
          f"{report['scanned_pages']} scanned")
    print(f"report: {out_report}")


if __name__ == "__main__":
    main()
