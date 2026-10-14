"""**R109-3 — الأدواتُ ترفض المدخلات المجهولة، وتُسجَّل مدخلاتُ كلّ نداء في الأثر.**

**العطبُ المقيس (مراجعة ١١٧ · `forbid` = ٠ في الأدوات):** مخطّطُ وسائط الأداة في
`langchain-core` يبنى من التوقيع، و`extra` فيه **`None`** ⇒ فالخانةُ الزائدة تُهمَل **صامتةً**.
قِيس بأداةٍ مصغّرة على المكتبة نفسها: `{"side": "مدين", "foo": 1}` نُفِّذ وأعاد الجوابَ ذاته
كأنّ `foo` لم تُذكر ⇒ **مدخلٌ مجهولٌ يُنتج رقمًا** بدل أن يُرفض.

**ونصُّ الرفض كان يُفرَغ قبل أن يصل النموذج (R118-1 · مراجعة ١١٨):** مسبارُ هذه الجولة بنموذجٍ
مُبرمَج عبر `answer_question` قرأ في `ToolMessage`: `"… with error:\n \n Please fix the error…"`
— **بلا اسم الخانة** — لأنّ مُحقِّقًا يدويًّا فوق `extra="forbid"` يرفع خطأً على مستوى النموذج
(بلا `loc`) تُسقِطه مرشّحةُ `ToolNode`. فالنموذجُ لا يعرف ما يُصلح، **والضابطُ هنا يقيس ما يراه هو**
لا ما يُرفع في `.invoke` المباشر.

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
    """**والرسالةُ تسمّي الخانةَ — من المكتبة لا من طبقةٍ يدويّة (R118-1 · مراجعة ١١٨):**
    كانت فوق `extra="forbid"` طبقةُ `@model_validator(mode="before")` ترفع خطأً على مستوى النموذج
    كلّه (بلا `loc`) ⇒ فتُسقطه مرشّحةُ `ToolNode` ويصل النموذجَ **نصٌّ فارغ**. والطبقةُ أُزيلت،
    والمكتبةُ تسمّي الخانةَ (`foo: Extra inputs are not permitted`)."""
    tools = _by_name(_tools())
    with pytest.raises(_VE()) as err:
        tools["sum_movements"].invoke({"side": "مدين", "foo": 1})
    text = str(err.value)
    assert "foo" in text and "extra_forbidden" in text, \
        f"الرفضُ لا يسمّي المدخلَ المجهول: {text[:200]}"
    assert "side" in str(tools["sum_movements"].args_schema.model_fields), \
        "المخطّطُ المرسَل لا يعلن الوسائطَ المقبولة (فلا يعرف النموذجُ ما يُصلح)"


class _ScriptedUnknownCall:
    """نموذجٌ مُبرمَج: يطلب `count_movements(page=9)` (خانةٌ لا تعرفها الأداة) ثمّ يجيب."""

    def __init__(self):
        self.tool_texts: list[str] = []

    def build(self):
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage, ToolMessage
        from langchain_core.outputs import ChatGeneration, ChatResult

        outer = self

        class _Scripted(BaseChatModel):
            def _generate(self, messages, stop=None, run_manager=None, **kw):
                seen = [m for m in messages if isinstance(m, ToolMessage)]
                if seen:
                    outer.tool_texts = [str(m.content) for m in seen]
                    return ChatResult(generations=[ChatGeneration(message=AIMessage("ok"))])
                call = {"name": "count_movements", "args": {"page": 9}, "id": "c1",
                        "type": "tool_call"}
                return ChatResult(generations=[ChatGeneration(message=AIMessage("", tool_calls=[call]))])

            def bind_tools(self, tools, **kw):
                return self

            def with_structured_output(self, schema, **kw):
                return self

            @property
            def _llm_type(self):
                return "scripted-r118"

        return _Scripted()


def test_the_refusal_reaches_the_model_with_the_field_name():
    """**القبولُ بنصّه (R118-1):** نموذجٌ مُبرمَج عبر `answer_question` ⇒ الـ`ToolMessage` يسمّي
    الخانة. قِيس على الرأس `13fb534` **فارغًا** (`"… with error:\n \n Please fix…"`)."""
    pytest.importorskip("langchain")
    pytest.importorskip("langgraph")
    from statement_qa.qa import answer_question

    class _NoStore:
        def similarity_search_with_score(self, *_a, **_k):
            return []

    rows = [{"page": 1, "row": 1, "page_row": 1, "date": "2026-01-02", "movement": "100.00",
             "balance": "4,321.00", "debit": "100.00", "credit": None, "description": "رسوم",
             "desc": "رسوم", "kind": "txn"}]
    script = _ScriptedUnknownCall()
    answer_question(_NoStore(), "كم حركةً في الكشف؟", rows=rows, llm=script.build())
    assert script.tool_texts, "لم يُلتقط ToolMessage — والمسبارُ نفسه مشكوكٌ فيه"
    text = script.tool_texts[0]
    assert "page" in text or "foo" in text, f"الرسالةُ لا تسمّي الخانةَ المرفوضة: {text!r}"
    assert "with error:\n \n" not in text, f"نصُّ الخطأ فارغٌ كما كان (R118-1): {text!r}"


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
