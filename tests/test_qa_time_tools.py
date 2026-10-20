"""بوّابةُ البُعد الزمنيّ (R130-1): التاريخُ يُقرأ ويُرشَّح ويُجمَّع، والامتناعُ يسمّي **حدَّ الأداة**.

**العِلّة المقيسة (مراجعة ١٣٠):** سؤالُ «الرصيد في تاريخٍ» كان يُجاب «لا توجد حركاتٌ بهذا التاريخ»
**بلا أداةٍ سألت التاريخَ** — دعوى عن الكشف لا سند لها. والعلاجُ **قدرةٌ** (أدواتٌ تقرأ المدى
وتُجمّع وتُخرج المعدّل) **لا قائمةُ عبارات** تمنع جملة؛ فالضوابطُ هنا تقيس القدرةَ والصدقَ معًا:

- يومٌ موجودٌ في الكشف يُجاب من أداة (برصيده وسنده).
- يومٌ خارج المدّة يُجاب «خارج مدّة الكشف» **مع المدّة وسندها** (لا «لا توجد حركات»).
- معدّلُ السحب في الأسبوع وعددُ أيّام السحب يُحسبان **في الأداة** (لا في رأس النموذج).
- تاريخٌ غيرُ مفهوم ⇒ خطأُ أداةٍ يسمّي الصيغة (حدُّ الأداة)، ولا يُقلَب إلى دعوى غياب.
- والأدواتُ تقرأ من **القاعدة** لا من قائمةٍ في الذاكرة.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

pytest.importorskip("langchain_core")          # الأدواتُ تُبنى بـ`@tool`؛ تُتخطّى حيث لا مكتبة

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_qa import ledger as L           # noqa: E402
from statement_qa.qa_tools import make_qa_tools  # noqa: E402


def _rows() -> list[dict]:
    """كشفٌ صغير: حركتان في ٢ مارس (سحبٌ + إيداع) وسحبٌ في ١٦ مارس، وصفٌّ بلا تاريخ."""
    base = {"printed_page": 1, "kind": "txn"}
    return [
        {**base, "page": 1, "row_no": 1, "desc": "رصيد افتتاحي", "date": "2026-03-01",
         "balance": "7431.29", "movement": None, "side": "", "opening": True, "type": ""},
        {**base, "page": 1, "row_no": 2, "desc": "سحب صراف آلي", "date": "2026-03-02",
         "balance": "7166.92", "movement": "264.37", "side": "debit",
         "type": "سحب صراف آلي"},
        {**base, "page": 1, "row_no": 3, "desc": "إيداع نقدي", "date": "2026-03-02",
         "balance": "7555.33", "movement": "388.41", "side": "credit",
         "type": "إيداع نقدي (صراف آلي)"},
        {**base, "page": 2, "printed_page": 2, "row_no": 1, "desc": "سحب صراف آلي",
         "date": "2026-03-16", "balance": "7412.25", "movement": "143.08", "side": "debit",
         "type": "سحب صراف آلي"},
        {**base, "page": 2, "printed_page": 2, "row_no": 2, "desc": "صفٌّ بلا تاريخ",
         "date": "", "balance": "7412.25", "movement": None, "side": "", "type": ""},
    ]


def _tools(rows=None):
    trace: list[dict] = []
    tools = make_qa_tools(rows if rows is not None else _rows(), trace=trace)
    return {t.name: t for t in tools}, trace


def test_a_day_inside_the_statement_is_answered_with_its_balance_and_reference():
    by, _trace = _tools()
    got = by["balance_on"].invoke({"date": "2026-03-02"})
    # آخرُ رصيدٍ في اليوم نفسه (بعد الإيداع) = 7555.33 — وسندُه الصفُّ الثالث
    assert "الرصيد" in got and "7,555.33" in got, got
    assert "(صفحة 1، صف 3)" in got, "الجوابُ بلا سندِ الصفّ — لا يُقبل"


def test_a_day_outside_the_period_names_the_period_and_its_evidence():
    by, _trace = _tools()
    got = by["balance_on"].invoke({"date": "2026-04-01"})
    assert "خارج مدّة الكشف" in got
    assert "2026-03-01" in got and "2026-03-16" in got, "المدّةُ لم تُذكر"
    assert "(صفحة" in got, "المدّةُ بلا سندِ صفٍّ"
    assert "لا توجد حركات" not in got, "الامتناعُ عاد دعوى عن الكشف لا حدَّ أداة"


def test_the_weekly_rate_and_the_number_of_days_are_computed_by_the_tool():
    from decimal import Decimal

    by, _trace = _tools()
    got = by["movement_days"].invoke({"tx_type": "سحب صراف آلي"})
    # أيّامُ السحب = ٢ (٢ مارس و١٦ مارس) · الحركات = ٢ · المجموع = 407.45
    assert "أيّامُ الحركة = 2" in got, got
    assert "عددُ الحركات = 2" in got
    assert "407.45" in got
    # المدّةُ ١٦ يومًا ⇒ ١٦/٧ = 2.29 أسبوعًا (مقرَّبةٌ بخانتين) — والمعدّلُ يُحسب في الأداة
    weeks = (Decimal(16) / Decimal(7)).quantize(Decimal("0.01"))
    assert f"{weeks}" in got
    assert f"{(Decimal('407.45') / weeks).quantize(Decimal('0.01'))}" in got


def test_a_date_range_narrows_the_sum_and_the_count():
    by, _trace = _tools()
    got = by["sum_movements"].invoke({"tx_type": "سحب صراف آلي",
                                      "date_from": "2026-03-01", "date_to": "2026-03-10"})
    assert "264.37" in got and "عدد الحركات = 1" in got, got
    count = by["count_movements"].invoke({"date_from": "2026-03-01", "date_to": "2026-03-31"})
    assert "العدد = 3" in count, count


def test_a_range_outside_the_statement_is_a_tool_limit_not_an_absence_claim():
    by, _trace = _tools()
    got = by["sum_movements"].invoke({"date_from": "2027-01-01", "date_to": "2027-01-31"})
    assert "خارج مدّة الكشف" in got and "2026-03-01" in got and "(صفحة" in got, got


def test_an_unknown_date_is_refused_by_the_tool_not_turned_into_an_absence():
    by, _trace = _tools()
    with pytest.raises(Exception) as ei:          # ToolException/ValueError تُعمّقها المكتبة
        by["balance_on"].invoke({"date": "كذا"})
    text = str(ei.value)
    assert "تاريخٌ غيرُ مفهوم" in text or "حدُّ الأداة" in text, text
    assert "لا توجد حركات" not in text


def test_the_tools_read_from_the_database_itself(tmp_path):
    """**شرطُ القبول:** الأداةُ تجيب من القاعدة ولو فرغت الذاكرة — فلا تُقرأ قائمةٌ عابرة."""
    conn = L.open_ledger(tmp_path / "ledger.sqlite")
    try:
        L.ingest(conn, _rows(), L.pages_from_state(_rows(), {1: {"verdict": "ok"},
                                                            2: {"verdict": "ok"}}))
        # قائمةٌ «مسمومة» تُمرَّر مع `conn` — يجب أن تُتجاهَل لصالح القاعدة
        poisoned = [{"page": 9, "row_no": 1, "desc": "مزيف", "date": "2026-01-01",
                     "balance": "0.00", "movement": "98765.43", "side": "debit", "kind": "txn"}]
        tools = {t.name: t for t in make_qa_tools(poisoned, conn=conn)}
        got = tools["sum_movements"].invoke({"date_from": "2026-03-01", "date_to": "2026-03-31"})
        assert "388.41" in got and "98765" not in got, got
    finally:
        conn.close()


def test_no_phrase_list_was_added_to_forbid_a_sentence():
    """**الثابتُ المنصوص:** لا قائمةَ عباراتٍ تمنع «لا توجد حركات» — المنعُ بالقدرة لا باللفظ.

    يُقاس بالـAST في **الوحدات الثلاث** التي كانت ستحتاج القائمةَ لو لم تُبنَ القدرة (`qa_tools` ·
    `qa` · `render`): لا اسمَ مخزَّنًا يبدأ بـ`_ABSENCE`/`_AMBIG`/`_REFUSAL`/`_BANNED`، ولا قاموسَ
    مطابقةِ ألفاظ. **وحدُّه مُعلَن:** هذا فحصُ أسماءٍ لا سلوك؛ فحارسُ السلوك هو ضوابطُ الزمن
    (`balance_on` داخل المدّة/خارجها) — ولو كُتبت مطابقةُ نصٍّ بلا اسمٍ مذكورٍ لم يرها هذا الضابط.
    """
    for name in ("qa_tools.py", "qa.py", "render.py"):
        tree = ast.parse((ROOT / "src" / "statement_qa" / name).read_text(encoding="utf-8"))
        stored = {n.id for n in ast.walk(tree)
                  if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        forbidden = {n for n in stored
                     if n.upper().startswith(("_ABSENCE", "_AMBIG", "_REFUSAL", "_BANNED"))}
        assert not forbidden, f"{name}: أُضيفت قائمةُ عبارات: {sorted(forbidden)}"
