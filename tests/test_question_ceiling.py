"""حدُّ السؤال الواحد (R109-1) — يُقاس بالنقيضين: العطبُ مُعادًا، والحدُّ قائمًا.

**الجذرُ المقيس قبل الإصلاح:** `agent.invoke` بلا `config` ⇒ حدُّ langgraph الافتراضيُّ 10007 خطوة،
و`ChatOpenAI` بلا مهلةٍ ولا حدِّ نداءات ⇒ **سؤالٌ واحدٌ طلب الأداةَ إلى الأبد فأنفق وحدَه ما يقارب**
**ثلثَ دولار** في قياس r108 وتوقّف القياسُ عند ٣٠ من ٥٠.

**وما لا يقطعه الحدّ:** أكثرُ ما احتاجه سؤالٌ في الملفّات المحفوظة (r105/r107/r108) خمسةُ نداءاتِ
أدوات (`cit-02` في r105) ⇒ ١٢ نداءً هامشٌ مضاعف لا يمسّ جوابًا واحدًا — ويُقاس من الملفّات نفسها.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from statement_qa.qa import (MODEL_CALL_LIMIT, REQUEST_TIMEOUT_S, STEP_LIMIT,
                             _run_agent)

SAVED = Path("data/eval_pack")


class _ForeverToolModel(BaseChatModel):
    """نموذجٌ يطلب الأداةَ أبدًا — لا يقف إلّا بحدٍّ، ويعدّ نداءاتِه."""

    calls: int = 0

    def bind_tools(self, tools, **kwargs):        # noqa: D102 — يكفي أن يقبل الربط
        return self

    @property
    def _llm_type(self) -> str:
        return "forever-tool-fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(
            content="",
            tool_calls=[{"name": "tick", "args": {}, "id": f"call-{self.calls}"}]))])


@tool
def tick() -> str:
    """أداةٌ بلا أثر — تكفي ليدور الوكيل."""
    return "tock"


def test_a_runaway_question_stops_at_the_ceiling_not_at_thousands_of_calls():
    """السؤالُ الذي لا ينتهي يقف عند الحدّ — **بلا استثناء` وبلا إنفاق** (R109-1)."""
    model = _ForeverToolModel()
    answer, parsed, mode = _run_agent(model, [tick], "نظامٌ للاختبار", "اسأل بلا نهاية")

    assert model.calls <= MODEL_CALL_LIMIT, (
        f"نُودي النموذجُ {model.calls} مرّةً — والحدُّ المعلَن {MODEL_CALL_LIMIT}")
    assert isinstance(answer, str)
    assert mode == "prose" and parsed is None


def test_the_library_default_would_spend_thousands_of_calls():
    """**النقيض:** بلا حدٍّ يبلغ الوكيلُ آلافَ النداءات — العطبُ مُعادًا بلا إنفاق حقيقيّ."""
    from langchain.agents import create_agent

    model = _ForeverToolModel()
    agent = create_agent(model=model, tools=[tick], system_prompt="اختبار")
    with pytest.raises(Exception):
        agent.invoke({"messages": [{"role": "user", "content": "go"}]})

    assert model.calls > 10 * MODEL_CALL_LIMIT, (
        f"بلا حدٍّ نُودي النموذجُ {model.calls} مرّةً ⇒ فالنقيضُ لم يُقَس")


def test_the_step_ceiling_is_ours_not_the_library_default():
    """حدُّ الخطوات يُمرَّر صريحًا ويقع **تحت** افتراضيّ المكتبة (مقيسٌ بالاستيراد)."""
    from langgraph._internal._config import DEFAULT_RECURSION_LIMIT

    assert STEP_LIMIT < DEFAULT_RECURSION_LIMIT


def test_the_model_carries_a_real_request_timeout(monkeypatch):
    """مهلةُ الطلب نفسِه — لا مهلةُ انتظارٍ في أداة القياس (R109-1).

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
