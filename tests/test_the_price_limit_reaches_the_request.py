"""**R117-1 — حدُّ السعر لا يخرج من العميل: يُقاس من الجسم المرسَل لا من الوسيط المُمرَّر.**

**العطبُ المقيس (مراجعة ١١٧ · P1 · بلا نموذجٍ حقيقيّ وبلا كلفة):** `build_llm` كان يضع
`provider.max_price` في `model_kwargs`، وهي بنصّ `langchain-openai` «معاملاتٌ صالحةٌ لِنداء `create`»
⇒ فتُفكّ **وسائطَ مسمّاةً** في `Completions.create()` من `openai` 3.13، وهذه لا تعرف `provider`
⇒ **`TypeError` قبل أيّ طلب**: قِيس **صفرُ طلبٍ** يصل خادمًا مُقلَّدًا، وأصبح كلُّ سؤالٍ يمرّ الحاجز
`<TypeError...>` في القياس (يُسجَّل «عطبٌ/مهلة» جوابًا خاطئًا) — والتطبيقُ لا يلفّه بـ`try` (`app.py`).

**والسببُ أنّ شيئًا لم يكن يقيس الوصل:** ضوابطُ الجولة تستبدل `build_llm` كلَّها وتقرأ **الوسيطَ
المُمرَّر** (`max_price=…`) لا **الجسمَ المرسَل** ⇒ فحذفُ السطر لم يُحرّك ضابطًا واحدًا.

**وهذا الضابطُ يقيس الوصلَ نفسه:** يبني `build_llm` الحقيقيّ (بمفتاحٍ مزيّفٍ لا يمسّ الجسمَ
المرسَل)،
ويُوقف النقلَ عند آخر طبقة (‏`httpx2.Client.send` — عميلُ `openai` 3.13) فيقرأ **الجسمَ المُسلسَل**
الذي كان سيمرّ على السلك، ويطلب `provider.max_price` في **كلّ** طلب — ومنه الطلبُ الحامل للأدوات.

**والضوابطُ لا تسحب مفتاحَ المالك (R118-3 · مراجعة ١١٨):** كانت سبعةُ ضوابط تبني `build_llm()`
بلا `api_key` ⇒ فتمرّ بمفتاح المالك من `~/.hermes/.env` وحدَه، وتسقط في بيتٍ نظيف. والآن كلُّ بناءٍ
هنا بمفتاحٍ مزيّف (`api_key="sk-test"`)، ومسارُ التطبيق بمفتاحٍ مزيّفٍ في البيئة.

**وموضعُ الحقن مقيس:** `openai` 3.13 يستورد `httpx2` (لا `httpx`) ⇒ فرقعةُ `httpx.Client.send`
لا تعترض شيئًا، والطلبُ الحقيقيّ يخرج فعلًا (قِيس: 401 من المزوّد بمفتاحٍ مزيّف). ولهذا يُفرقَع
`httpx2` ويُشترط أن يُلتقط طلبٌ واحد على الأقلّ: **صفرُ طلباتٍ ⇒ سقوطٌ مُسمّى** لا نجاحٌ صامت.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def _qa():
    """وحدةُ السؤال كما تُستورَد في بيئتها — والحدُّ المُعلَن: بلا عميلٍ حقيقيّ لا يُقاس وصل."""
    pytest.importorskip("httpx2", reason="عميلُ openai 3.13 غيرُ مركَّب في هذه البيئة (CI خفيف)")
    pytest.importorskip("openai", reason="بلا openai لا نداءَ يُقاس")
    pytest.importorskip("langchain_openai", reason="بلا langchain-openai لا ChatOpenAI يُبنى")

    from statement_qa import qa

    return qa


def _completion(request_body: dict) -> dict:
    return {
        "id": "chatcmpl-req117", "object": "chat.completion", "created": 0,
        "model": request_body.get("model", "m"),
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": "لا شيء"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@pytest.fixture
def sent(monkeypatch):
    """كلُّ جسمٍ أرسله العميل فعلاً — مُلتقَطًا عند آخر طبقةٍ قبل السلك (بلا شبكةٍ ولا كلفة)."""
    httpx2 = pytest.importorskip("httpx2")
    bodies: list[dict] = []

    def _send(self, request, *a, **k):
        bodies.append(json.loads(request.read().decode()))
        return httpx2.Response(200, json=_completion(bodies[-1]), request=request)

    monkeypatch.setattr(httpx2.Client, "send", _send)
    return bodies


# ── ① الحدُّ في الجسم المُرسَل (شكلُ نداء التطبيق: بلا وسائط) ──────────────────────────────
def test_the_limit_is_in_the_body_the_client_sends(sent):
    qa = _qa()
    qa.build_llm(api_key="sk-test").invoke("كم رصيد الصفحة ٥؟")
    assert len(sent) == 1, f"لم يُلتقط طلبٌ واحد ({len(sent)}) — والمسبارُ نفسه مشكوكٌ فيه"
    limit = sent[0].get("provider", {}).get("max_price")
    assert limit == dict(qa.PROVIDER_MAX_PRICE), (
        f"الحدُّ لم يصل في الجسم المُرسَل: {sent[0].get('provider')!r} "
        f"(المتوقَّع {qa.PROVIDER_MAX_PRICE})")


# ── ② الحدُّ في الطلب الحامل للأدوات (مسارُ الوكيل) ────────────────────────────────────────
def test_the_limit_rides_with_the_tool_carrying_request(sent):
    qa = _qa()
    llm = qa.build_llm(api_key="sk-test")
    llm.bind_tools([{"name": "page_rows", "description": "صفوفُ صفحة",
                     "parameters": {"type": "object",
                                    "properties": {"page": {"type": "integer"}}}}]).invoke(
        "ما حركات الصفحة ٣؟")
    assert len(sent) == 1, f"لم يُلتقط طلبُ الأداة ({len(sent)})"
    assert sent[0].get("tools"), "الطلبُ لم يحمل أدواتٍ — فالقياسُ على غير المسار المقصود"
    assert sent[0].get("provider", {}).get("max_price") == dict(qa.PROVIDER_MAX_PRICE), (
        "الحدُّ غائبٌ من الطلب الحامل للأدوات — وهو الطلبُ الذي يشتري التطبيقُ به")


# ── ③ النقيضُ: الحدُّ ليس في الخانة التي يرفضها العميل ─────────────────────────────────────
def test_the_limit_is_not_in_the_slot_the_client_rejects(sent):
    """**الموضعُ مُعلَنٌ لا مُستنتَج:** لو رجع الحدُّ إلى `model_kwargs` لسقط كلُّ نداءٍ
    بـ`TypeError` قبل الإرسال (قِيس على الرأس: صفرُ طلب). فالنقيضُ يُشترَط صراحةً مع الإثبات."""
    qa = _qa()
    llm = qa.build_llm(api_key="sk-test")
    assert "provider" not in dict(llm.model_kwargs), (
        "الحدُّ عاد إلى `model_kwargs` ⇒ كلُّ نداءٍ يسقط قبل الإرسال (R117-1)")
    assert dict(getattr(llm, "extra_body") or {}).get("provider", {}).get("max_price") == \
        dict(qa.PROVIDER_MAX_PRICE), "الحدُّ ليس في `extra_body` — الخانةُ الموثَّقة للمزوّد"


# ── ④ مسارُ التطبيق من طرفه: `answer_question(..., llm=None)` ─────────────────────────────
def test_the_app_path_carries_the_limit_end_to_end(sent, monkeypatch):
    """**المقيسُ مسارُ المستخدم نفسه:** `app.ask_followup` ينادي `answer_question` بلا `llm`
    ⇒ فيُبنى العميلُ داخل الوحدة. وكان هذا الطريق كله يسقط بـ`TypeError` قبل الإصلاح."""
    qa = _qa()
    from statement_qa.qa import answer_question

    # **والبيتُ مزيّف (R118-3 · مراجعة ١١٨):** مفتاحٌ مزيّفٌ في البيئة يُقرأ قبل ملفّات `.env`
    # (`get_api_key` يقرأ البيئة أوّلًا) ⇒ فالضابطُ لا يسحب مفتاحَ المالك ولا يعتمد على وجوده.
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    class _NoStore:
        def similarity_search_with_score(self, *_a, **_k):
            return []

    rows = [{"page": 1, "date": "2026-01-02", "movement": "100.00", "balance": "4,321.00",
             "side": "debit", "desc": "رسوم"}]
    answer_question(_NoStore(), "كم مجموع الحركات المدينة في الكشف؟", rows=rows)
    assert sent, "لم يُلتقط طلبٌ من مسار التطبيق"
    for body in sent:
        assert body.get("provider", {}).get("max_price") == dict(qa.PROVIDER_MAX_PRICE), (
            f"طلبٌ بلا حدّ سعرٍ في مسار التطبيق: {body.get('provider')!r}")
