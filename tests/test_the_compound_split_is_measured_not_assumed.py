"""**R118-2 (= R105-5) — التقسيمُ حُذف: الحكمُ قِيس أوّلًا، والسؤالُ يُطرح كاملًا.**

**الحكمُ بنصّه** (`20261010-023343` §٤، وأعاده `184500` بندًا): السؤالُ المجّانيّ هو **هل تحرس
بوّابةُ قراءة الجواب مع بوّابة النطاق الحالةَ F؟** فإن نعم ⇒ **يُحذف التقسيم**، وإن لا ⇒ يُمرَّر
النصفُ الأوّل سياقًا للثاني. **و«الإبقاءُ كما هو» ليس أحدَ الفرعين** (مراجعة ١١٨).

**والقياسُ بلا كلفة — هذا الملفّ، و`answers-r108-03.json`، وبلا نداءِ نموذج:**

| المقياس | المقيس |
| :--- | :--- |
| الجزءُ الثاني كما يصنعه التقسيم | `«ما الفرقُ بينهما بالمبلغ»` — **بلا مرجع**: لا صفحةَ ولا صفّ |
| `needs_tools` على الجزء | **False** (لا كلمةَ عددٍ فيه) ⇒ البوّابةُ لا تطلبه |
| جوابُه المقيس في `chn-01..04` | **نصٌّ واحدٌ متطابق** (بصمة `ebf18e19` · ٢٣٥ حرفًا · **صفرُ مبالغ**) ⇒ `_money_shaped` = False |
| ⇒ الحكمُ على الجزء | **البوّابةُ عمياءُ عنه بالبناء**: لا تطلبه ولا تقرأ فيه مبلغًا — وهو العطبُ الحيّ |
| وعلى السؤال **كاملًا** | مبلغٌ في الجواب بلا نداءِ أداةٍ **يُشعل البوّابة** (توجيهٌ ثمّ رفضُ «رقم لم يُحسَب») |

⇒ **فالتقسيمُ هو ما يُعطّل الحرسَ ويصنع الطلبَ الكاذب** (المستخدمُ سأل سؤالًا يسمّي الطرفين ثمّ
يُطلب منه توضيحُه)، **والمرجعُ يحضر بمجرّد أن يُطرح السؤالُ كاملًا** ⇒ **يُحذف** كما حكم §٤ بفرعه
الأوّل، والكودُ اليدويُّ يقلّ.

**وما يُقاس في هذا الملفّ:** أنّه لا وظيفةَ تقسيمٍ باقية (ولا مدخلَ خلفيّ)، وأنّ السقفَ لم يبقَ
مضروبًا في عدد الأجزاء، وأنّ السؤالَ المركّبَ **يصل النموذجَ كاملًا بمرجعه**، وأنّ الحزمةَ لا تحمل
سؤالًا بشكل «شظيّةٍ» بلا مرجع. **وعلامةُ القياس المدفوع (الخمسون):** غيابُ البصمة `ebf18e19` —
تُقرأ في الجولة ولا تُدّعى الآن.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import statement_qa.qa as qa  # noqa: E402

PACK = ROOT / "docs" / "eval_pack" / "questions.json"
QA_SRC = ROOT / "src" / "statement_qa" / "qa.py"
RUN = pathlib.Path.home() / "Projects" / "rajhi-rag" / "data" / "eval_pack" / "answers-r108-03.json"
COMPOUND_IDS = ("chn-01", "chn-02", "chn-03", "chn-04", "cit-02")
COMPOUND = ("هل يساوي رصيدُ آخر صفٍّ مطبوعٍ في الصفحة ٥٢ رصيدَ أوّل صفٍّ مطبوعٍ في الصفحة ٥٣؟"
            " وما الفرقُ بينهما بالمبلغ؟")


def _pack() -> list[dict]:
    return json.loads(PACK.read_text(encoding="utf-8"))["questions"]


# ── ① لا تقسيمَ بعد اليوم — ولا مدخلَ خلفيّ ────────────────────────────────────────────────
def test_the_split_function_is_gone_from_the_module():
    src = QA_SRC.read_text(encoding="utf-8")
    assert "def split_compound" not in src, "التقسيمُ عاد ⇒ حكمُ §٤ نُقض بلا قياس"
    calls = [ln for ln in src.splitlines()
             if "split_compound(" in ln and not ln.lstrip().startswith("#")]
    assert not calls, f"اسمُ التقسيم يُنادى من الكود: {calls} — والسحبُ نصفُ سحب"


def test_the_ceiling_is_not_multiplied_by_parts():
    """**والسقفُ ينخفض ولا يرتفع:** كان ×٢ للمركّب (طرحان) ⇒ والآن حدُّ البسيط هو حدُّ الكلّ."""
    per_question = qa.MODEL_CALL_LIMIT * (qa.MAX_ATTEMPTS_PER_PART + qa.FALLBACK_CALLS_PER_PART)
    assert qa.question_ceiling("كم مجموع الحركات المدينة؟") == per_question
    assert qa.question_ceiling(COMPOUND) == per_question, \
        "المركّبُ ما زال يُضاعف السقفَ ⇒ التقسيمُ باقٍ في حساب الحدّ"


# ── ② السؤالُ المركّبُ يصل الوكيلَ كاملًا (نموذجٌ مسجِّل · بلا كلفة) ────────────────────────
class _Recorder:
    """نموذجٌ مسجِّل: يحفظ **نصَّ كلّ رسالةٍ بشريّة** كما وصلت — وهو المقيس."""

    def __init__(self):
        self.human_texts: list[str] = []

    def build(self):
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage, HumanMessage
        from langchain_core.outputs import ChatGeneration, ChatResult

        outer = self

        class _M(BaseChatModel):
            def _generate(self, messages, stop=None, run_manager=None, **kw):
                outer.human_texts += [str(m.content) for m in messages
                                      if isinstance(m, HumanMessage)]
                return ChatResult(generations=[ChatGeneration(message=AIMessage("الفرق 37.00"))])

            def bind_tools(self, tools, **kw):
                return self

            def with_structured_output(self, schema, **kw):
                return self

            @property
            def _llm_type(self):
                return "recorder-r118"

        return _M()


def _ask(question=COMPOUND, **kw):
    pytest.importorskip("langchain")
    pytest.importorskip("langgraph")
    from statement_qa.qa import answer_question

    class _NoStore:
        def similarity_search_with_score(self, *_a, **_k):
            return []

    rec = _Recorder()
    rows = [{"page": 52, "row": 1, "page_row": 1, "date": "2026-01-02", "movement": "37.00",
             "balance": "37.33", "debit": "37.00", "credit": None, "description": "خصم",
             "desc": "خصم", "kind": "txn"},
            {"page": 53, "row": 2, "page_row": 1, "date": "2026-01-03", "movement": None,
             "balance": "0.33", "debit": None, "credit": None, "description": "رصيد",
             "desc": "رصيد", "kind": "txn"}]
    return rec, answer_question(_NoStore(), question, rows=rows, llm=rec.build(), **kw)


def test_the_compound_question_reaches_the_model_whole():
    """**القبولُ بنصّه (مراجعة ١١٨):** في الحذف، المركّبُ يصل الوكيلَ كاملًا."""
    rec, _res = _ask()
    assert rec.human_texts, "لم تصل رسالةٌ بشريّةٌ إلى النموذج — والمسبارُ نفسه مشكوكٌ فيه"
    assert any(COMPOUND in text for text in rec.human_texts), \
        f"المركّبُ لم يصل كاملًا في أيّ نداء: {rec.human_texts}"
    for text in rec.human_texts:
        if "ما الفرقُ بينهما بالمبلغ" in text:
            assert "الصفحة ٥٢" in text and "الصفحة ٥٣" in text, \
                "وصل جزءُ «بينهما» بلا مرجعه — وهو عينُ عطب R105-5"


# ── ③ الحزمةُ لا تحمل شظيّةً بلا مرجع ───────────────────────────────────────────────────────
def test_no_pack_question_is_shaped_like_the_lost_fragment():
    """**النقيضُ الذي يعضّ:** الشظيّةُ التي حكم عليها التقسيم («ما الفرق بينهما بالمبلغ») تُقاس
    بمعيارٍ لا بلفظها: **إشارةٌ إلى طرفين بلا أن يُسمّى أحدهما**. والحزمةُ كلُّها يجب أن تنجو منه."""
    def _names_a_referent(q: str) -> bool:
        return bool(re.search(r"(الصفحة|صف|السطر|صفحت)", q))

    fragments = [q["id"] for q in _pack()
                 if ("بينهما" in q["q"] or "بينه" in q["q"]) and not _names_a_referent(q["q"])]
    assert not fragments, f"سؤالٌ بشكل شظيّةٍ بلا مرجع: {fragments}"
    # **والخمسةُ المقسومةُ سابقًا** تُسمّي مرجعَها (وهو ما أعاد الحذفُ إليها):
    by_id = {q["id"]: q for q in _pack()}
    for qid in COMPOUND_IDS:
        assert _names_a_referent(by_id[qid]["q"]), f"{qid} لا يسمّي مرجعَه"


# ── ④ الأدلّةُ التي بُني عليها الحذف — تُعاد من الملفّ المحفوظ (محلّيٌّ فقط) ───────────────
def test_the_historical_evidence_is_reproducible():
    """**يُعاد تشغيلُ ما بُني عليه الحكم من الملفّ لا من التقرير** — والبياناتُ محلّيّة ⇒ يُعلَن التخطّي."""
    rec: dict = {}
    try:
        rec = {r["id"]: r for r in json.loads(RUN.read_text(encoding="utf-8"))["results"]}
    except (OSError, ValueError, KeyError):
        rec = {}
    if not rec:
        pytest.skip("لا جولةَ محفوظة في هذه الشجرة (بياناتُ المالك لا تصل الـCI) — تُقرأ عند المالك")
    for qid in ("chn-01", "chn-02", "chn-03", "chn-04"):
        ans = rec[qid]["answer"]
        second = ans.split("\n\n• ")[-1]
        assert "غير محدد المرجع" in second, \
            f"{qid}: الشظيّةُ لم تُنتج طلبَ توضيحٍ في هذه الجولة — فالشاهدُ تغيّر: {second[:80]}"
        assert not re.search(r"\d+[.,]\d{2}", second), \
            f"{qid}: النصفُ الثاني حمل مبلغًا ⇒ البوّابةُ كانت تُصيبه (والمقيسُ أنّه لم يحمل)"
