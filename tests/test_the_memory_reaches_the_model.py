"""إثباتُ ما لم يُثبت: **هل يصل السجلُّ والنطاقُ إلى تلقين النموذج فعلًا؟** (R92)

**ما كان غيرَ مُثبت:** بوّاباتُ البند ١ تُثبت أنّ الدالّة النقيّة تُصيغ السجلَّ صحيحًا، وتُثبت أنّ الواجهةَ
**تنادي** بالكلمتين — **ولا تُثبت أنّ ما يُصاغ يبلغ النموذج**. والفرقُ هو الذي يفرّق بين «ميزةٌ مكتوبة»
و«ميزةٌ تعمل»: مسارٌ كاملٌ قد يُبنى فيه التلقينُ ثمّ يُهمَل قبل النداء.

**كيف يُثبت بلا كلفة:** يُعترَض `_run_agent` (آخرُ محطّةٍ قبل المزوّد) فيُلتقَط **نصُّ التلقين** الذي كان
سيُرسَل، ويُنادى **نفسُ** الدالّة التي تستدعيها طبقةُ الجواب (`_answer_with_tools`). فالبرهانُ على
**المُدخَل عند حدود المزوّد** لا على قصد الكاتب.

**ولماذا `_answer_with_tools` لا `answer_question`:** الثانيةُ لا تبلغ الأولى إلّا بعد بوّابة النطاق
الرقمية (`qa.py:403`) — وهي بوّابةٌ صحيحةٌ تُصنَّف صفَّ اختبارٍ واحد «خارج النطاق». فيُقاس الموضعُ الذي
**يُبنى فيه التلقين فعلًا**، ويُقاس **التمريرُ عبر السلسلة** بالـAST أعلاه.

**وما لا يُثبته هذا الملفّ (يُقال صراحةً):** أن يجيب النموذجُ **أحسن** — أثرٌ لا يُقاس إلا بنداءٍ مدفوع،
وتكلفتُه تُطلب من المالك قبل إنفاقها.
"""

from __future__ import annotations

import ast
import pathlib

from statement_qa import qa

QA_SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "statement_qa" / "qa.py"
ROWS = [{"page": 1, "row": 1, "description": "شراء", "amount": "10.00",
         "debit": "10.00", "credit": None, "balance": "100.00",
         "derived_movement": "10.00", "opening": False, "proven": True}]
Q = "وماذا عن الصفحة ٢؟"


class _AgentText:
    """بديلُ نتيجة الوكيل — يكفي ليمرّ المسار بلا نموذجٍ حقيقيّ."""

    mode = "tools"
    numbers: list = []
    cited_row_ids: list = []
    unsupported_citations: list = []


def _capture(monkeypatch) -> dict:
    seen: dict = {}

    def _fake_agent(llm, tools, system_prompt, user_content, **_kw):
        seen["system"], seen["user"] = system_prompt, user_content
        return "الجواب", _AgentText(), "tools"

    monkeypatch.setattr(qa, "_run_agent", _fake_agent)
    return seen


def _ask(**kw):
    return qa._answer_with_tools(object(), ROWS, "قطعةُ سياق", Q, **kw)


def test_the_previous_turn_reaches_the_model_prompt(monkeypatch) -> None:
    """**الدعوى الحاكمة:** سؤالٌ سابقٌ وجوابُه والنطاقُ تظهر **في نصّ التلقين المُرسَل**."""
    seen = _capture(monkeypatch)
    _ask(history=[("كم عدد الحركات؟", "١٠٣ حركة")], scope="كشفُ الاختبار")
    assert seen, "المسارُ لم يبلغ محطّةَ النموذج إطلاقًا — لا برهانَ على مُدخَل"
    assert "كم عدد الحركات؟" in seen["system"], "السؤالُ السابقُ لم يبلغ النموذج"
    assert "١٠٣ حركة" in seen["system"], "الجوابُ السابقُ لم يبلغ النموذج"
    assert "كشفُ الاختبار" in seen["system"], "النطاقُ لم يبلغ النموذج"


def test_without_memory_the_prompt_is_the_old_one_to_the_letter(monkeypatch) -> None:
    """**وقياسُ النقيض:** بلا سجلٍّ ولا نطاقٍ ⇒ نصُّ الوكيل الأصليّ بحرفه (لا انزلاقَ صامت)."""
    seen = _capture(monkeypatch)
    _ask()
    assert seen["system"] == qa.AGENT_SYSTEM_PROMPT


def test_the_model_is_asked_the_question_it_was_given(monkeypatch) -> None:
    """**ولا يُنقل النصُّ من مكانه:** سؤالُ المستخدم المُرسَل هو السؤالُ نفسُه."""
    seen = _capture(monkeypatch)
    _ask(history=[("قديم", "قديم")], scope="نطاق")
    assert Q in seen["user"]


def test_the_whole_chain_forwards_the_two_arguments() -> None:
    """**والسلسلةُ تمرّر (AST):** `answer_question` تُعلن المعاملين **وتمرّرهما** إلى `_answer_one`."""
    tree = ast.parse(QA_SRC.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "answer_question")
    names = {a.arg for a in fn.args.args}
    assert {"history", "scope"} <= names, f"answer_question لا تُعلنهما: {sorted(names)}"
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "_answer_one"]
    assert calls, "لا نداءَ لـ`_answer_one` — السلسلةُ انقطعت"
    kw = set().union(*({k.arg for k in c.keywords} for c in calls))
    assert {"history", "scope"} <= kw, f"السلسلةُ لا تمرّرهما: {sorted(kw)}"
