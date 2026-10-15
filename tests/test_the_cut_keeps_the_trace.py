"""**R124-1 (P2 · مراجعة ١٢٤) — القطعُ عند حدّ الرموز حالةٌ مُسمّاة، وما حسبته الأدواتُ لا يُمحى.**

**المقيس (من الخمسين ومن سابقتها):** ثلاثةُ ردودٍ انتهت بـ`length` في ٥٠+٥٠ (`cit-02` في r108-03 ·
و`cit-02` و`abs-05` في r123) ⇒ وسقط المسارُ إلى `_answer_plain` **فصفّر `used` و`tools_used`** وإن
كانت الأدواتُ نُوديت فعلًا (`cit-02`: نداءان) ⇒ **فجوابٌ نثريٌّ تحت لافتة «تعذّرت الأدوات» ولوحةُ
أدلّةٍ فارغة، وضاع حسابٌ وقع.**

**والثوابتُ الثلاثة:** ① القطعُ حالةٌ مُسمّاةٌ لا سقوطٌ صامتٌ، وما حُسب قبله يبقى في الأثر ·
② ميزانيّةُ الاستدلال تُضبط بخيار المزوّد في جسم الطلب (كما `max_price`) — والضابطُ يعيش في
`tests/test_the_price_limit_reaches_the_request.py` ⑤ — · ③ القبول: ردٌّ مُقلَّدٌ ينتهي بـ`length`
بعد نداء أداة ⇒ الأثرُ محفوظ والحالةُ مُسمّاةٌ والجوابُ لا يُعرض حسابًا كاملًا.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from statement_qa import qa  # noqa: E402


class _LLM:
    """نموذجٌ مُقلَّد: `_answer_plain` تنادي `invoke` ⇒ فنُعيد نصًّا بلا نداءِ شبكة."""

    def invoke(self, messages):                       # noqa: ANN001, D102
        class _M:
            content = "نصٌّ نثريٌّ بعد القطع"

        return _M()


def _answer_one(monkeypatch, *, trace, finish, answer=""):
    """يشغّل `_answer_one` بأثرٍ مُصنَّعٍ وبأسبابِ انتهاءٍ معلَنة — بلا نموذجٍ ولا شبكة."""
    monkeypatch.setattr(qa, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(qa, "pages_for", lambda *a, **k: None)
    monkeypatch.setattr(qa, "_answer_with_tools",
                        lambda *a, **k: (answer, list(trace), None, "prose", list(finish)))
    from statement_qa import qa_tools

    monkeypatch.setattr(qa_tools, "citation_truth",
                        lambda cited, trace_rows: {"cited": [], "unsupported": []})
    rows = [{"row_no": 1, "page": 1, "text": "س"}]
    return qa._answer_one(store=object(), question="ما حركات الصفحة ٣؟", rows=rows, chunks=None,
                          llm=_LLM(), k=6, footers=None, thread_id=None, scope="")


TOOL_CALL = {"tool": "page_rows", "args": {"page": 3}, "row_nos": [3, 4]}


def test_a_cut_reply_keeps_what_the_tools_computed(monkeypatch):
    """**القبولُ بنصّه:** ردٌّ ينتهي بـ`length` **بعد نداء أداة** ⇒ **الأثرُ محفوظ**، **والحالةُ
    مُسمّاة**، والجوابُ لا يُعرض حسابًا كاملًا (اللافتةُ في طبقة العرض، لا في نصّ الجواب)."""
    res = _answer_one(monkeypatch, trace=[TOOL_CALL], finish=["tool_calls", "length"])
    assert res.used_row_nos == [3, 4], f"أثرُ الأدوات مُحي: {res.used_row_nos}"
    assert res.tools_used == ["page_rows"], f"أسماءُ الأدوات مُحيت: {res.tools_used}"
    assert res.truncated is True, "القطعُ لم يُسمَّ حالةً"
    assert res.limit_hit is False and res.tools_failed is False, (res.limit_hit, res.tools_failed)
    # **والنصُّ نظيفٌ في السجلّ:** اللافتةُ تُعرض ولا تُطبع في الجواب (فلا تتلوّث بصمةُ نصّ)
    assert res.answer == "نصٌّ نثريٌّ بعد القطع", res.answer
    assert res.answer_kind == "", "أُعلنت إشارةٌ لجوابٍ لم يُعلنها"


def test_a_fallback_with_nothing_computed_still_wipes(monkeypatch):
    """**والنقيضُ محفوظٌ كما كان:** سقوطٌ بلا قطعٍ ولا حسابٍ (مهلةُ مزوّد · عطبٌ) ⇒ الأثرُ فارغ
    بالبناء (قاعدةُ «من لا أثرَ له لا نوعَ له») — فلا يُخلط الإصلاحُ بحالةٍ أخرى."""
    res = _answer_one(monkeypatch, trace=[], finish=[])
    assert res.truncated is False and res.used_row_nos == [] and res.tools_used == []


def test_the_specific_banner_shows_alone():
    """**والحالةُ المُسمّاةُ تُعرض وحدَها** (سابقةُ `limit_hit` · R111-1): لافتةُ القطع تقول الحالتين
    معًا (حسابٌ وقع · جوابٌ ناقص)، فلا تُقرأ تحت «تعذّرت الأدوات» ولا «حدَّ الخطوات» — وكلاهما لا
    يصف الحال، واللافتةُ الأخصُّ تُرجَع فورًا."""
    from statement_qa import render

    res = qa.QAResult(answer="نصٌّ ناقص", sources=[], truncated=True, tools_failed=True,
                      limit_hit=True)
    text = render.answer_text(res, page_of={}, verdicts={})
    assert "قُطع ردُّ النموذج" in text, text[:150]
    assert "حدَّ الخطوات" not in text and "تعذّرت الأدوات" not in text, text[:200]
    assert "نصٌّ ناقص" in text, "الجوابُ نفسه غاب عن العرض"


def test_the_truncation_is_read_from_the_finish_reason(monkeypatch):
    """**والقطعُ يُقرأ من سبب الانتهاء لا من نصّ الرسالة** (R124-1 · الثابت ①): رسالةٌ تحمل
    `response_metadata.finish_reason = 'length'` ⇒ تُسمّى، والنوعُ نصّيٌّ (`prose`)."""
    import langchain.agents as la

    class _Msg:
        content = ""

        def __init__(self, fr):
            self.response_metadata = {"finish_reason": fr}

    class _Agent:
        def invoke(self, *_a, **_k):
            return {"messages": [_Msg("tool_calls"), _Msg("length")]}

    monkeypatch.setattr(la, "create_agent", lambda **kw: _Agent())
    finish: list[str] = []
    text, parsed, mode = qa._run_agent(object(), [], "نظام", "سؤال", response_format=qa.Answer,
                                       finish=finish)
    assert finish == ["tool_calls", "length"], finish
    assert text == "" and parsed is None and mode == "prose", (text, parsed, mode)
