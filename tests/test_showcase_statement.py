"""The showcase statement must keep the shape that makes it «closer to the real one».

The owner's decision F2 = (ب) (2026-10-29, `docs/SHOWCASE_PLAN.md` §7) asked for a
synthetic statement closer in shape to the real scans, measured against the template in
`src/statement_qa/row_bands.py`. These controls hold that shape, so a later edit cannot
quietly take it away: the project's own template reader must find, on the rendered
pages, the page kinds, the anchors and the continuations the generator laid out.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src"), str(ROOT / "tools")]
pytest.importorskip("fpdf")
import make_showcase_statement as ms  # noqa: E402

ROWS, SHEETS = ms.build()


def test_the_balance_chain_is_exact():
    for prev, row in zip(ROWS, ROWS[1:]):
        assert row["balance"] == prev["balance"] + (row["credit"] or 0) - (row["debit"] or 0)
        assert (row["debit"] is None) != (row["credit"] is None), "حركةٌ بعمودين أو بلا عمود"


def test_the_first_page_opens_with_the_opening_balance_row():
    first = SHEETS[0][0]["row"]
    assert first["lines"] == ["الرصيد الافتتاحي"]
    assert first["date"] is None and first["debit"] is None and first["credit"] is None


def test_a_description_continues_at_the_top_of_the_next_page():
    continued = [n for n, s in enumerate(SHEETS) if s and s[0].get("continued")]
    assert continued, "لا تكملةَ وصفٍ أعلى صفحة ⇒ ضاع شكلٌ من القالب المقيس"
    for n in continued:
        assert SHEETS[n - 1][-1]["row"] is SHEETS[n][0]["row"], "التكملةُ ليست لآخر صفٍّ في سابقتها"


def test_the_footer_totals_are_cumulative_and_the_summary_closes_them():
    totals = ms.footer_totals(SHEETS)
    moves = ROWS[1:]
    assert totals[-1]["debits"] == sum((r["debit"] or Decimal(0) for r in moves), Decimal(0))
    assert totals[-1]["credits"] == sum((r["credit"] or Decimal(0) for r in moves), Decimal(0))
    assert totals[-1]["balance"] == ROWS[-1]["balance"]
    summary = dict(ms.summary_lines(ROWS))
    assert summary["رصيد الاقفال"] == ms._amount(ROWS[-1]["balance"])
    assert summary["اجمالي السحوبات"] == ms._amount(totals[-1]["debits"])


def test_no_printed_figure_equals_a_real_amount():
    """The PDF is images, so the amount guard cannot read it once rendered — the figures
    are screened here, from the generator, against the deny manifest."""
    import amount_guard as ag

    deny = ag.load_deny()                 # the file, or the session environment; None = neither
    if not deny:
        pytest.skip("لا مانيفستَ على هذا السطح ⇒ الفحصُ يجري حيث توجد الأدلّة")
    hits = ag.find_in_text("\n".join(ms.printed_numbers(ROWS, SHEETS)), deny)
    assert not hits, f"رقمٌ مطبوعٌ يطابق مبلغًا حقيقيًّا ({len(hits)}) ⇒ غيّر البذرة أو المدى"


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    pdf = tmp_path_factory.mktemp("showcase") / "statement_showcase.pdf"
    raw = pdf.with_suffix(".raw.pdf")
    ms.build_pdf(ROWS, SHEETS, raw)
    try:
        ms.rasterize(raw, pdf)
        from pdf2image import convert_from_path

        return pdf, convert_from_path(str(pdf), dpi=200, grayscale=True)
    except Exception as exc:  # poppler missing (CI) — the check is local
        pytest.skip(f"لا مُصيّر PDF هنا: {type(exc).__name__}")


def test_the_template_reader_finds_the_layout(rendered):
    """`row_bands.analyze_page` — the reader measured on the real scans — must see the
    page kinds, the anchors and the continuations exactly as the generator laid them."""
    np = pytest.importorskip("numpy")
    from statement_qa.row_bands import analyze_page

    _pdf, pages = rendered
    found = [analyze_page(np.asarray(img), 200) for img in pages]
    assert [p.kind for p in found] == ["first"] + ["transactions"] * (len(SHEETS) - 1) + ["summary"]
    for n, (sheet, page) in enumerate(zip(SHEETS, found), 1):
        assert len(page.bands) == sum(1 for i in sheet if not i.get("continued")), f"ص{n}: عددُ المراسي"
        assert bool(page.orphan) == any(i.get("continued") for i in sheet), f"ص{n}: التكملة"
        assert page.suspects() == [], f"ص{n}: مرساةٌ بلا تاريخ"
    assert len(found[-1].bands) == len(ms.summary_lines(ROWS)), "صفحةُ الملخّص"


def test_the_statement_has_no_text_layer(rendered):
    from pypdf import PdfReader

    pdf, _pages = rendered
    assert "".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages).strip() == ""
