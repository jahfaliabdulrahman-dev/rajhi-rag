"""One page of a real statement, made public for the story page: its rows as the system read them, and two crops.

Owner, 2026-10-31: «ما ابغى كشف اصطناعي ابدا هنا», then «لا اوافق انك ما تنقل المبالغ … صفحة واحدة بس وعلى كذا
مطبق عليها حجب قوي», then, on page 43 after the account holder's consent, «نعم موافق امضي بالصفحه 43 بالحجب المذكور
اعلاه». The bound is docs/SHOWCASE_PLAN.md section 6 («شرطُ الصدق»): ONE page, its amounts visible, and

  - cropped, not covered: the page header (holder, account, IBAN, address) and footer are outside both crops;
  - solid boxes, never blur: a person's name, an account or transfer reference, a card number;
  - the same items hidden in the text the page reads, by rule and not by position: a transfer row keeps its first
    line only (the names of its parties follow it), and a bracketed reference or a masked card number is hidden
    wherever it is. The text is then audited against the owner's private identity patterns (the same file and
    reader as tools/capture_training.py), and nothing is written if one survives.

The inputs stay on the owner's machine (the run's ledger export and its page images); only the outputs are
tracked. The boxes and the hidden lines are written here by position, so this file names nobody.

    python3 tools/ledger.py build --run <run> --db <scratch>/real.sqlite --source <run>/slice_629p.pdf
    python3 tools/ledger.py export --db <scratch>/real.sqlite --source <run>/slice_629p.pdf --read-on 2026-10-31 \\
        --out <scratch>/real.export.json
    python3 tools/publish_real_page.py --export <scratch>/real.export.json --pages <run>/pages \
        [--patterns ~/.hermes/private/rajhi-private-patterns.txt]

Prints counts only, never a figure or a name from the page.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
PAGE = 43
OUT_JSON = ROOT / "docs" / "measurements" / "real-page-43.json"
OUT_ROWS = ROOT / "site" / "real-rows.png"
OUT_ROW = ROOT / "site" / "real-row.png"

#: The rows region of the 200-DPI page image (left, top, right, bottom): below the header, above the footer.
ROWS_CROP = (140, 780, 1560, 1835)
#: Solid boxes inside ROWS_CROP, each over one item that names or identifies someone.
BOXES = (
    (612, 38, 1082, 68), (612, 68, 660, 102),    # row 1: the transaction reference
    (748, 226, 1032, 262),                       # row 2: a card number
    (668, 573, 956, 603), (812, 604, 956, 642),  # row 5: a person's name, on two lines
    (612, 666, 1108, 706), (790, 706, 1018, 734),  # row 6: an account reference and a name
    (748, 914, 1032, 950),                       # row 8: a card number
)
#: The flagged row's first printed line inside ROWS_CROP: its amount and its description, kept at full size.
ROW_CROP = (560, 818, 1100, 854)
#: The rows crop is scaled down for the page; the flagged row's line is not, so its digits stay legible on a phone.
SCALE = 0.75

HIDDEN = "[محجوب]"
PATTERNS = Path("~/.hermes/private/rajhi-private-patterns.txt")
#: Western, Arabic-Indic and Extended Arabic-Indic digits: the reader writes all three.
DIGIT = "0-9٠-٩۰-۹"
#: A reference in brackets that carries a long run of digits; a card number masked in the middle.
_REFERENCE = re.compile(rf"\([^)]*[{DIGIT}]{{6,}}[^)]*\)")
_CARD = re.compile(rf"[{DIGIT}]{{4,}}\*+[{DIGIT}]{{2,}}")
#: A transfer names its parties under its first line.
_TRANSFER = re.compile(r"تحويل")
#: What the page needs of each row; the footer keeps its verdict only.
ROW_FIELDS = ("seq", "row_no", "page", "date_iso", "desc", "side", "printed_movement", "movement",
              "derived_movement", "balance", "chain_ok")


def redact(desc: str) -> tuple[str, int]:
    """A row's description with names, references and card numbers hidden; and how many items were hidden."""
    lines = (desc or "").split("\n")
    hidden = 0
    if _TRANSFER.search(lines[0]) and len(lines) > 1:
        lines, hidden = [lines[0], HIDDEN], 1
    out = []
    for line in lines:
        line, n = _REFERENCE.subn("(" + HIDDEN + ")", line)
        line, m = _CARD.subn(HIDDEN, line)
        hidden += n + m
        out.append(line)
    return "\n".join(out), hidden


def surviving_patterns(text: str, patterns_file: Path) -> int:
    """How many of the owner's private identity patterns survive in `text` (a count, never the pattern)."""
    from capture_training import load_private_patterns

    patterns = [p for section in load_private_patterns(patterns_file).values() for p in section if p]
    return sum(1 for p in patterns if p in text)


def extract(doc: dict, page: int = PAGE) -> tuple[dict, int]:
    """The public record of one page: its rows (descriptions redacted) and its footer's verdict."""
    rows, hidden = [], 0
    for r in sorted((r for r in doc["rows"] if r["page"] == page), key=lambda r: r["seq"]):
        row = {k: r.get(k) for k in ROW_FIELDS}
        row["desc"], n = redact(r.get("desc") or "")
        hidden += n
        rows.append(row)
    footer = doc["footers"][str(page)]
    return {"source": doc["source"], "source_sha256": doc["source_sha256"], "n_pages": doc["n_pages"],
            "read_on": doc["read_on"], "page": page,
            # An unmarked basis is the cumulative check, which runs only when it reaches a verdict.
            "footer": {"verdict": footer["verdict"],
                       "basis": footer.get("basis") or ("cumulative" if footer["verdict"] in ("ok", "mismatch") else "")},
            "rows": rows}, hidden


def crops(page_image: Path) -> tuple:
    """The two crops, boxes drawn into the pixels, saved without metadata."""
    from PIL import Image, ImageDraw

    rows = Image.open(page_image).convert("L").crop(ROWS_CROP)
    draw = ImageDraw.Draw(rows)
    for box in BOXES:
        draw.rectangle(box, fill=0)
    one = rows.crop(ROW_CROP)
    return rows.resize((round(rows.width * SCALE), round(rows.height * SCALE)), Image.LANCZOS), one


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--export", type=Path, required=True, help="the run's ledger export (stays local)")
    ap.add_argument("--pages", type=Path, required=True, help="the run's page images (stay local)")
    ap.add_argument("--patterns", type=Path, default=PATTERNS, help="the owner's private identity patterns (stay local)")
    args = ap.parse_args(argv)

    record, hidden = extract(json.loads(args.export.read_text(encoding="utf-8")))
    text = json.dumps(record, ensure_ascii=False, indent=1) + "\n"
    patterns = args.patterns.expanduser()
    if not patterns.is_file():
        print(f"refused: no private patterns file at {args.patterns} — nothing is published unaudited")
        return 2
    left = surviving_patterns(text, patterns)
    if left:
        print(f"refused: {left} private identity pattern(s) survive the redaction — nothing written")
        return 1
    OUT_JSON.write_text(text, encoding="utf-8")
    rows, one = crops(args.pages / f"pg-{PAGE:03d}.png")
    for im, out in ((rows, OUT_ROWS), (one, OUT_ROW)):
        im.save(out, format="PNG", optimize=True)   # a new image: no text chunks, no EXIF
    print(f"page {PAGE}: {len(record['rows'])} rows · {hidden} items hidden in the text · "
          f"{len(BOXES)} boxes in the picture · footer {record['footer']['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
