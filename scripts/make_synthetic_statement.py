"""Generate the synthetic Arabic statement used for public demos.

Writes ``data/sample/statement_sample.pdf`` — and WHAT IT CONTAINS is a
requirement, not a detail. It is the only statement a stranger ever runs, and
until now it carried no printed totals row, no Arabic-Indic digits, no page
number and a full text layer — so every verification layer the project is built
on answered «nothing to check» on the demo, and the one feature worth showing
was invisible (audit P3-10). It now exercises them:

* **Arabic-Indic digits** for every amount, date and page number — the style the
  legacy parser exists for;
* a **cumulative totals row** at the foot of each page (مدين / دائن / الرصيد),
  cumulative-to-date exactly like the real prints, which is what the footer
  oracle compares against the balance chain;
* a **printed page number** in the top-left corner of each sheet;
* **two or more pages**, so cross-page continuity and the page-order check have
  something to look at;
* **no text layer** — the sheets are rasterised at 200 dpi and rebuilt as
  images, so the fixture behaves like the scanned statements this project is
  for.

Public-safe by construction: fixed seed, invented vocabulary, invented account
mask, no real name, no real amount, no real bank.

Usage:
    python scripts/make_synthetic_statement.py [n_txn] [--out PATH]
"""
from __future__ import annotations

import random
import sys
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "assets" / "fonts" / "NotoNaskhArabic-Regular.ttf"
LATIN_FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"  # local dev fallback
OUT = ROOT / "data" / "sample" / "statement_sample.pdf"
ROWS_PER_PAGE = 20
DPI = 200

# Direction-consistent vocabulary: credit-decoded descriptions only ever run
# as credits and vice versa — a «سحب صراف آلي» that RAISES the balance is
# nonsense the moment النوع + مدين/دائن columns sit side by side.
DEBIT_DESCS = [
    "تحويل صادر - مطعم ب",
    "سحب صراف آلي - الرياض",
    "فاتورة كهرباء - الشركة السعودية",
    "شراء نقاط بيع - سوبرماركت د",
    "رسوم صيانة الحساب",
    "تحويل صادر - شركة هـ",
]
CREDIT_DESCS = [
    "تحويل وارد - شركة أ",
    "راتب شهري - جهة العمل",
    "تحويل وارد - شخص ج",
    "إيداع نقدي - فرع الوديقي",
]
DEBIT_AMTS = ["120.50", "450.00", "1800.75", "2600.00"]
CREDIT_AMTS = ["1500.00", "3500.00", "9000.00", "12500.50"]

_AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def ar(text: str) -> str:
    """Western digits -> Arabic-Indic, the way the prints write them."""
    return str(text).translate(_AR)


def make_rows(n_txn: int) -> list[dict]:
    """Synthetic rows with an exact balance chain (opening -> closing).

    Direction comes FROM the description (debit vs credit pools) — never a coin
    flip — so the public demo stays self-consistent.
    """
    rng = random.Random(42)
    balance = Decimal("10000.00")
    rows: list[dict] = [
        {"date": "01/01/2026", "desc": "رصيد افتتاحي",
         "debit": "", "credit": "", "balance": f"{balance:.2f}"}
    ]
    for i in range(1, n_txn + 1):
        if rng.random() < 0.45:
            desc = rng.choice(CREDIT_DESCS)
            credit = Decimal(rng.choice(CREDIT_AMTS))
            debit = Decimal("0.00")
        else:
            desc = rng.choice(DEBIT_DESCS)
            credit = Decimal("0.00")
            debit = Decimal(rng.choice(DEBIT_AMTS))
        balance = balance + credit - debit
        rows.append({
            "date": f"{i + 1:02d}/01/2026",
            "desc": desc,
            "debit": f"{debit:.2f}" if debit else "",
            "credit": f"{credit:.2f}" if credit else "",
            "balance": f"{balance:.2f}",
        })
    return rows


def page_totals(rows: list[dict], upto: int) -> dict:
    """Cumulative-to-date totals at the end of a page — the real print semantics.

    debits/credits accumulate from the statement opening; balance is the page's
    last one. This is what the footer oracle expects, so the fixture produces a
    comparable footer instead of an «absent» one.
    """
    debits = sum((Decimal(r["debit"] or "0") for r in rows[1:upto]), Decimal("0"))
    credits = sum((Decimal(r["credit"] or "0") for r in rows[1:upto]), Decimal("0"))
    balance = rows[upto - 1]["balance"] if upto else "0.00"
    return {"debits": f"{debits:.2f}", "credits": f"{credits:.2f}",
            "balance": balance}


def _add_latin(pdf: FPDF) -> str | None:
    """Register a Latin-capable fallback font; returns its family name."""
    if Path(LATIN_FONT).exists():
        path: str | None = LATIN_FONT
    else:
        bundled = ROOT / "assets" / "fonts" / "DejaVuSans.ttf"
        path = str(bundled) if bundled.exists() else None
    if not path:
        return None
    pdf.add_font("latin", "", path)
    return "latin"


def build_pdf(rows: list[dict], out: Path, rows_per_page: int = ROWS_PER_PAGE) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_font("naskh", "", str(FONT))
    pdf.set_font("naskh", size=11)
    # RTL shaping/bidi — without it fpdf2 draws isolated glyphs in logical order
    # and the fixture reads reversed/garbled to any reader.
    pdf.set_text_shaping(True, direction="rtl")
    latin = _add_latin(pdf)
    if latin:
        pdf.set_fallback_fonts([latin])

    widths = (28, 70, 28, 28, 32)
    headers = ("التاريخ", "الوصف", "مدين", "دائن", "الرصيد")
    body = rows[1:]
    pages = [body[i:i + rows_per_page]
             for i in range(0, len(body), rows_per_page)] or [[]]

    consumed = 1
    for page_no, chunk in enumerate(pages, start=1):
        pdf.add_page()
        # printed page number, top-left, Arabic-Indic like the real prints
        pdf.set_font_size(10)
        pdf.set_xy(12, 10)
        pdf.cell(20, 8, ar(str(page_no)), align="C")
        pdf.set_xy(0, 10)
        pdf.set_font_size(14)
        pdf.cell(0, 10, "كشف حساب بنكي - تجريبي (بيانات اصطناعية)",
                 new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_font_size(10)
        pdf.cell(0, 8, ar("حساب: XXXX-1234   الفترة: يناير 2026   العملة: SAR"),
                 new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(4)

        pdf.set_font_size(10)
        for w, h in zip(widths, headers):
            pdf.cell(w, 8, h, border=1, align="C")
        pdf.ln()
        for r in chunk:
            pdf.cell(widths[0], 8, ar(r["date"]), border=1, align="C")
            pdf.cell(widths[1], 8, r["desc"], border=1, align="R")
            pdf.cell(widths[2], 8, ar(r["debit"]), border=1, align="C")
            pdf.cell(widths[3], 8, ar(r["credit"]), border=1, align="C")
            pdf.cell(widths[4], 8, ar(r["balance"]), border=1, align="C")
            pdf.ln()
            consumed += 1

        # Cumulative totals row at the FOOT of the sheet, not right after the
        # last transaction: the oracle reads the bottom band (footer_oracle
        # CROP_TOP = 0.75), which is where the real prints put it. A totals row
        # floating mid-page looks equivalent and is unreadable to the checker.
        t = page_totals(rows, consumed)
        pdf.set_y(-30)
        pdf.cell(sum(widths[:2]) - 8, 8, "الإجمالي التراكمي حتى نهاية الصفحة",
                 border=1, align="R")
        pdf.cell(widths[2], 8, ar(t["debits"]), border=1, align="C")
        pdf.cell(widths[3], 8, ar(t["credits"]), border=1, align="C")
        pdf.cell(widths[4], 8, ar(t["balance"]), border=1, align="C")
        pdf.ln()

    pdf.output(str(out))


def rasterize(src: Path, out: Path, dpi: int = DPI) -> None:
    """Rebuild the PDF as page images so it has NO text layer.

    The real inputs are scans; a fixture with a text layer lets a reader — and a
    reviewer — believe the pipeline is doing something it is not. Rasterisation
    uses pdf2image + fpdf2, both already dependencies of the application: no new
    package is added for the sake of the demo.

    Page geometry is converted back to points at 72 dpi (pixels × 72 ÷ dpi), so
    rendering the fixture again at the pipeline's DPI reproduces the same
    physical sheet instead of a poster.
    """
    from pdf2image import convert_from_path

    images = convert_from_path(str(src), dpi=dpi)
    if not images:
        raise RuntimeError("لا صفحات لتجسيدها")
    w_pt, h_pt = images[0].width * 72 / dpi, images[0].height * 72 / dpi
    pdf = FPDF(unit="pt", format=(w_pt, h_pt))
    for img in images:
        pdf.add_page(format=(img.width * 72 / dpi, img.height * 72 / dpi))
        pdf.image(img, x=0, y=0, w=img.width * 72 / dpi, h=img.height * 72 / dpi)
    pdf.output(str(out))


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 26
    out = OUT
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    raw = out.with_suffix(".raw.pdf")
    rows = make_rows(n)
    build_pdf(rows, raw)
    rasterize(raw, out)
    raw.unlink(missing_ok=True)
    pages = -(-len(rows[1:]) // ROWS_PER_PAGE)
    print(f"OK: {out.relative_to(ROOT)} rows={len(rows)} pages={pages} "
          f"closing_balance={rows[-1]['balance']} (no text layer, {DPI} dpi)")


if __name__ == "__main__":
    main()
