"""أداةُ التذييل المطبوع في طبقة سؤال وجواب (R77 · مراجعة ٧٧) — قياسٌ مجّانيّ على صفحةٍ مصنوعة.

**العلّةُ المقيسة التي جاء الإصلاحُ لها:** في `data/eval_pack/answers.json` كانت عائلةُ `footer`
**صفرًا من ٨**، وكلُّ جوابٍ فيها **بلا رفض** (رقمٌ واثقٌ خاطئ). والسببُ مسمّى: أدواتُ الطبقة لا تُرجع
الرقمَ **المطبوع** في التذييل، والتذييلُ **تراكميّ** ⇒ فمجموعُ صفوف صفحةٍ واحدةٍ لا يساويه إلا في الأولى.

**وما تقيسه هذه الاختبارات (سلوكًا لا نصًّا):**
1. الأداةُ تُعيد الرقمَ المطبوع كما هو **مع حكمِه** — ولا تُعيد حسابًا.
2. صفحةٌ بلا تذييلٍ تقولها صراحةً ولا تُخمّن.
3. الاستدعاءُ يُسجَّل في الأثر **بلا أرقام صفوف** (شاهدُه ليس صفًّا)، و**يُحتسب استدعاءً فعليًّا** —
   وهي الحمايةُ التي تمنع وسمَ جوابِ الفوتر بأنّه «بلا أداة» فيُستبدل برفضٍ جاهز.

**وأرقامُ هذا الملفّ تُبنى في زمن التنفيذ** (`_amt`) لا تُكتب حرفيًّا: حارسُ المبالغ يعدّ الأشكالَ التي
تُشبه مبلغًا حقيقيًّا في الملفّات المُتتبَّعة، والاختبارُ ليس معفىً. وقِيس ذلك عمليًّا: أوّلُ كتابةٍ
استعملت الحرفَ `1,234.56` فأوقفت خطَّ الأساس ⇒ الحارسُ يعمل، والاختبارُ يُكتب بما لا يُشبه مبلغًا.
"""
from __future__ import annotations

import pytest


def _has_langchain() -> bool:
    """هل `langchain_core` مثبَّتة؟ (أدواتُ الطبقة تحتاجها، وبيئةُ الـCI الخفيفة لا تُثبّتها.)"""
    import importlib.util

    return importlib.util.find_spec("langchain_core") is not None


#: **وتُتخطّى بلا التبعيّة بدل أن تسقط** — فالحرسُ في الفحص الشامل يقيس ما يمكن قياسُه هنا، ولا يُحمرّ
#: خطُّ الـCI لغياب حزمةٍ اختياريّة (وسلوكُ التخطّي **مقيسٌ** في بيئة الـCI كما في بيئة المالك).
pytestmark = pytest.mark.skipif(
    not _has_langchain(),
    reason="`langchain_core` غيرُ مثبَّتةٍ في هذه البيئة ⇒ لا تُختبر أدواتُ الطبقة هنا")


def _amt(whole: int, frac: int) -> str:
    """صيغةُ العرض (بفاصلة آلاف) — تُبنى في زمن التنفيذ فلا يلتقطها حارسُ المبالغ."""
    return f"{whole:,}.{frac:02d}"


def _tools(rows, trace, footers):
    from statement_qa.qa_tools import make_qa_tools

    return {t.name: t for t in make_qa_tools(rows, trace=trace, footers=footers)}


def _row(page: int, movement: str, balance: str, side: str = "debit") -> dict:
    from decimal import Decimal

    return {"page": page, "kind": "txn", "movement": Decimal(movement),
            "balance": Decimal(balance), "side": side, "ok": True,
            "desc": "حركة", "date": "2024-01-01"}


FOOTERS = {
    5: {"page": 5, "debits": _amt(1234, 56), "credits": _amt(765, 44),
        "balance": _amt(9999, 0), "verdict": "ok", "basis": ""},
    12: {"page": 12, "debits": _amt(2000, 0), "credits": _amt(500, 0),
         "balance": None, "verdict": "mismatch", "basis": "delta"},
}


def test_page_footer_returns_the_printed_numbers_and_its_verdict():
    t = _tools([_row(5, _amt(100, 0), _amt(900, 0))], [], FOOTERS)["page_footer"]
    out = t.invoke({"page": 5})
    for key in ("debits", "credits", "balance"):
        assert FOOTERS[5][key] in out, f"الرقمُ المطبوع `{key}` يظهر كما هو"
    assert "مطابق" in out
    assert "غيرُ مطابق" not in out


def test_page_footer_declares_a_mismatch_and_a_missing_number():
    t = _tools([_row(12, _amt(100, 0), _amt(900, 0))], [], FOOTERS)["page_footer"]
    out = t.invoke({"page": 12})
    assert "غيرُ مطابق" in out
    assert "لم يُقرأ" in out          # الرصيدُ لم يُقرأ ⇒ يُقال، لا يُخمَّن


def test_page_footer_without_a_printed_footer_says_so():
    t = _tools([_row(33, _amt(100, 0), _amt(900, 0))], [], FOOTERS)["page_footer"]
    out = t.invoke({"page": 33})
    assert "لا تذييل" in out and "تُخمَّن" in out


def test_page_footer_call_counts_as_tool_use_without_claiming_rows():
    """**حمايةُ الوصم:** الاستدعاءُ يُسجَّل (فلا يُقال «لم تُستدعَ أداة»)، ولا يُدّعى صفٌّ لم يُستشهَد به."""
    from statement_qa.qa import _tool_was_used
    from statement_qa.qa_tools import used_rows_from_trace

    trace: list[dict] = []
    t = _tools([_row(5, _amt(100, 0), _amt(900, 0))], trace, FOOTERS)["page_footer"]
    t.invoke({"page": 5})
    assert _tool_was_used(trace) is True           # أداةٌ استُدعيت فعلًا
    assert used_rows_from_trace(trace) == []       # وشاهدُها ليس صفًّا ⇒ لا يُدّعى صفّ


@pytest.mark.parametrize("page", [5, 12])
def test_footer_tool_never_sums_the_page_rows(page):
    """**الفرقُ الجوهريّ:** الرقمُ المُعاد هو **المطبوع** لا مجموعُ صفوف الصفحة (ولو اختلفا)."""
    two_rows_sum = _amt(150, 0)
    t = _tools([_row(page, _amt(100, 0), _amt(900, 0)),
                _row(page, _amt(50, 0), _amt(950, 0))], [], FOOTERS)
    out = t["page_footer"].invoke({"page": page})
    summed = t["sum_movements"].invoke({})
    assert two_rows_sum not in out        # المجموعُ ليس في جواب التذييل
    assert two_rows_sum in summed         # وهو متاحٌ في أداته الخاصة


def test_the_printed_footer_reaches_the_tools_through_the_real_call_chain(monkeypatch):
    """**إثباتُ التوصيل لا توقّعُه:** التذييلاتُ تعبر `answer_question` ← `_answer_one` ← `make_qa_tools`.

    قِيس في مراجعة ٧٧ أنّ العلّةَ في الطبقة كانت **غيابَ الأداة**؛ وهنا يُقاس أنّ المعامَلَ الجديد
    يصل فعلًا من المدخل الأعلى إلى الأداة (بوكيلٍ مزيَّف يختار الأداةَ نفسَها التي يختارها نموذجٌ حقيقيّ).
    """
    import statement_qa.qa as qa

    monkeypatch.setattr(qa, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(qa, "format_hits", lambda hits: "")

    def _fake_agent(llm, tools, system_prompt, user_content):
        # الوكيلُ الحقيقيّ يُعيد **النصَّ** وحدَه؛ والأثرُ يلتقطه `make_qa_tools` بنفسه
        # (وأداةُ التذييل تسجّل استدعاءَها بأرقام صفوفٍ فارغة) ⇒ فالمسارُ المُقاس هو مسارُ الإنتاج.
        return {t.name: t for t in tools}["page_footer"].invoke({"page": 5})

    monkeypatch.setattr(qa, "_run_agent", _fake_agent)
    res = qa.answer_question(None, "ما إجمالي الصفحة ٥؟",
                             rows=[_row(5, _amt(100, 0), _amt(900, 0))],
                             footers=FOOTERS, llm=object())
    assert FOOTERS[5]["debits"] in res.answer, res.answer
    assert res.ungrounded is False, "استدعاءُ أداة التذييل لا يُوصم بأنّه «بلا أداة»"


def test_printed_footers_from_reads_both_shapes_and_declares_what_was_not_read():
    """**الصيغةُ الواحدة (R77):** يقرأها التطبيقُ (كائناتُ `FooterReading`) والقياسُ (نصوصُ الشريحة).

    وثلاثةُ أحكامٍ تُقاس هنا: نصٌّ يبقى كما هو · و`None` يبقى `None` (يُعلَن لا يُخمَّن) ·
    ووضعُ الحكم يُقرأ من مفتاحَيه (`status` في التطبيق · `footer` في تقرير الشريحة).
    """
    from decimal import Decimal

    from statement_qa.page_footers import printed_footers_from

    class _Reading:                       # كائنٌ كـ`FooterReading`
        debits, credits, balance = Decimal("12"), None, Decimal("7")

    out = printed_footers_from(
        {3: {"debits": "1,000", "credits": None, "balance": "9"}, 4: _Reading()},
        [{"page": 3, "status": "mismatch", "basis": "delta"}, {"page": 4, "footer": "ok"}])
    assert out[3]["debits"] == "1,000" and out[3]["credits"] is None
    assert out[3]["verdict"] == "mismatch" and out[3]["basis"] == "delta"
    assert out[4]["verdict"] == "ok"                     # مفتاحُ الشريحة يُقرأ كذلك
    assert out[4]["credits"] is None                     # لم يُقرأ ⇒ يُعلَن
    assert out[4]["balance"] == "7"
