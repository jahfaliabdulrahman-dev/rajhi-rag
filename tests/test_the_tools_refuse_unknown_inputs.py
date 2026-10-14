"""**R109-3 — الأدواتُ ترفض المدخلات المجهولة، وتُسجَّل مدخلاتُ كلّ نداء في الأثر.**

**العطبُ المقيس (مراجعة ١١٧ · `forbid` = ٠ في الأدوات):** مخطّطُ وسائط الأداة في
`langchain-core` يبنى من التوقيع، و`extra` فيه **`None`** ⇒ فالخانةُ الزائدة تُهمَل **صامتةً**.
قِيس بأداةٍ مصغّرة على المكتبة نفسها: `{"side": "مدين", "foo": 1}` نُفِّذ وأعاد الجوابَ ذاته
كأنّ `foo` لم تُذكر ⇒ **مدخلٌ مجهولٌ يُنتج رقمًا** بدل أن يُرفض.

**والمدخلُ لم يكن يُسجَّل في الأثر:** `_record` كان يكتب `{"tool", "row_nos"}` **وإذا اختارت
الأداةُ صفرًا لا يكتب شيئًا** ⇒ فالمحاسبُ يقرأ أثرًا ناقصًا ولا يرى ما طُلب.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

ROWS = [
    {"page": 1, "date": "2026-01-02", "movement": "100.00", "balance": "4,321.00",
     "side": "debit", "type": "رسوم", "desc": "رسوم إدارة", "kind": "txn"},
    {"page": 1, "date": "2026-01-03", "movement": "50.00", "balance": "950.00",
     "side": "credit", "type": "تحويل وارد", "desc": "تحويل", "kind": "txn"},
]


def _VE():
    """استثناءُ التحقّق **داخل الدالّة**: البيئةُ الخفيفةُ لا تُركِّب `pydantic` ⇒ فلا استيرادَ
    على مستوى الوحدة يُسقط تجميعَ الملفّ (وهو ما يجعل عدّادَ البيئة يتقادم صامتًا)."""
    return pytest.importorskip("pydantic").ValidationError


def _tools(trace=None):
    """الأدواتُ الحقيقيّة من `make_qa_tools` — بلا نموذجٍ وبلا كلفة."""
    from statement_qa.qa_tools import make_qa_tools

    return make_qa_tools(ROWS, trace=trace)


def _by_name(tools):
    return {t.name: t for t in tools}


# ── ① المدخلُ المجهول يُرفض ولا يُنفَّذ ───────────────────────────────────────────────────
def test_an_unknown_argument_is_refused_not_ignored():
    tools = _by_name(_tools())
    with pytest.raises(_VE()) as err:
        tools["sum_movements"].invoke({"side": "مدين", "foo": 1})
    text = str(err.value)
    assert "مدخلٌ مجهول" in text and "foo" in text, \
        f"الرفضُ لا يسمّي المدخلَ المجهول: {text[:200]}"
    assert "side" in text, "الرفضُ لا يسمّي الوسائطَ المقبولة"


def test_the_same_call_without_the_unknown_key_still_runs():
    """**نقيضٌ في الضابط نفسه:** المنعُ لا يمسّ النداءَ الصحيح (وإلّا ابتلعت البوّابةُ العمل)."""
    tools = _by_name(_tools())
    assert "المجموع" in tools["sum_movements"].invoke({"side": "مدين"})


def test_a_typo_cannot_return_a_number():
    """**العطبُ الأصليّ بعينه:** `keywordt` (حرفٌ زائد) كان يُهمَل فيعود مجموعُ الكشف كلِّه."""
    tools = _by_name(_tools())
    with pytest.raises(_VE()):
        tools["sum_movements"].invoke({"keywordt": "رسوم"})
    with pytest.raises(_VE()):
        tools["page_rows"].invoke({"page": 1, "limitt": 5})


def test_every_tool_carries_the_strict_schema():
    """**الوصولُ مُعدَّد لا مُدَّعى:** الثمانيةُ كلُّها، لا التي مُسِست في الاختبار."""
    tools = _tools()
    assert len(tools) == 8, f"عددُ الأدوات تغيّر ({len(tools)}) ⇒ حدِّث نطاقَ الضابط"
    for t in tools:
        extra = (t.args_schema.model_config or {}).get("extra")
        assert extra == "forbid", f"الأداة {t.name}: extra={extra!r} ⇒ تقبل مدخلًا مجهولًا"


def test_the_strict_schema_still_declares_the_real_parameters():
    """**ولا يُفرَغ المخطّط:** الصرامةُ لا تُسقط الوسائطَ المعلَنة (البديلُ الأسوأ من العطب)."""
    tools = _by_name(_tools())
    fields = set(tools["sum_movements"].args_schema.model_fields)
    assert {"side", "keyword", "tx_type", "amount", "page"} <= fields, fields
    assert "page" in tools["page_footer"].args_schema.model_fields


# ── ② كلُّ نداءٍ يُسجَّل بمدخله ───────────────────────────────────────────────────────────
def test_the_trace_records_the_inputs_of_every_call():
    trace: list[dict] = []
    tools = _by_name(_tools(trace))
    tools["sum_movements"].invoke({"side": "مدين", "keyword": "رسوم"})
    tools["page_rows"].invoke({"page": 1})
    assert [e["tool"] for e in trace] == ["sum_movements", "page_rows"], trace
    assert trace[0]["args"] == {"side": "مدين", "keyword": "رسوم", "tx_type": "",
                                "amount": None, "page": None}, trace[0]
    assert trace[1]["args"]["page"] == 1 and trace[1]["args"]["limit"] == 40


def test_a_call_that_selects_nothing_is_still_recorded():
    """كان الأثرُ يُكتَم إن لم تختر الأداةُ صفًّا ⇒ فيقرأ المحاسبُ أثرًا ناقصًا بلا سبب."""
    trace: list[dict] = []
    tools = _by_name(_tools(trace))
    out = tools["page_summary"].invoke({"page": 999})
    assert "لا توجد بيانات" in out
    assert trace and trace[-1]["tool"] == "page_summary" and trace[-1]["args"] == {"page": 999}
    assert trace[-1]["row_nos"] == []


def test_the_footer_call_is_recorded_with_its_page_and_no_rows():
    trace: list[dict] = []
    tools = _by_name(_tools(trace))
    tools["page_footer"].invoke({"page": 1})
    assert trace[-1] == {"tool": "page_footer", "args": {"page": 1}, "row_nos": []}
