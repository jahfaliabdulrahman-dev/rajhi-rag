"""حَرَسُ القراءة المسقوفة — بلا شبكةٍ وبلا سنت (مراجعة ٨١ الطريق (ب) · مراجعة ٨٢).

**العقدُ المقيس هنا هو نصُّ قرار المالك، حرفيًّا:**
  · الطلبُ الأوّل **بلا حدّ** — كلُّ صفحةٍ تُقرأ أوّلًا كما تُقرأ اليوم، فلا يتغيّر ما شُهد له.
  · ومحاولةٌ **واحدة بالحدّ** — **فقط** بعد جوابٍ مقطوع.
  · **ولا طلبَ ثالث**: الانقطاعُ بعد المحاولة المسقوفة يظهر خطأً مسمًّى ويتوقّف.
  · و**كلُّ** محاولةٍ تُحسب كلفتُها في الدفتر (كانت الأخيرةُ وحدها).

الاستبدالُ هو أداةُ الحرَس: لا نداءَ حقيقيّ، فلا كلفةَ ولا مفتاحَ ولا شبكة.
(و`urllib` يُستبدَل في الوحدة التي تُنفِّذ النداء، لا في الاختبار نفسه.)
"""
import io
import json
import urllib.error
from typing import Any

import pytest

import statement_qa.vlm_reader as R


def _answer(finish, content, cost=0.0165, prompt=400):
    return {"choices": [{"finish_reason": finish, "message": {"content": content}}],
            "usage": {"completion_tokens": 3996, "cost": cost, "prompt_tokens": prompt}}


class _Sent(list):
    """النداءاتُ المُرسَلة فعلًا؛ و`feed` تُلقِّم التسلسلَ وتُثبّته في الوحدة."""

    monkeypatch: Any = None      # يضعها الضابطُ (الـfixture) في جهة الاختبار
    slept: Any = None            # أوقاتُ الانتظار المُقاسة (بلا نومٍ حقيقيّ)

    def __init__(self):
        super().__init__()
        self.slept = []

    def feed(self, seq):
        """يُثبّت ردودَ التسلسل ويُصفّر ما سُجِّل قبله."""
        self.clear()
        self.monkeypatch.setattr(R.urllib.request, "urlopen", self._wire(seq))

    def _wire(self, seq):
        it = iter(seq)

        def urlopen(req, timeout=None):
            item = next(it)
            self.append(json.loads(req.data.decode()))
            if isinstance(item, Exception):
                raise item
            return io.BytesIO(json.dumps(item).encode())

        return urlopen


@pytest.fixture
def calls(monkeypatch):
    """شبكةٌ مزيّفة: كلُّ نداءٍ يُسجَّل، ويُعاد عليه ما نصَّ عليه التسلسل."""
    sent = _Sent()
    sent.monkeypatch = monkeypatch
    monkeypatch.setattr(R.time, "sleep", sent.slept.append)   # تُقاس ولا تنام
    # مفتاحٌ مزيّف: بيئةُ الـCI بلا مفتاح، والبحثُ عنه كان يجده في ملفٍّ على جهاز المالك وحده
    # (فمرّ الضابطُ محلّيًّا وسقط على GitHub). ولا يُرسَل شيء: الشبكةُ مستبدَلة.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-real-key")
    return sent


def test_a_healthy_first_read_sends_no_reasoning(calls):
    """الصفحةُ التي تُقرأ اليوم بلا مشكلة يُرسَل لها الطلبُ نفسُه — بلا مفتاح سقف."""
    calls.feed([_answer("stop", "[]")])

    R.chat_vlm_image("b64", "q")

    assert len(calls) == 1
    assert "reasoning" not in calls[0]


def test_one_capped_attempt_after_a_cut_off_and_no_third(calls):
    """مقطوع ⇒ **محاولةٌ واحدة** بالحدّ؛ ومقطوعٌ ثانيةً ⇒ توقّفٌ بلا طلبٍ ثالث."""
    calls.feed([_answer("length", '{"rows"'),
                _answer("length", '{"rows"'),
                _answer("stop", "[]")])          # لا يُستهلك: لا طلبَ ثالث

    with pytest.raises(R.AnswerTruncated) as err:
        R.chat_vlm_image("b64", "q")

    assert len(calls) == 2, "لا طلبَ ثالث"
    assert sum(1 for c in calls if c.get("reasoning")) == 1, "سقفٌ واحدٌ لا أكثر"
    assert calls[0].get("reasoning") is None
    assert calls[1]["reasoning"] == {"effort": R.REASONING_RETRY_EFFORT}
    assert "max_tokens" not in calls[1]["reasoning"], "«not both» — effort وحدَه"
    assert "لا ثالثة" in str(err.value)       # الخطأُ مسمًّى بسببِه، لا بلفظٍ يتغيّر بتغيّر الصيغة


def test_the_capped_retry_returns_the_answer(calls):
    """المحاولةُ المسقوفةُ الواحدةُ قد تُنجح — والجوابُ يُعاد من غيرها."""
    calls.feed([_answer("length", '{"rows"'),
                _answer("stop", '[{"amount": "10.00"}]', 0.0155, 800)])

    out = R.chat_vlm_image("b64", "q", parse=R._rows_from_content)

    assert len(out) == 1
    assert calls[0].get("reasoning") is None
    assert calls[1]["reasoning"] == {"effort": R.REASONING_RETRY_EFFORT}


def test_a_network_error_does_not_buy_a_second_capped_attempt(calls):
    """**R83-1 (القانونُ المُحدَّث):** السقفُ يُنفَق **بنداءٍ أجاب**، لا بمجرّد إرسال — فخطأُ الشبكة
    يُعيد السقفَ في المحاولة التالية (وإلّا لقُرئت الصفحةُ بلا سقفٍ ووُصم السجلُّ بأنّه مسقوف)."""
    calls.feed([_answer("length", '{"rows"'),
                urllib.error.URLError("شبكة"),
                _answer("length", '{"rows"')])

    with pytest.raises(R.AnswerTruncated):
        R.chat_vlm_image("b64", "q")

    assert [bool(c.get("reasoning")) for c in calls] == [False, True, True], \
        "السقفُ يُعاد لأنّ نداءه لم يُجَب"


def test_every_attempt_is_priced_and_marked(calls):
    """الدفترُ يحمل **مجموع** المحاولات، والختمُ يعرف بالتفكير الذي قُرئ به."""
    stats = {}
    calls.feed([_answer("length", '{"rows"', 0.0165, 400),
                _answer("stop", "[]", 0.0155, 400)])

    R.chat_vlm_image("b64", "q", stats=stats)

    assert stats["cost"] == pytest.approx(0.032), "مجموعُ المحاولتين لا الأخيرة"
    assert stats["prompt_tokens"] == 800
    assert stats["request_calls"] == 2
    assert stats["reasoning"] == f"effort:{R.REASONING_RETRY_EFFORT}"


def test_a_network_error_does_not_spend_the_cap(calls):
    """R83-1: خطأُ شبكةٍ على الطلب المسقوف **لا يُستهلك السقفُ** — التاليةُ تحمله، والختمُ صادق."""
    calls.feed([_answer("length", '{"rows"', 0.0165),
                urllib.error.URLError("شبكة"),
                _answer("stop", '[{"amount": "1"}]', 0.005)])

    stats = {}
    out = R.chat_vlm_image("b64", "q", stats=stats, parse=R._rows_from_content)

    assert len(calls) == 3
    assert [bool(c.get("reasoning")) for c in calls] == [False, True, True], \
        "المسقوفةُ لم تُجَب ⇒ يُعاد السقفُ في التالية (لا تُنفَق على خطأ شبكة)"
    assert len(out) == 1
    assert stats["reasoning"] == f"effort:{R.REASONING_RETRY_EFFORT}"

def test_a_cut_off_after_an_unanswered_cap_is_named(calls):
    """«مقطوع · شبكة · مقطوع»: السقفُ أُجيب في الثالثة ⇒ الخطأُ باسمه ولا محاولةَ رابعة."""
    calls.feed([_answer("length", '{"rows"'),
                urllib.error.URLError("شبكة"),
                _answer("length", '{"rows"')])

    with pytest.raises(R.AnswerTruncated):
        R.chat_vlm_image("b64", "q")

    assert len(calls) == 3
    assert [bool(c.get("reasoning")) for c in calls] == [False, True, True]

def test_a_malformed_capped_answer_ends_the_read(calls):
    """**ما يعود به الجوابُ المسقوفُ يُنهي القراءة** (قرارُ المالك ٢ · R82-2 · مقعدُ المواصفة ٧):
    جوابٌ تالفٌ بعد السقف ⇒ خطأٌ مسمًّى، لا محاولةَ ثالثة."""
    calls.feed([_answer("length", '{"rows"'),
                _answer("stop", "ليس JSON")])

    with pytest.raises(RuntimeError) as err:
        R.chat_vlm_image("b64", "q", parse=R._rows_from_content)

    assert len(calls) == 2, "لا ثالثة: الجوابُ التالفُ بعد السقف يُنهي القراءة"
    assert not isinstance(err.value, R.AnswerTruncated), "مسمًّى بسببٍ آخر: تالفٌ لا مقطوع"
    assert sum(1 for c in calls if c.get("reasoning")) == 1

def test_an_empty_answer_takes_the_cut_off_path(calls):
    """الفارغُ يمضي في مسار القطع (قرارُ المالك ٢ · R82-4): محاولةٌ مسقوفةٌ واحدة ثمّ خطأٌ مسمّى."""
    calls.feed([_answer("stop", ""), _answer("stop", "")])

    with pytest.raises(R.AnswerTruncated):
        R.chat_vlm_image("b64", "q")

    assert len(calls) == 2
    assert calls[0].get("reasoning") is None
    assert calls[1]["reasoning"] == {"effort": R.REASONING_RETRY_EFFORT}

def test_a_cut_off_on_the_last_attempt_promises_nothing(calls):
    """قطعٌ في المحاولة الأخيرة (R82-3): **بلا انتظار**، والرسالةُ تصف ما وقع ولا تعد بإعادة."""
    calls.feed([_answer("stop", "ليس JSON"), _answer("stop", "ليس JSON"),
                _answer("stop", "ليس JSON"), _answer("length", '{"rows"')])

    with pytest.raises(RuntimeError) as err:
        R.chat_vlm_image("b64", "q", parse=R._rows_from_content)

    assert len(calls) == 4
    assert len(calls.slept) == 3, "ثلاثةُ انتظاراتٍ فقط: الأخيرةُ تُقطع فورًا"
    text = str(err.value)
    assert "المحاولةُ القادمة" not in text, "لا وعدَ بإعادةٍ لا تقع"
    assert "آخر محاولة" in text, "مسمًّى بموضعه: آخرُ محاولة (R83-5 — لا «VLM JSON»)"
