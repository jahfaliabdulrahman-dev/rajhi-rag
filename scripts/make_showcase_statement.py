"""Generate the synthetic statement for the public showcase («جرّب الآن» and the scene).

Writes ``data/sample/statement_showcase.pdf`` — the owner's decision F2 = (ب) of
2026-10-29 (`docs/SHOWCASE_PLAN.md` §7): a NEW statement closer in shape to the real
scans, beside ``statement_sample.pdf``, which stays as it is for the controls that read it.

«Closer» is measured, not remembered: the sheet follows the template in
``src/statement_qa/row_bands.py`` (14 scanned pages), at its coordinates:

* a header on every page ending with the IBAN line, and **no printed column headers**;
* amount and running balance on a transaction's **first line**, the description below it;
* a description cut at a page bottom **continues at the top of the next page**;
* page 1 opens with the «الرصيد الافتتاحي» row (balance, no date, no amount) and a stamp
  near the footer; the last page is a **summary page** — balances with no dates;
* the cumulative totals row and the «العملة» label in the footer; Arabic-Indic digits with
  a comma between thousands (shape «#,###.##», as measured on the real prints); and no text
  layer (the sheets are rasterised, like the scans).

**One declared difference:** the real date cell prints the Hijri date before the
Gregorian one. Only the Gregorian run is printed here: no Hijri converter is among the
project's dependencies, and nothing downstream reads the Hijri run (the frozen prompt
asks for ``greg`` alone, and ``contract_rows.normalize_date``, the one date reader, keeps the
Gregorian run).

Public-safe by construction: fixed seed, **no bank name and no logo**, an invented customer
and a masked account, «بيانات اصطناعية» on every page. No bank is named on purpose (owner,
2026-10-30): naming the supported bank would impersonate it, and an invented name is «another bank»
to the app's bank gate (``bank_check.verdict_from_name``), which stops the read before it
starts — measured on the first paid attempt. With no name the gate lets the read through,
as it does for ``statement_sample.pdf``. Whether an invented
amount happens to equal a real one is not decided here — the generator has no access
to the evidence — but by ``tests/test_showcase_statement.py`` against the amount guard.

Usage:
    python scripts/make_showcase_statement.py [--out PATH] [--pages N] [--seed S]
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_synthetic_statement import _add_latin, ar, rasterize  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "assets" / "fonts" / "NotoNaskhArabic-Regular.ttf"
OUT = ROOT / "data" / "sample" / "statement_showcase.pdf"
SEED = 2026

MM = 25.4 / 100            # one template pixel (100 dpi) in millimetres
SYNTHETIC = "بيانات اصطناعية للعرض — ليست كشفًا حقيقيًّا لأيّ عميل"

# --- the template's columns (row_bands.py, pixels at 100 dpi) as cells (x, w) in mm ---
BALANCE = (24.5, 21.0)     # BALANCE_X 95–180: the running balance, the row's anchor
CREDIT = (57.5, 18.5)      # CREDIT_X 225–300
DEBIT = (77.5, 16.5)       # the debit sits against the description (row_bands: not split by position)
DESC = (95.0, 62.5)        # DESC_X 330–712, kept left of the date band on every line
DATE = (160.0, 20.5)       # DATE_X 625–712
IBAN_Y = 84.0              # HEADER_Y 300–378: the IBAN line ends the header (measured ≈338–344)
TABLE_TOP = 98.0           # below the header window (378 px = 96 mm): a row inside it reads as header
# The footer stands apart from the table, as on the real form — measured 2026-10-30 on four real
# pages (positions only): the last row ends at ≈912–916 px and the totals line with «العملة» sits
# at ≈994–1008, about 20 mm lower, with nothing printed below it. The first layout put the totals
# straight after the last row, and the paid read took them for a transaction on one page of four
# (on the real reads: 5 totals-line rows in 5809, all on one page); and a stamp and a line BELOW
# the footer hid it from page_gate's referee, which looks for the footer as the last printed line.
TABLE_END = 232.0          # ≈912–916 px: where the last row ends on a full real page
FOOTER_Y = 252.5           # ≈994–1004 px: the totals line and «العملة»
LINE = 4.0                 # the print's lines nearly touch
LINES_PER_PAGE = int((TABLE_END - TABLE_TOP) // LINE)

# Amounts carry cents on purpose, even a cash withdrawal: a round figure is the likeliest to
# equal a real amount, and roundness is not evidence that a figure is synthetic (the amount
# guard's rule). The weights keep a one-line fee from repeating row after row.
DEBITS = [
    (["شراء عبر نقاط البيع", "مدى - متجر تجريبي", "مرجع: POS-A7"], (18, 640)),
    (["تحويل صادر إلى حساب آخر", "المستفيد: مستفيد تجريبي", "الغرض: مصاريف عائلية"], (150, 2400)),
    (["سداد فاتورة", "شركة خدمات تجريبية"], (90, 780)),
    (["سحب نقدي من صراف آلي", "صراف الفرع التجريبي"], (100, 1500)),
    (["رسوم خدمة"], (5, 60)),
    (["شراء عبر الإنترنت", "متجر إلكتروني تجريبي", "مرجع: WEB-K2"], (35, 920)),
]
DEBIT_WEIGHTS = (5, 3, 2, 2, 1, 3)
CREDITS = [
    (["تحويل وارد من حساب آخر", "المحوِّل: عميل تجريبي آخر"], (200, 3200)),
    (["إيداع نقدي", "الفرع التجريبي"], (300, 2600)),
    (["استرداد مبلغ شراء", "متجر تجريبي"], (20, 410)),
]
SALARY = ["راتب", "جهة العمل: منشأة تجريبية"]


def _money(rng: random.Random, lo: int, hi: int) -> Decimal:
    return Decimal(rng.randint(lo * 100, hi * 100)) / 100


def make_rows(n: int, seed: int = SEED) -> list[dict]:
    """``n`` transactions after the opening row, with an exact balance chain.

    Direction comes from the description pool, never a coin flip on the amount, and a
    salary arrives once a month from the 27th — the shape of a current account.
    """
    rng = random.Random(seed)
    balance = _money(rng, 14000, 22000)
    rows = [{"date": None, "lines": ["الرصيد الافتتاحي"], "debit": None, "credit": None,
             "balance": balance}]
    day, paid = date(2026, 1, 1), set()
    while len(rows) <= n:
        if day.day >= 27 and (day.year, day.month) not in paid:
            paid.add((day.year, day.month))
            lines, debit, credit = SALARY, None, _money(rng, 11800, 12400)
        elif rng.random() < 0.3:
            lines, (lo, hi) = rng.choice(CREDITS)
            debit, credit = None, _money(rng, lo, hi)
        else:
            lines, (lo, hi) = rng.choices(DEBITS, weights=DEBIT_WEIGHTS)[0]
            debit, credit = _money(rng, lo, hi), None
            if debit > balance:                       # a current account does not go negative
                continue
        balance = balance + (credit or 0) - (debit or 0)
        rows.append({"date": day, "lines": list(lines), "debit": debit, "credit": credit,
                     "balance": balance})
        day += timedelta(days=rng.choice((0, 1, 1, 2)))
    return rows


def paginate(rows: list[dict], pages: int, per_page: int = LINES_PER_PAGE) -> list[list[dict]]:
    """Lay rows on ``pages`` transaction sheets the way the print does.

    A row starts on the sheet where its first line (the anchor) fits; a description that
    runs past the bottom continues at the top of the next sheet, ABOVE its first anchor
    (``continued`` marks those lines). Rows beyond the last sheet are dropped whole, and
    so is a last row that would spill onto a sheet that is not printed.
    """
    sheets: list[list[dict]] = [[]]
    used = 0
    for row in rows:
        if used + 1 > per_page:
            if len(sheets) == pages:
                break
            sheets.append([])
            used = 0
        room = per_page - used
        if len(row["lines"]) <= room:
            sheets[-1].append({"row": row, "lines": row["lines"]})
            used += len(row["lines"])
            continue
        if len(sheets) == pages:                      # its tail would land on no sheet
            break
        sheets[-1].append({"row": row, "lines": row["lines"][:room]})
        sheets.append([{"row": row, "lines": row["lines"][room:], "continued": True}])
        used = len(row["lines"]) - room
    return sheets


def _amount(v: Decimal | None) -> str:
    """Printed like the real statement: Arabic-Indic digits, a comma between thousands and
    a full stop before the halalas (shape «#,###.##»). Measured on the owner's word (2026-10-30):
    3834 of 3859 values of a thousand or more in the 629-page reads carry the comma, every
    year 2013–2024, and the glyphs were confirmed on two real page images."""
    return ar(f"{v:,.2f}") if v is not None else ""


def footer_totals(sheets: list[list[dict]]) -> list[dict]:
    """Cumulative debits/credits through each sheet, and the sheet's last balance."""
    out, debits, credits, balance = [], Decimal(0), Decimal(0), None
    for sheet in sheets:
        for item in sheet:
            if item.get("continued"):
                continue
            row = item["row"]
            debits += row["debit"] or 0
            credits += row["credit"] or 0
            balance = row["balance"]
        out.append({"debits": debits, "credits": credits, "balance": balance})
    return out


def summary_lines(rows: list[dict]) -> list[tuple[str, str]]:
    """The closing page: labels and figures with no dates (what the prompt sends to
    ``summary_lines``)."""
    moves = rows[1:]
    credits = [r["credit"] for r in moves if r["credit"] is not None]
    debits = [r["debit"] for r in moves if r["debit"] is not None]
    closing = rows[-1]["balance"]
    return [
        ("الرصيد الافتتاحي", _amount(rows[0]["balance"])),
        ("اجمالي الايداعات", _amount(sum(credits, Decimal(0)))),
        ("عدد الايداعات", ar(str(len(credits)))),
        ("اجمالي السحوبات", _amount(sum(debits, Decimal(0)))),
        ("عدد السحوبات", ar(str(len(debits)))),
        ("أجمالي قيود محجوزة", _amount(Decimal(0))),
        ("رصيد الاقفال", _amount(closing)),
        ("الرصيد المتاح اليوم", _amount(closing)),
    ]


def printed_numbers(rows: list[dict], sheets: list[list[dict]]) -> list[str]:
    """Every figure the sheets print — what the amount-guard control screens."""
    vals = [_amount(r[k]) for r in rows for k in ("debit", "credit", "balance") if r[k] is not None]
    for t in footer_totals(sheets):
        vals += [_amount(t[k]) for k in ("debits", "credits", "balance")]
    vals += [v for _label, v in summary_lines(rows)]
    return [v for v in vals if v]


def _cell(pdf: FPDF, col: tuple[float, float], y: float, text: str, align: str = "C") -> None:
    pdf.set_xy(col[0], y)
    pdf.cell(col[1], LINE, text, align=align)


def _header(pdf: FPDF, page_no: int) -> None:
    pdf.set_font_size(7)
    pdf.set_xy(0, 5)
    pdf.cell(210, 4, SYNTHETIC, align="C")
    # the page number on the same line as the «start and end of page» box (the frozen prompt's rule 5)
    pdf.set_font_size(10)
    pdf.set_xy(12, 12)
    pdf.cell(8, 7, ar(str(page_no)), align="C")
    pdf.set_font_size(8)
    pdf.set_xy(22, 12)
    pdf.cell(46, 7, "بداية ونهاية معاملات الصفحة", border=1, align="C")
    pdf.set_font_size(15)
    pdf.set_xy(0, 24)
    pdf.cell(210, 8, "كشف حساب", align="C")
    pdf.set_font_size(9)
    right = ["اسم العميل: عميل تجريبي", "رقم الحساب: XXXX-XXXX-5821", "نوع الحساب: جاري",
             f"الفترة: {ar('20260101')} - {ar('20260331')}", "العملة: ريال سعودي"]
    for i, text in enumerate(right):
        pdf.set_xy(110, 40 + i * 5.5)
        pdf.cell(88, 5, text, align="R")
    pdf.set_xy(12, 40)
    pdf.cell(80, 5, "الفرع: الفرع التجريبي", align="L")
    pdf.set_xy(70, IBAN_Y)
    pdf.cell(70, 5, "رقم الآيبان: SA•• XXXX XXXX XXXX XXXX 5821", align="C")


def _footer(pdf: FPDF, totals: dict) -> None:
    pdf.set_font_size(9)
    _cell(pdf, BALANCE, FOOTER_Y, _amount(totals["balance"]))
    _cell(pdf, CREDIT, FOOTER_Y, _amount(totals["credits"]))
    _cell(pdf, DEBIT, FOOTER_Y, _amount(totals["debits"]))
    # two lines in the description band, as measured on the real footer
    _cell(pdf, (100.0, 50.0), FOOTER_Y, "الإجمالي التراكمي", align="R")
    _cell(pdf, (100.0, 50.0), FOOTER_Y + 4.0, "حتى نهاية الصفحة", align="R")
    _cell(pdf, (150.0, 33.0), FOOTER_Y, "العملة: ريال سعودي", align="R")
    # nothing below: the footer is the last printed line (the «بيانات اصطناعية» line is at the top)


def _stamp(pdf: FPDF) -> None:
    """The stamp near the footer of page 1 (measured on the real first page) — in the gap
    above the footer and right of every column band (x > 181 mm), so it adds no anchor, joins
    no description, and leaves the footer the last printed line."""
    cx, cy, r = 196.0, 241.0, 9.0
    with pdf.rotation(-12, x=cx, y=cy):
        pdf.set_line_width(0.6)
        # x, y is the CENTRE in the pinned fpdf2 2.8.8 — measured from the drawn ink; its
        # docstring still says «upper-left of bounding box», and the ink is what counts.
        pdf.circle(x=cx, y=cy, radius=r)
        pdf.circle(x=cx, y=cy, radius=r - 1.5)
        pdf.set_font_size(8)
        pdf.set_xy(cx - r, cy - 4.5)
        pdf.cell(2 * r, 4, "مُدقَّق", align="C")
        pdf.set_font_size(6)
        pdf.set_xy(cx - r, cy + 0.5)
        pdf.cell(2 * r, 4, "تجريبي", align="C")


def build_pdf(rows: list[dict], sheets: list[list[dict]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_font("naskh", "", str(FONT))
    pdf.set_font("naskh", size=9)
    pdf.set_text_shaping(True, direction="rtl")
    latin = _add_latin(pdf)
    if latin:
        pdf.set_fallback_fonts([latin])

    totals = footer_totals(sheets)
    for page_no, sheet in enumerate(sheets, start=1):
        pdf.add_page()
        _header(pdf, page_no)
        pdf.set_font_size(9)
        y = TABLE_TOP
        for item in sheet:
            row = item["row"]
            if not item.get("continued"):
                _cell(pdf, BALANCE, y, _amount(row["balance"]))
                _cell(pdf, CREDIT, y, _amount(row["credit"]))
                _cell(pdf, DEBIT, y, _amount(row["debit"]))
                if row["date"]:
                    _cell(pdf, DATE, y, ar(row["date"].strftime("%Y%m%d")), align="R")
            for line in item["lines"]:
                _cell(pdf, DESC, y, line, align="R")
                y += LINE
        _footer(pdf, totals[page_no - 1])
        if page_no == 1:
            _stamp(pdf)

    pdf.add_page()                                      # the closing summary page
    _header(pdf, len(sheets) + 1)
    pdf.set_font_size(10)
    _cell(pdf, DESC, TABLE_TOP, "ملخّص الكشف", align="R")
    pdf.set_font_size(9)
    for i, (label, value) in enumerate(summary_lines(rows)):
        y = TABLE_TOP + 8 + i * 6
        _cell(pdf, DESC, y, label, align="R")
        _cell(pdf, BALANCE, y, value)
    _footer(pdf, totals[-1])
    pdf.output(str(out))


def build(pages: int = 4, seed: int = SEED) -> tuple[list[dict], list[list[dict]]]:
    """Rows and their sheets: enough rows to fill ``pages`` transaction sheets."""
    rows = make_rows(pages * LINES_PER_PAGE, seed)
    sheets = paginate(rows, pages)
    placed = {id(i["row"]) for s in sheets for i in s}
    return [r for r in rows if id(r) in placed], sheets


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--pages", type=int, default=4, help="transaction sheets (the summary page is added)")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    rows, sheets = build(args.pages, args.seed)
    raw = args.out.with_suffix(".raw.pdf")
    build_pdf(rows, sheets, raw)
    rasterize(raw, args.out)
    raw.unlink(missing_ok=True)
    continued = sum(1 for s in sheets for i in s if i.get("continued"))
    print(f"OK: {args.out} pages={len(sheets) + 1} transactions={len(rows) - 1} "
          f"continuations={continued} closing_balance={rows[-1]['balance']:.2f} (no text layer)")


if __name__ == "__main__":
    main()
