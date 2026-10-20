"""بوّابةُ حالة «لم تُقرأ» في الأدوات (R133-1).

**العِلّة المقيسة (مراجعة ١٣٣):** القاعدةُ صارت تحفظ صفحةً لم تُقرأ (`footer_basis='unread'`)،
والحاجزُ يقولها للنموذج، **لكنّ الأدواتِ نفسَها لا تقرؤها**: `page_summary(2)` و`page_rows(2)`
تقولان «لا توجد بيانات/صفوف للصفحة 2 في هذا الكشف»، و`sum_movements(page=2)` «لا توجد حركات
مطابقة… في الكشف» — **دعوى غيابٍ عن صفحةٍ داخلةٍ في الكشف**. ومجاميعُ الكشف كلِّه (`count` ·
`sum` · `statement_period`) تُخرج ما قُرئ وحدَه كأنّه الكلّ.

**الثابت:** الحالةُ تصل من القاعدة في موضعٍ واحد (`read_footers` ⇒ `basis`)، وأدواتُ الصفحة تقول
«لم تُقرأ» كما `page_footer`، ومجاميعُ الكشف تسمّي ما لم يدخلها — **وعلى قاعدةٍ كاملة لا كلمةَ
زائدة** (الضابطُ الأخير يقيس الحرف).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("langchain_core")          # الأدواتُ تُبنى بـ`@tool`

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_qa import ledger as L           # noqa: E402
from statement_qa.qa_tools import make_qa_tools  # noqa: E402


def _rows(pages=(1, 3), per_page=3) -> list[dict]:
    out = []
    for pg in pages:
        for i in range(1, per_page + 1):
            out.append({
                "page": pg, "row_no": i, "printed_page": pg,
                "date": f"2026-03-{i:02d}", "date_iso": f"2026-03-{i:02d}",
                "date_status": "ok", "date_source": "من خانة الورق", "year": 2026,
                "desc": f"حوالة صادرة {pg}-{i}", "printed_movement": "10.00",
                "printed_balance": "15.00", "movement": "10.00", "balance": "15.00",
                "derived_movement": "10.00", "side": "debit", "opening": False,
                "chain_ok": True, "row_state": "حركة مثبتة بالسلسلة", "source": "السلسلة",
                "shift": "", "footer": "ok", "counted": 1,
            })
    return out


def _pages(pages=(1, 3)) -> dict:
    return {int(pg): {"page_no": pg, "footer": "ok", "rows": 3} for pg in pages}


def _ledger(tmp_path, *, n_pages=3, pages=(1, 3)):
    """قاعدةٌ من ثلاث صفحاتٍ لم تُقرأ ثانيتُها — كما في مسبار المراجعة."""
    conn = L.open_ledger(tmp_path / "ledger.sqlite")
    L.ingest(conn, _rows(pages=pages), _pages(pages=pages), n_pages=n_pages)
    return conn


def _tools(conn):
    trace: list[dict] = []
    return {t.name: t for t in make_qa_tools(conn=conn, trace=trace)}, trace


def test_a_page_that_was_never_read_is_named_by_every_page_tool(tmp_path):
    """الحالاتُ الستّ: الصفحةُ غيرُ المقروءة تُسمّى ولا يُدّعى غيابُها."""
    conn = _ledger(tmp_path)
    try:
        by, trace = _tools(conn)
        summary = by["page_summary"].invoke({"page": 2})
        rows = by["page_rows"].invoke({"page": 2})
        total = by["sum_movements"].invoke({"page": 2})
        searched = by["search_rows"].invoke({"page": 2})
        footer = by["page_footer"].invoke({"page": 2})
    finally:
        conn.close()

    for name, got in (("page_summary", summary), ("page_rows", rows),
                      ("sum_movements", total), ("search_rows", searched)):
        assert "لم تُقرأ" in got, f"{name} لم تقرأ الحالة: {got}"
        assert "لا توجد" not in got, f"{name} عادت دعوى غيابٍ عن صفحةٍ داخلة: {got}"
    assert "لم يُقرأ" in footer, footer
    # كلُّ نداءٍ يُسجَّل ولو لم يجد صفًّا — أثرُ الاستدعاء شاهدٌ لا يتغيّر.
    assert {"page_summary", "page_rows", "sum_movements", "search_rows"} <= {
        t["tool"] for t in trace}


def test_a_whole_statement_total_names_the_page_it_leaves_out(tmp_path):
    """مجاميعُ الكشف كلِّه لا تُخرج ما قُرئ كأنّه الكلّ — تسمّي ص٢."""
    conn = _ledger(tmp_path)
    try:
        by, _ = _tools(conn)
        count = by["count_movements"].invoke({})
        total = by["sum_movements"].invoke({})
        period = by["statement_period"].invoke({})
        extremes = by["balance_extremes"].invoke({})
        closing = by["closing_balance"].invoke({})
    finally:
        conn.close()

    for name, got in (("count_movements", count), ("sum_movements", total),
                      ("statement_period", period), ("balance_extremes", extremes),
                      ("closing_balance", closing)):
        assert "لم تُقرأ" in got and "ص2" in got, f"{name} لم يسمّ الناقص: {got}"


def test_a_complete_ledger_gets_no_extra_word(tmp_path):
    """**قبولُ القاعدة:** على قاعدةٍ كاملةٍ المخرجُ كما هو حرفًا."""
    conn = _ledger(tmp_path, n_pages=2, pages=(1, 2))
    try:
        by, _ = _tools(conn)
        count = by["count_movements"].invoke({})
        total = by["sum_movements"].invoke({})
        page = by["page_summary"].invoke({"page": 1})
    finally:
        conn.close()

    assert count == "العدد = 6 حركة (الفلتر: الاتجاه=الكل)", count
    assert "لم تُقرأ" not in total and "60.00" in total, total
    assert "لم تُقرأ" not in page and "صفحة 1" in page, page
