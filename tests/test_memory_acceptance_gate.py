"""ضابطُ قبول ذاكرة الحوار — يكتبه المدقّق ويشغّله (قرار 98ب · الشرط ٤ · مراجعة ٩٩).

**ما يقيسه:** سؤالان متتاليان **في التطبيق نفسه** — `prepare_ask` ثمّ `ask_followup` كما يربطهما زرُّ
«اسأل» — على حالةٍ بناها **مسارُ القراءة في `app.py`** (الـ fixture `read_sample` من ضابط زرّ Excel:
العيّنةُ المصطنعةُ المتتبَّعة، ونداءاتُ النموذج وحدها مستبدَلة، والشبكةُ مغلقة ⇒ $0 مُثبتًا).
والنموذجُ في السؤالين **مسجِّل** يرى ما يصل إليه فعلًا. والمستبدَلُ غيرُه شيءٌ واحد: الاسترجاعُ يعيد
قطعَ الكشف نفسِها (فهرسُ البحث يُحمّل نموذجَ تضمين، والضابطُ عن الذاكرة لا عن البحث).

**الضابطان دعوى القرار (يمرّان على الفرع، ويسقط الأوّلُ على `main` 8ebe827 حيث السجلُّ نصٌّ في التعليمات):**
السؤالُ السابقُ وجوابُه يبلغان النموذجَ **رسائلَ** لا نصًّا في التعليمات · وقراءةٌ جديدةٌ تبدأ محادثةً نظيفة.

**وملاحظتا مراجعة ٩٩ (R99-1 رقمٌ مرفوضٌ يبلغ السؤالَ التالي · R99-2 قطعُ الاسترجاع تتراكم) مقيستان بهذه
الـ fixture نفسِها** في المراجعة، وضابطاهما يهبطان **مع إصلاحهما** ناجحَين (`chat` جاهزةٌ لهما).

**وما لا يقيسه:** جودةَ الجواب بنموذجٍ حقيقيّ — تلك إعادةُ قياس الخمسين المدفوعة بعد هذا الضابط.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("gradio")
pytest.importorskip("langchain")
pytest.importorskip("langgraph")

from langchain_core.language_models.chat_models import BaseChatModel     # noqa: E402
from langchain_core.messages import AIMessage                            # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult            # noqa: E402
from test_button_builds_a_workbook import SAMPLE, read_sample            # noqa: E402,F401 (fixture)

Q1 = "ما وصف أول حركة في الصفحة ١؟"
Q2 = "وما وصف الحركة التي تليها؟"
REFUSED = "٧٧٧٫٧٧"      # رقمٌ يقوله المسجِّلُ بلا أداة ⇒ يرفضه التطبيق (مسبارُ R99-1 في المراجعة)


class _Recorder(BaseChatModel):
    """نموذجٌ مسجِّل: يحفظ رسائلَ كلِّ نداء، ويجيب بالنوع المُقيَّد إن رُبط (`Answer`)."""

    calls: list = []
    bound: list = []

    def _generate(self, messages, stop=None, run_manager=None, **kw):
        self.calls.append(list(messages))
        asked = [m for m in messages if m.type == "human"][-1].content
        from statement_qa.qa import _NUMERIC_HINT

        text = (f"المجموع {REFUSED}" if any(h in asked for h in _NUMERIC_HINT)
                else f"الجواب رقم {len(self.calls)}")
        if "Answer" in self.bound:
            msg = AIMessage(content="", tool_calls=[{
                "name": "Answer", "id": f"c{len(self.calls)}",
                "args": {"answer": text, "cited_row_ids": [], "refused": False}}])
        else:
            msg = AIMessage(content=text)
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools, **kw):
        self.bound = [getattr(t, "name", None) or getattr(t, "__name__", None) for t in tools]
        return self

    @property
    def _llm_type(self):
        return "recorder"


def _text(m) -> str:
    return str(m.content) + json.dumps(getattr(m, "tool_calls", None) or [], ensure_ascii=False)


@pytest.fixture
def chat(request, monkeypatch):
    """زرُّ «اسأل» على حالة التطبيق — والنموذجُ مسجِّل، والاسترجاعُ قطعُ الكشف نفسُها."""
    from statement_qa import qa

    # **بالاسم لا بالمعامل:** الـ fixture مستوردةٌ في رأس الملف ليجدها pytest، ومعاملٌ بالاسم نفسه
    # يُعيد تعريفها فيوقفه حارسُ الأسماء (`redefinition of unused`) — فتُطلب هنا باسمها.
    app = request.getfixturevalue("read_sample")

    rec = _Recorder()
    monkeypatch.setattr(qa, "build_llm", lambda *_a, **_k: rec)
    monkeypatch.setattr(qa, "retrieve", lambda _s, _q, k=4: [
        {"chunk_id": c.chunk_id, "page": c.page, "row_start": c.start_row,
         "row_end": c.end_row, "text": c.text, "score": 0.0}
        for c in (app.STATE.get("chunks") or [])[:k]])
    app.STATE.setdefault("store", None)
    if hasattr(qa, "clear_conversation"):
        qa.clear_conversation(app._ledger_key())

    def ask(history, q):
        history, _ = app.prepare_ask(q, history)
        return app.ask_followup(history)[0]

    return app, rec, ask


def test_the_second_question_sees_the_first_turn_as_messages(chat) -> None:
    """**الدعوى الحاكمة (الشرط ١):** في السؤال الثاني يرى النموذجُ السؤالَ الأوّلَ **رسالةً بشريّة**
    وجوابَه **رسالةً من المساعد** — لا نصًّا داخل التعليمات."""
    _app, rec, ask = chat
    h = ask([], Q1)
    answer1 = h[-1]["content"]
    ask(h, Q2)
    seen = rec.calls[-1]
    humans = [str(m.content) for m in seen if m.type == "human"]
    system = "\n".join(str(m.content) for m in seen if m.type == "system")
    assert any(Q1 in t for t in humans[:-1]), "السؤالُ الأوّل لم يبلغ النموذجَ رسالةً"
    assert Q2 in humans[-1], "السؤالُ الحاليُّ ليس آخرَ رسالةٍ بشريّة"
    assert any(m.type == "ai" and "الجواب رقم 1" in _text(m) for m in seen), \
        f"جوابُ السؤال الأوّل لم يبلغ النموذجَ رسالةً (المعروض: {answer1[:40]})"
    assert Q1 not in system, "السجلُّ عاد نصًّا داخل التعليمات — والشرط ١: رسائلُ لا نصّ"


def test_a_new_read_starts_a_clean_conversation(chat) -> None:
    """**الشرط ٢ (R93-2):** نقرُ «اقرأ» على كشفٍ ⇒ المحادثةُ السابقةُ لا تبلغ النموذج."""
    app, rec, ask = chat
    ask([], Q1)
    app._reset_qa_surfaces()                     # الحدثُ الثاني على زرّ القراءة
    app._process_pdf_locked(str(SAMPLE), progress=lambda *_a, **_k: None)
    ask([], Q2)
    assert not any(Q1 in _text(m) for m in rec.calls[-1]), "سؤالُ القراءة السابقة بلغ النموذج"
