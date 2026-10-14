"""حدُّ السؤال الواحد (R109-1 · R110-1 · R110-2) — يُقاس بالنقيضين: العطبُ مُعادًا، والحدُّ قائمًا.

**الجذرُ المقيس قبل الإصلاح:** `agent.invoke` بلا `config` ⇒ حدُّ langgraph الافتراضيُّ 10007 خطوة،
و`ChatOpenAI` بلا مهلةٍ ولا حدِّ مخرجات، ولا حدِّ نداءاتٍ في الوكيل ⇒ **سؤالٌ واحدٌ طلب الأداةَ إلى
الأبد فأنفق وحدَه ما يقارب ثلثَ دولار** في قياس r108 (وتوقّف القياسُ عند ٣٠ من ٥٠).

**وثلاثةُ ثوابتَ تحرسها هذه الملفّ:**
1. السؤالُ الدوّارُ يقف عند حدِّ نداءاتٍ **حقيقيّ** (لا آلاف) — والنقيضُ مُعادٌ في التالي.
2. **والمستخدمُ لا يرى نصَّ المكتبة الإنجليزيّ:** بلوغُ الحدّ حالةٌ مُسمّاةٌ (`limit_hit`) برسالةٍ عربيّة.
3. **وسقفُ السؤال مشتقٌّ من بنية المسار** (طروحٌ × أجزاء) لا مكتوبٌ بيد.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from statement_qa import render
from statement_qa.qa import (MODEL_CALL_LIMIT, REQUEST_TIMEOUT_S, STEP_LIMIT, _run_agent,
                             answer_question, question_ceiling)

SAVED = Path("data/eval_pack")


class _ForeverToolModel(BaseChatModel):
    """نموذجٌ يطلب أداةً أبدًا — لا يقف إلّا بحدٍّ، ويعدّ نداءاتِه."""

    calls: int = 0
    tool_name: str = "page_summary"

    def bind_tools(self, tools, **kwargs):        # noqa: D102 — يكفي أن يقبل الربط
        return self

    @property
    def _llm_type(self) -> str:
        return "forever-tool-fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(
            content="",
            tool_calls=[{"name": self.tool_name, "args": {"page": 1},
                         "id": f"call-{self.calls}"}]))])


@tool
def tick() -> str:
    """أداةٌ بلا أثر — تكفي ليدور الوكيل في ضابط المسار المباشر."""
    return "tock"


class _NoHits:
    """مخزنٌ بلا نتائج: يُقاس ما يُمرَّر وما يُنفَق، لا ما يُسترجَع (ولا نموذجَ حقيقيًّا هنا)."""

    index = type("_Idx", (), {"ntotal": 1})()

    def similarity_search_with_score(self, query, k=4, filter=None, fetch_k=None):  # noqa: ARG002
        return []


ROWS = [{"row_no": 1, "page": 1, "printed_page": 1, "desc": "سطر", "date": "2026-01-01",
         "movement": "10.00", "side": "debit", "balance": "10.00", "printed_movement": "10.00",
         "printed_balance": "10.00", "counted": 1, "row_state": "عادي", "source": "طباعة"},
        {"row_no": 2, "page": 2, "printed_page": 2, "desc": "سطر", "date": "2026-01-02",
         "movement": "10.00", "side": "debit", "balance": "20.00", "printed_movement": "10.00",
         "printed_balance": "20.00", "counted": 1, "row_state": "عادي", "source": "طباعة"}]


def test_the_runaway_stops_at_the_ceiling_not_at_thousands_of_calls():
    """**R109-1 · والنقيضُ صار حدًّا مُعلنًا:** السؤالُ الذي لا ينتهي **يرفع
    `ModelCallLimitExceededError` عند الحدّ** — ولا تُبتلعه المكتبةُ بنصِّها الإنجليزيّ (عطبُ R110-2)."""
    from statement_qa.qa import _LIMIT_ERRORS, _limit_errors

    assert _LIMIT_ERRORS, ("لم يُقرأ أيُّ نوعِ خطأٍ للحدّ من المكتبة ⇒ بلوغُ الحدّ لن يُلتقط "
                           "بالنوع، وهو الشرطُ الذي منعه R110-2")
    assert _limit_errors() == _LIMIT_ERRORS
    ModelCallLimitExceededError = _LIMIT_ERRORS[0]

    model = _ForeverToolModel(tool_name="tick")
    with pytest.raises(ModelCallLimitExceededError):
        _run_agent(model, [tick], "نظامٌ للاختبار", "اسأل بلا نهاية")

    assert model.calls == MODEL_CALL_LIMIT, f"توقّف عند {model.calls} لا {MODEL_CALL_LIMIT}"


def test_the_library_default_would_spend_thousands_of_calls():
    """**النقيض:** بلا حدٍّ يبلغ الوكيلُ آلافَ النداءات — العطبُ مُعادًا بلا إنفاق حقيقيّ."""
    from langchain.agents import create_agent

    model = _ForeverToolModel(tool_name="tick")
    agent = create_agent(model=model, tools=[tick], system_prompt="اختبار")
    with pytest.raises(Exception):
        agent.invoke({"messages": [{"role": "user", "content": "go"}]})

    assert model.calls > 10 * MODEL_CALL_LIMIT, (
        f"بلا حدٍّ نُودي النموذجُ {model.calls} مرّةً ⇒ فالنقيضُ لم يُقَس")


def test_the_user_never_sees_the_librarys_english_note():
    """**R110-2 · يُقاس النصُّ المعروضُ نفسُه لا وجودُ عَلَم:** سؤالٌ دوّارٌ عبر المسار الكامل
    (`answer_question` ثمّ `render.answer_text`) ⇒ **لا «Model call limits» على الشاشة**، ورسالةٌ
    عربيّةٌ صادقة، والحالةُ مُسمّاةٌ في النتيجة — **والإنفاقُ داخل سقف السؤال لا خارجه**.
    """
    question = "ما إجماليُ الحركات في الصفحة ١؟"
    model = _ForeverToolModel()
    res = answer_question(store=_NoHits(), question=question, rows=ROWS, chunks=None,
                          llm=model, k=2, footers=None)
    shown = render.answer_text(res, page_of={}, verdicts={})

    assert "Model call limits" not in shown, shown[:200]
    assert "حدّ الخطوات" in shown, shown[:200]
    assert res.limit_hit is True, "بلوغُ الحدّ ليس حالةً مُسمّاةً في النتيجة"
    ceiling = question_ceiling(question)
    assert model.calls <= ceiling, f"{model.calls} نداءً خارج السقف المشتقّ {ceiling}"


def test_the_question_ceiling_is_derived_from_the_path_not_written_by_hand():
    """**R110-1 · العاملُ يُشتقّ من بنية المسار:** طرحان لكلّ جزءٍ (طرحٌ ثمّ تنبيه) + نداءُ الاحتياط
    ⇒ `الحدُّ × ٣ × الأجزاء`. فالحدُّ يُقرأ من الكود، ليس رقمًا يكتبه المراجع بيده.
    """
    from statement_qa.qa import split_compound

    one = "ما إجماليُ الحركات في الصفحة ١؟"
    two = ("هل يساوي رصيدُ آخر صفٍّ مطبوعٍ في الصفحة ١ رصيدَ أوّل صفٍّ مطبوعٍ في الصفحة ٢؟ "
           "وما الفرقُ بينهما بالمبلغ؟")
    assert len(split_compound(two)) == 2, split_compound(two)

    assert question_ceiling(one) == MODEL_CALL_LIMIT * 3 * 1
    assert question_ceiling(two) == MODEL_CALL_LIMIT * 3 * len(split_compound(two))
    assert question_ceiling(two) > question_ceiling(one), "المركّبُ ليس أكبرَ من البسيط"


def test_the_step_ceiling_is_ours_not_the_library_default():
    """حدُّ الخطوات يُمرَّر صريحًا ويقع **تحت** افتراضيّ المكتبة (مقيسٌ بالاستيراد)."""
    from langgraph._internal._config import DEFAULT_RECURSION_LIMIT

    assert STEP_LIMIT < DEFAULT_RECURSION_LIMIT


def test_the_model_carries_a_request_timeout_and_an_output_ceiling(monkeypatch):
    """مهلةُ الطلب **وحدُّ المخرجات** — كلاهما يُقيّد كلفةَ النداء من أعلى (R110-1).

    **ويُقاس بما بُنِي به النموذج لا بكائنٍ حقيقيّ:** `build_llm` يستورد `langchain_openai` داخل
    الدالّة، وبيئةُ الـCI الخفيفة تُثبّت `langchain`/`langchain-core`/`langgraph` **بلا
    `langchain_openai`** ⇒ فطلبُ الكائن حقّق `ModuleNotFoundError` في الـCI (قِيس) وهو ثقبُ بيئةٍ
    لا ثقبُ ضابط. فيُحلّ مزوّدٌ مُلتقِطٌ محلَّ الحزمة **ويُقاس ما يُمرَّر إليها** — وهي العلّةُ نفسُها.
    """
    import sys
    import types

    import statement_qa.qa as qa

    captured: dict = {}

    class _Captured:
        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setitem(sys.modules, "langchain_openai", types.SimpleNamespace(ChatOpenAI=_Captured))
    monkeypatch.setattr("statement_qa.api_key.get_api_key", lambda: "test-key")
    qa.build_llm("x/y")

    assert captured.get("timeout") == REQUEST_TIMEOUT_S, captured
    assert captured.get("max_retries") == 1, captured
    assert captured.get("max_tokens") == qa.MAX_ANSWER_TOKENS, captured


def test_the_ceiling_sits_above_every_question_measured_so_far():
    """الحدُّ لا يقطع جوابًا عاديًّا — **يُقاس من الملفّات المحفوظة** لا من الطمأنينة."""
    files = sorted(SAVED.glob("answers-*.json")) if SAVED.exists() else []
    if not files:
        pytest.skip("لا ملفّاتِ أجوبةٍ محفوظة في هذه البيئة")

    worst, where = 0, None
    for path in files:
        for res in json.loads(path.read_text(encoding="utf-8")).get("results") or []:
            n = len(res.get("tools_used") or [])
            if n > worst:
                worst, where = n, f"{path.name}:{res.get('id')}"

    assert worst + 1 <= MODEL_CALL_LIMIT, (
        f"أكثرُ ما احتاجه سؤالٌ محفوظ: {worst} نداءَ أداة ({where}) ⇒ الحدُّ يقطع جوابًا قائمًا")
