"""**R117-3 · R117-8 — رفضُ المزوّد يُقرأ من نوعه، والمفتاحُ لا يُشترط بعَلَم.**

**العطبُ المقيس (مراجعة ١١٧ · P2 · بلا كلفة):** الكاشفُ كان **قائمةَ كلماتٍ على نصّ الخطأ**
(`"402"`, `"credit"`, `"insufficient"`, `"key limit"`, `"quota"`)، وقِيس على `main` بعميلٍ حقيقيّ
وردودٍ مُقلَّدةٍ بالشكل الموثَّق أنّه **يُخطئ شكلين**:

| الرفض | يُلتقط؟ | ما في الاستثناء |
| :--- | :--- | :--- |
| ٤٠٢ نفادُ رصيد | ✓ | `status_code=402` |
| ٤٠٣ حدُّ المفتاح (`limit_source = openrouter_key_limit`) | **✗** | `PermissionDeniedError` · `body.metadata.limit_source` |
| ٥٠٣ لا مضيفَ تحت الحدّ | **✗** | `InternalServerError` · `status_code=503` |

⇒ فما لا يُلتقَط **يُسجَّل جوابًا خاطئًا** بدل توقّفٍ مُسمّى. **و`render`/Gradio:** الرفضُ كان يصعد
استثناءً بلا رسالةٍ عربيّة. **والمفتاح:** كان `run_questions` يرفض غيابَه **فقط إن مُرِّر
`--budget`** ⇒ وبلاه يُبنى العميلُ بمفتاح **التطبيق** (قِيس: ٨/٨ سؤالًا طُرحت و`api_key=None`).

**ونصفا الضابط:** نصفٌ **خالصٌ** يعمل في أيّ بيئة (لا `openai` ولا `httpx2` ولا `langchain`)،
ونصفٌ **وظيفيّ** يبني العميلَ الحقيقيّ ويوقف النقلَ فيقرأ الشكلَ الموثَّق بعينه.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from statement_qa import provider_errors  # noqa: E402

#: الشكلُ الموثَّق لحدّ المفتاح (OpenRouter): الرمزُ في الحالة، والمصدرُ في `metadata`.
KEY_LIMIT_BODY = {"error": {"message": "Budget limit exceeded", "code": 403,
                            "metadata": {"limit_source": "openrouter_key_limit"}}}


class _Err(Exception):
    """استثناءٌ بشكل `openai.APIStatusError` — `status_code` و`body` (قِيس على المكتبة)."""

    def __init__(self, status, body=None, text=None):
        super().__init__(text or f"Error code: {status}")
        self.status_code = status
        self.body = body


def _eval():
    from tools import eval_questions

    return eval_questions


# ── ① الأصنافُ الموثَّقة تُسمّى من نوعها · وما ليس موثَّقًا لا يُبتلع ────────────────────────
def test_the_documented_shapes_are_named_by_their_type():
    assert provider_errors.classify(_Err(402)) == provider_errors.OUT_OF_CREDIT
    assert provider_errors.classify(_Err(403, KEY_LIMIT_BODY)) == provider_errors.KEY_LIMIT
    assert provider_errors.classify(_Err(503)) == provider_errors.NO_HOST_UNDER_PRICE


def test_a_403_is_named_by_its_limit_source_not_by_its_code():
    """**R118-4 · مراجعة ١١٨:** كانت **كلُّ** ٤٠٣ تُسمّى «حدَّ المفتاح» فيُقال للمستخدم
    «بلغ المفتاحُ حدَّ صرفه» على حجبِ حارسٍ أو نقصِ صلاحيّات — نصٌّ كاذبٌ في مسارٍ نادر.
    ووثائقُ OpenRouter: الميزانيّاتُ وحدَها تحمل `limit_source`."""
    assert provider_errors.classify(_Err(403, KEY_LIMIT_BODY)) == provider_errors.KEY_LIMIT
    guard = {"error": {"message": "Guardrail triggered", "code": 403,
                       "metadata": {"limit_source": "openrouter_guardrail_budget"}}}
    assert provider_errors.classify(_Err(403, guard)) == provider_errors.BUDGET_LIMIT
    assert provider_errors.classify(_Err(403)) == provider_errors.FORBIDDEN, \
        "٤٠٣ بلا `limit_source` تُسمّى حدَّ مفتاحٍ ⇒ ادّعاءُ حدِّ صرفٍ بلا سند"


def test_a_403_without_a_source_never_claims_a_spend_limit():
    """**القبولُ بنصّه:** ٤٠٣ رقابةٍ مُقلَّد ⇒ **لا تُذكر «حدَّ صرفه»**."""
    text = provider_errors.answer_text(provider_errors.FORBIDDEN, _Err(403))
    for claim in ("حدَّ صرفه", "ارفع حدَّ المفتاح", "رصيدَ المفتاح"):
        assert claim not in text, f"ادّعاءُ حدِّ صرفٍ في ٤٠٣ بلا `limit_source` ({claim}): {text}"
    assert "403" in text and "صلاحيّات" in text, "الرسالةُ لا تسمّي ما تعرفه (الرمزُ والاحتمال)"
    # **وميزانيّةُ الحارس تُسمّى بمصدرها** (لا بحدّ المفتاح):
    guard = {"error": {"message": "Guardrail triggered", "code": 403,
                       "metadata": {"limit_source": "openrouter_guardrail_budget"}}}
    gtext = provider_errors.answer_text(provider_errors.BUDGET_LIMIT, _Err(403, guard))
    assert "openrouter_guardrail_budget" in gtext, gtext
    for claim in ("حدَّ صرفه", "ارفع حدَّ المفتاح"):
        assert claim not in gtext, f"ميزانيّةُ الحارس تُقرأ حدَّ مفتاح: {gtext}"


def test_a_non_documented_failure_is_not_swallowed():
    """**ونقيضُه:** ما ليس رفضًا موثَّقًا **يُعاد رفعُه** ولا يُسمّى باسمٍ لا يخصّه."""
    assert provider_errors.classify(_Err(500)) is None
    assert provider_errors.classify(_Err(404)) is None
    assert provider_errors.classify(ValueError("402 credit quota")) is None, \
        "نصٌّ فيه كلماتُ القائمة القديمة لا يُصنَّف نوعًا (النقيضُ الذي يعضّ على الرجوع إليها)"


def test_the_limit_source_is_read_from_the_documented_place():
    err = _Err(403, KEY_LIMIT_BODY)
    assert provider_errors.limit_source(err) == "openrouter_key_limit"
    text = provider_errors.answer_text(provider_errors.KEY_LIMIT, err)
    assert "openrouter_key_limit" in text and "403" in text, "الرسالةُ لا تحمل المصدرَ المقيس"
    assert provider_errors.limit_source(_Err(403)) is None, "غيابُ المصدر لا يُخترع"


def test_the_source_is_found_wherever_the_metadata_sits():
    """**الشكلُ المقيس من المكتبة ليس الشكلَ المنشور:** عند ٤٠٣ حقيقيّة مرّت من `langchain-openai`
    كان الجسمُ **مسطّحًا** (`{'message':…, 'code':403, 'metadata':{'limit_source':…}}` بلا غلاف
    `error`) ⇒ فمسارٌ واحدٌ ثابتٌ (`body["error"]["metadata"]`) **يُخطئه**. قِيس على `main` `23f4e39`."""
    flat = {"message": "Budget limit exceeded", "code": 403,
            "metadata": {"limit_source": "openrouter_key_limit"}}
    nested = {"error": {"message": "Budget limit exceeded",
                        "metadata": {"limit_source": "openrouter_key_limit"}}}
    assert provider_errors.limit_source(_Err(403, flat)) == "openrouter_key_limit"
    assert provider_errors.limit_source(_Err(403, nested)) == "openrouter_key_limit"


def test_every_named_refusal_has_an_arabic_answer_with_no_library_text():
    for kind in provider_errors.PROVIDER_REFUSALS:
        text = provider_errors.answer_text(kind)
        assert text.strip() and any("\u0600" <= c <= "\u06FF" for c in text), \
            f"لا رسالةَ عربيّةً للصنف {kind}"
        for latin in ("TypeError", "APIStatusError", "status_code", "Error code"):
            assert latin not in text, f"نصُّ المكتبة ({latin}) ظاهرٌ للمستخدم في {kind}"


# ── ② الحكمُ في الحلقة من الحالة المُسمّاة (لا من نصّ) ─────────────────────────────────────
class _Res:
    def __init__(self, scope):
        self.scope = scope


def test_the_halt_is_named_from_the_state_or_the_type():
    ev = _eval()
    kinds = provider_errors.PROVIDER_REFUSALS
    assert ev.refusal_of({}, _Res(provider_errors.KEY_LIMIT), kinds) == provider_errors.KEY_LIMIT
    assert ev.refusal_of({"error_refusal": provider_errors.NO_HOST_UNDER_PRICE}, None, kinds) \
        == provider_errors.NO_HOST_UNDER_PRICE
    # **والنقيض:** نصُّ خطأٍ يشبه القائمة القديمة لا يُوقف الجولة
    assert ev.refusal_of({"error": "Error code: 402 - insufficient credit"}, None, kinds) is None
    assert ev.refusal_of({}, _Res("in_scope"), kinds) is None


def test_the_word_list_is_gone_and_the_loop_asks_the_named_state():
    """**الوصلُ مقروءٌ من الملفّ:** لا قائمةَ كلماتٍ تُطابَق، والحلقةُ تسأل الحالةَ المُسمّاة."""
    src = (_eval().__file__ and pathlib.Path(_eval().__file__).read_text(encoding="utf-8")) or ""
    for word in ("insufficient", "key limit", "quota"):
        assert word not in src, f"قائمةُ الكلمات باقيةٌ في الملفّ (`{word}`) — R117-3"
    assert "refusal_of(msg, res, provider_errors.PROVIDER_REFUSALS)" in src, \
        "الحلقةُ لا تسأل الحالةَ المُسمّاة ⇒ فالعطبُ يعود من بابٍ آخر"


# ── ③ المفتاحُ شرطٌ دائمٌ: بلا مفتاحٍ ⇒ صفرُ نداء ─────────────────────────────────────────
def test_without_the_eval_key_no_call_is_made_even_without_a_budget(monkeypatch):
    ev = _eval()
    monkeypatch.setattr(ev, "eval_key", lambda: None)          # المفتاحُ غائب، وبلا `--budget`
    from tools import refusal_test

    def _poison(*_a, **_k):                                    # سُمٌّ يُقاس: أيُّ عملٍ قبل الفحص يفشل
        raise AssertionError("شُغِّل عملٌ قبل فحص مفتاح القياس (R117-3)")

    monkeypatch.setattr(refusal_test, "build_rows", _poison)
    monkeypatch.setattr(refusal_test, "build_footers", _poison)

    class _Args:
        budget = None
        model = None
        out = None
        only = None

    rc = ev.run_questions(_Args(), [], None, {}, {})
    assert rc == 5, f"بلا مفتاحٍ ولا `--budget` يجب أن يتوقّف مُسمّى (5) — عاد {rc}"


# ── ④ الوصلُ الوظيفيّ: الشكلُ الموثَّق بعينه عبر النقل (بلا شبكةٍ ولا كلفة) ────────────────
def _transport(monkeypatch, status: int, body: dict):
    """يوقف النقلَ ويعيد الشكلَ الموثَّق — فيُقرأ ما كان سيمرّ، ولا يُشترى شيء."""
    httpx2 = pytest.importorskip("httpx2", reason="عميلُ openai 3.13 غيرُ مركَّبٍ في هذه البيئة")
    seen: list[dict] = []

    def _send(self, request, *a, **k):
        seen.append(json.loads(request.read().decode()))
        return httpx2.Response(status, json=body, request=request)

    monkeypatch.setattr(httpx2.Client, "send", _send)
    return seen


ROWS = [
    {"page": 1, "date": "2026-01-02", "movement": "100.00", "balance": "4,321.00",
     "side": "debit", "desc": "رسوم"},
    {"page": 1, "date": "2026-01-03", "movement": "50.00", "balance": "950.00",
     "side": "credit", "desc": "تحويل"},
]


@pytest.mark.parametrize("status,body,kind", [
    (402, {"error": {"message": "Insufficient credits", "code": 402}},
     provider_errors.OUT_OF_CREDIT),
    (403, KEY_LIMIT_BODY, provider_errors.KEY_LIMIT),
    (503, {"error": {"message": "No available model provider meets your routing requirements",
                     "code": 503}}, provider_errors.NO_HOST_UNDER_PRICE),
    (403, {"error": {"message": "Forbidden", "code": 403}}, provider_errors.FORBIDDEN),
    (403, {"error": {"message": "Guardrail triggered", "code": 403,
                     "metadata": {"limit_source": "openrouter_guardrail_budget"}}},
     provider_errors.BUDGET_LIMIT),
])
def test_the_app_path_names_the_refusal_instead_of_raising(monkeypatch, status, body, kind):
    """**مسارُ التطبيق نفسه** (`llm=None` ⇒ `build_llm()`): كان الاستثناءُ يصعد إلى Gradio،
    وكان القياسُ يسجّل السؤالَ جوابًا خاطئًا. والآن يعود **نتيجةٌ مُسمّاةٌ برسالةٍ عربيّة**.

    **والبيتُ مزيّف (R118-3):** مفتاحٌ مزيّفٌ في البيئة يُقرأ قبل ملفّات `.env` ⇒ فلا يسحب
    الضابطُ مفتاحَ المالك، ويمرّ في بيتٍ نظيف."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    pytest.importorskip("openai")
    pytest.importorskip("langchain_openai")
    seen = _transport(monkeypatch, status, body)
    from statement_qa.qa import answer_question

    class _NoStore:                     # لا فهرسَ هنا: المقيسُ هو الوصل إلى المزوّد لا الاسترجاع
        def similarity_search_with_score(self, *_a, **_k):
            return []

    res = answer_question(_NoStore(), "كم مجموع الحركات المدينة في الكشف؟", rows=ROWS)
    assert getattr(res, "scope", None) == kind, (
        f"الحالةُ ليست مُسمّاة: scope={getattr(res, 'scope', None)!r} — R117-3")
    assert res.answer.strip(), "لا جوابَ عربيّ للمستخدم"
    assert "Error code" not in res.answer and "APIStatus" not in res.answer, \
        "نصُّ المكتبة ظاهرٌ للمستخدم"
    assert seen, "لم يُلتقط طلبٌ — والمسبارُ نفسه مشكوكٌ فيه"
    assert len(seen) <= 2, f"أُعيد النداءُ بعد رفضٍ مُسمّى ({len(seen)} طلبات) — R117-3"


def test_the_real_library_exception_carries_what_the_classifier_reads(monkeypatch):
    """**عقدُ المكتبة مقيس:** `openai.APIStatusError` يحمل `status_code` و`body` — والوارثُ في
    `langchain-openai` يرثهما (`OpenAIPermissionDeniedError` لـ٤٠٣ · `OpenAIAPIError` لـ٥٠٣)."""
    openai = pytest.importorskip("openai")
    httpx2 = pytest.importorskip("httpx2")
    req = httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    resp = httpx2.Response(403, json=KEY_LIMIT_BODY, request=req)
    err = openai.PermissionDeniedError("Budget limit exceeded", response=resp, body=KEY_LIMIT_BODY)
    assert provider_errors.status_code(err) == 403
    assert provider_errors.limit_source(err) == "openrouter_key_limit"
    assert provider_errors.classify(err) == provider_errors.KEY_LIMIT
