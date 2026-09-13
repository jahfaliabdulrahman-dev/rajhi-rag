"""Generate a synthetic Arabic bank statement PDF for public demos.

Creates ``data/sample/statement_sample.pdf`` — a text-layer PDF with N
transactions whose balances chain exactly (opening + credits - debits =
closing, row by row). Public-safe: no real names, no real data.

The generator is the ONLY source of demo data for the public Space.

Usage:
    python scripts/make_synthetic_statement.py [n_txn]
"""

from __future__ import annotations

import random
import sys
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
FONT = ROOT / "assets" / "fonts" / "NotoNaskhArabic-Regular.ttf"
LATIN_FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"  # local dev fallback
OUT = ROOT / "data" / "sample" / "statement_sample.pdf"

DESCS = [
    "تحويل وارد - شركة أ",
    "تحويل صادر - مطعم ب",
    "سحب صراف آلي - الرياض",
    "راتب شهري - جهة العمل",
    "فاتورة كهرباء - الشركة السعودية",
    "تحويل وارد - شخص ج",
    "شراء نقاط بيع - سوبرماركت د",
    "رسوم صيانة الحساب",
    "تحويل صادر - شركة هـ",
    "إيداع نقدي - فرع الوديقي",
]


def make_rows(n_txn: int) -> list[dict]:
    """Synthetic rows with an exact balance chain (opening -> closing)."""
    rng = random.Random(42)
    balance = Decimal("10000.00")
    rows: list[dict] = [
        {"date": "01/01/2026", "desc": "رصيد افتتاحي",
         "debit": "", "credit": "", "balance": f"{balance:.2f}"}
    ]
    for i in range(1, n_txn + 1):
        if rng.random() < 0.45:
            credit = Decimal(rng.choice(["1500.00", "3500.00", "9000.00", "12500.50"]))
            debit = Decimal("0.00")
        else:
            credit = Decimal("0.00")
            debit = Decimal(rng.choice(["120.50", "450.00", "1800.75", "2600.00"]))
        balance = balance + credit - debit
        rows.append({
            "date": f"{i + 1:02d}/01/2026",
            "desc": DESCS[i % len(DESCS)],
            "debit": f"{debit:.2f}" if debit else "",
            "credit": f"{credit:.2f}" if credit else "",
            "balance": f"{balance:.2f}",
        })
    return rows


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


def build_pdf(rows: list[dict]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("naskh", "", str(FONT))
    pdf.set_font("naskh", size=11)
    # RTL shaping/bidi — without it fpdf2 draws isolated glyphs in logical
    # order and the fixture reads reversed/garbled to a VLM (owner-caught
    # 2026-09-13: descriptions came back reversed, breaking filters).
    pdf.set_text_shaping(True, direction="rtl")
    latin = _add_latin(pdf)
    if latin:
        pdf.set_fallback_fonts([latin])

    pdf.set_font_size(14)
    pdf.cell(0, 10, "كشف حساب بنكي - تجريبي (بيانات اصطناعية)", new_x="LMARGIN", new_y="NEXT",
             align="C")
    pdf.set_font_size(10)
    pdf.cell(0, 8, "حساب: XXXX-1234     الفترة: يناير 2026     العملة: SAR",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    # Table: date | description | debit | credit | balance (LTR columns, Arabic text)
    pdf.set_font_size(10)
    widths = (28, 70, 28, 28, 32)
    headers = ("التاريخ", "الوصف", "مدين", "دائن", "الرصيد")
    for w, h in zip(widths, headers):
        pdf.cell(w, 8, h, border=1, align="C")
    pdf.ln()
    for r in rows:
        pdf.cell(widths[0], 8, r["date"], border=1, align="C")
        pdf.cell(widths[1], 8, r["desc"], border=1, align="R")
        pdf.cell(widths[2], 8, r["debit"], border=1, align="C")
        pdf.cell(widths[3], 8, r["credit"], border=1, align="C")
        pdf.cell(widths[4], 8, r["balance"], border=1, align="C")
        pdf.ln()
    pdf.output(str(OUT))


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    rows = make_rows(n)
    build_pdf(rows)
    closing = rows[-1]["balance"]
    print(f"OK: {OUT.relative_to(ROOT)} rows={len(rows)} closing_balance={rows[-1]['balance']}")
