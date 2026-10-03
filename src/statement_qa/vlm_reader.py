"""VLM-assisted row reader (OpenRouter gemini-3.7-flash).

v2 — INHERITS THE FROZEN PROMPT SET from the 629-page case
(src/statement_qa/legacy/prompts.py, owner directive: "العلم تراكمي").
Chain-derived architecture (validated on real page 5 — 8/10 exact):
- VLM transcribes printed numbers EXACTLY (Arabic-Indic, ٬ thousands,
  . 00 halalas) — tesseract garbles dense-table digits (skill lesson 6).
- The BALANCE CHAIN derives the true movement: mv[i] = bal[i] − bal[i−1];
  the VLM movement token is only a cross-check (side included).
- VLM rows that fail the chain → suspect → targeted re-read (not silent).

Chain-index rule (legacy lesson 3): balance prints AFTER the transaction —
amt[i+1] == bal[i] − bal[i+1]. Single-key discipline (legacy lesson 10):
one stream, retry with backoff, JSON-parse gate separate from rate-limit
retries.
"""

from __future__ import annotations

import base64
import http.client
import json
import os
import re
import time
import urllib.error
import urllib.request
from decimal import Decimal

from statement_qa.legacy.prompts import (  # noqa: E402
    FRONTIER_PROMPT, FRONTIER_PROMPT_V2, TOP_BAND_PROMPT,
)
from statement_qa.legacy.arabic_digit_parser import norm_num as _legacy_norm_num
from statement_qa.api_key import get_api_key

MODEL = os.environ.get("OPENROUTER_MODEL_VLM", "google/gemini-3.7-flash")

# Prompts available to callers: v2 (default) reads the printed column as a second
# witness; v1 is the frozen 629-page prompt, kept for comparison runs
# (`read_rows_vlm(path, prompt=PROMPTS["v1"])`).
PROMPTS = {"v2": FRONTIER_PROMPT_V2, "v1": FRONTIER_PROMPT}


def reader_stamp(prompt: str | None = None, *, reader: str = "vlm",
                 version: str | None = None) -> dict:
    """هوية القارئ الفعلية: النموذج والتلقينة اللذان أنتجا هذه القراءة.

    سببه حادثة مسجَّلة (FMEA FM-1): كوربوسٌ واحد قد يُبنى بقارئين مختلفين
    فيُجمَع تحت رقمٍ واحد، ولا شيء في نقطة الفحص يقول بأيّهما قُرئ. فالختم
    يُكتب مع كل قراءة، ويُقارَن عند الاستئناف. والتلقينة المجهولة تُختم
    ببصمتها لا باسمٍ عام.

    والقارئ الحتميّ (نصّ رقميّ بلا نموذج) يُختم `deterministic` ونسخته —
    فالمقارنة تبقى ممكنة مع بقية الكوربوس بلا اسم نموذجٍ لا وجود له.
    """
    import hashlib

    if reader == "text":
        return {"model": "deterministic", "prompt_version": version or "text-v1"}
    if prompt is None or prompt is FRONTIER_PROMPT_V2:
        name, text = "v2", FRONTIER_PROMPT_V2
    elif prompt is FRONTIER_PROMPT:
        name, text = "v1", FRONTIER_PROMPT
    else:
        name, text = "custom", prompt
    # **والختمُ من نصّ التعليمات لا من اسمٍ ثابت (R74-5 · قاسه المدقّق):** تعليمةٌ «مجمّدة» عُدِّلت في
    # 2026-09-19 وبقي ختمُها «v2» اسمًا ثابتًا ⇒ لم يكشف التعديلَ شيء، ولا الاستئنافُ رفض المقروءَ بها.
    # الآن حرفٌ واحدٌ يتغيّر ⇒ يتغيّر الختمُ ⇒ يُبطل الاستئنافَ ويُعلن نفسَه.
    version = f"{name}:{hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]}"
    return {"model": MODEL, "prompt_version": version}


def stamp_conflict(cached: dict | None, current: dict) -> str | None:
    """يُقارن ختم نقطة فحص بختم القارئ الحالي ⇒ سببُ رفضِ الاستئناف أو None.

    ولا يُعاد دفع ثمن صفحةٍ قديمة بلا ختم: ذلك يُعلن بالعدّ (`plain_legacy`)
    لأنّ الكوربوس القائم (629 صفحة) قُرئ قبل وجود الختم، وإعادةُ دفعه إتلافٌ
    لا إصلاح.
    """
    if not cached:
        return "checkpoint-unreadable"
    have_m, have_p = cached.get("model"), cached.get("prompt_version")
    if not have_m and not have_p:
        return "plain_legacy"
    if have_m != current["model"] or have_p != current["prompt_version"]:
        return (f"stamp-mismatch: cached={have_m}/{have_p} "
                f"current={current['model']}/{current['prompt_version']}")
    return None
# Response-level blips (RemoteDisconnected et al.) once killed whole runs —
# they now retry like any network error. 4 attempts: 10s/20s/40s backoff.
_ATTEMPTS = 4


def _api_key() -> str:
    """Resolution lives in one place — statement_qa.api_key."""
    return get_api_key()


def _parse_amount(tok: str | None) -> Decimal | None:
    """Printed Arabic-Indic money token -> Decimal (Western digits, dot halalas).

    DELEGATES to the proven legacy parser (629-page case) — it owns the full
    separator zoo: '٣٠٠,٠٠' -> 300.00 (comma is the decimal point on old
    prints), '.,..' -> 0.00 (printed zero), '٦١,١٦٥١٢' -> 61165.12 (lost
    dot), '١١٩.٠٠-' -> -119.00 (trailing minus). A local re-implementation
    once regressed all four of these at once — never re-implement; inherit.
    """
    if not tok:
        return None
    v = _legacy_norm_num(tok)
    if v is None:
        return None
    # money is 2dp forever: Decimal('300.0') would display as '300.0' —
    # quantize keeps the halala scale so every display/format shows 300.00
    return Decimal(str(v)).quantize(Decimal("0.01"))


def _extract_json(content: str):
    """Pull the JSON payload out of a VLM answer.

    VLMs occasionally emit slightly malformed JSON (stray commas, truncation).
    Repair what is safely repairable; anything else raises so the caller's
    retry loop re-rolls the call instead of crashing the whole run.
    """
    m = re.search(r"[\[{].*[\]}]", content, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON in VLM answer: {content[:120]}")
    text = m.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = re.sub(r",\s*([\]}])", r"\1", text)  # trailing commas
        return json.loads(repaired)


class AnswerTruncated(RuntimeError):
    """جوابٌ قطعَه المزوّد عند حدّ الرموز — **ولا يُعاد المحاولة**.

    **ولماذا لا يُعاد (توجيهُ المالك 2026-10-02 · الخيار الأول):** كان `finish_reason: "length"` يُصنَّف
    عارضًا فيُعاد النداء، **وقِيس أنّه حتميٌّ على صفحاتٍ بعينها**: الصفحة ٣١٣ استهلكت **٣٩٩٦ من ٤٠٠٠**
    عند حدّ ٤٠٠٠، و**٧٩٩٦ من ٨٠٠٠** عند حدّ ٨٠٠٠ ⇒ فرفعُ الحدّ لا يُصلح، **وكلُّ إعادةٍ تدفع ثمنَ
    الفشل نفسِه** (محاولةٌ سابقة على ٣١٣ = أربعةُ نداءاتٍ بـ$0.0165 لكلٍّ منها).
    ولا يُلتقط في `except (json.JSONDecodeError, ValueError)`: الإرثُ من `RuntimeError` يُخرجه من
    حلقة الإعادة، ويسمّيه للمالك بدل أن يُخفيَه في «تعذّرت المحاولات».
    """


# ————— سقفُ التفكير — **عند الحاجة وحدها** (قرارُ المالك في مراجعة ٨١ · الطريقُ (ب)) —————
# **وصُحِّح قتبسٌ خاطئ كان هنا (R81-1 · P1):** كتبتُ أنّ `effort` يُضبط «مع الميزانية، فلا يكفي
# أحدُهما» — **والوثيقةُ نفسُها تمنع الجمع**: معاملاتُ `reasoning` تقول نصًّا: **«One of the following
# (not both)»**. وتقول أيضًا: «OpenRouter maps the `reasoning.effort` parameter directly to Google's
# `thinkingLevel` values» ⇒ فـ`effort` وحدَه هو الضابطُ الموثَّق لمستويات تفكير Gemini 3، **ولا
# `max_tokens` معه**. وشرطُ «`max_tokens` يجب أن يبقى أعلى من ميزانية التفكير» يخصّ `reasoning.max_tokens`
# — ولا محلَّ له هنا ما دام `effort` هو المُرسَل.
# **ونطاقُ الحدّ بقرار المالك:** القراءةُ الأولى لكلّ صفحة تبقى **بالتفكير الافتراضيّ** — فلا يُمسّ ما
# شُهد له (البوّابة ٥/٥ · الفوتر ١٠/١٠) ولا تعود خليّةُ التأهيل إلى «قيد إعادة التأهيل» — **والحدُّ
# **والقانونُ المقيسُ صار: «جوابٌ مسقوفٌ واحد» لا «إرسالٌ واحد» (R83-1 · R84-2):** الإرسالُ
# يتكرّر إن لم يُجَب الطلبُ المسقوف (خطأُ شبكةٍ أو 429)، **والاستحقاقُ لا يُستهلك إلا بجواب**. فالوصفُ
# «في محاولةٍ ثانيةٍ واحدة» كان يخالف الكود بعد إصلاح R83-1 — والمقيس: يُرسَل حتى ثلاثِ مرّات.**
REASONING_RETRY_EFFORT = "low"    # يُسجَّل مع القراءة (R81-3) — **والقانون: جوابٌ مسقوفٌ واحد** (R83-1 · R84-2)


def reasoning_mark(*stats: dict | None) -> str | None:
    """ما استُعمل من إعداد التفكير في قراءاتٍ هذه الصفحة — **بصيغةٍ واحدة** (§R81-3 · R83-2).

    كان سجلُّ الصفحة يُختم من **قراءة الصفوف وحدها**، وفي السجلّ نفسِه قراءاتٌ أخرى قد تُسقَف
    فتُترك بلا ختم: **قراءةُ التذييل** (تُقرأ مرّتين على الصفحتين لأوّل مرّة) وإعادةُ القراءة/المرساة.
    فصار المصدرُ دالّةً واحدة: تُسمّى القراءاتُ المسقوفةُ باسمها بعد الإعداد، **وغيابُ الختم يعني أنّ
    قراءةً ما في هذا السجلّ لم تُسقَف** — فلا يُضاف مفتاحٌ لسجلّ قراءةٍ افتراضيّة.

    `rows` فقط ⇒ `effort:low` (كما كانت، فلا يتغيّر سجلُّ اليوم) · ومعها غيرُها ⇒ `effort:low (footer)`
    · وخانةُ إعادة القراءة/المرساة اسمها **`anchor`** لا `reread` (R83-2: هي مرساةٌ حدّيةٌ تُقرأ ثانيةً).
    """
    named = tuple(zip(("rows", "footer", "anchor"), stats))
    capped = [name for name, st in named if (st or {}).get("reasoning")]
    if not capped:
        return None
    if capped == ["rows"]:
        return f"effort:{REASONING_RETRY_EFFORT}"
    return f"effort:{REASONING_RETRY_EFFORT} ({','.join(capped)})"


def chat_vlm_image(image_b64: str | list[str], prompt: str,
                   max_tokens: int = 4000, stats: dict | None = None,
                   parse=None):
    """One prompt + one-or-more images -> parsed answer. THE single transport.

    Every vision call (row read, footer oracle, bank probe) goes through here,
    so retry semantics stay identical everywhere: 4 attempts, 10/20/40s
    backoff, ConnectionError family + HTTPException caught (the
    RemoteDisconnected regression), 429 handled separately.

    When `parse` is given it runs INSIDE the retry loop: a malformed answer
    (bad JSON / no JSON at all) re-rolls the call exactly like a network blip
    — the JSON glitch that once killed whole runs stays dead.

    When `stats` is a dict, the API `usage` object (tokens + cost) is merged
    into it — the measured cost/time evidence for scale slices.
    """
    images = [image_b64] if isinstance(image_b64, str) else list(image_b64)
    base_payload = {
        "model": MODEL,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content":
                      [{"type": "text", "text": prompt}] +
                      [{"type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b}"}}
                       for b in images]}],
    }
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"}
    delay = 10
    last_error: Exception | None = None
    # **نطاقُ الحدّ — قرارُ المالك (ب) في مراجعة ٨١:** القراءةُ الأولى **بالتفكير الافتراضيّ كما هي
    # اليوم** (فلا يُمسّ ما شُهد له)، **والسقفُ يُرسَل بعد قطعٍ أو فراغ، ولا يُستهلك إلا بجوابٍ مسقوف**
    # (R83-1) — فقد يُرسَل أكثرَ من مرّة، **والقانونُ: جوابٌ مسقوفٌ واحد** (R84-2).
    #
    # **ودرسُ مقعد الهيكل (مراجعة ٨٢ · الحاجز ١) مُذابٌ هنا:** كان فرعُ القطع يُعيد تنفيذَ بروتوكول
    # الإعادة يدويًّا (نومٌ وتراجعٌ و`continue`) ⇒ **نسخةً خامسةً** له، **وثلاثةَ حقولِ حالةٍ لمفهومٍ
    # واحد**، **ووعدًا في `last_error` لا يقع** (يُكتب في المحاولة الأخيرة ثمّ لا محاولةَ بعده). فصار:
    # القطعُ والفارغُ **يُرمَيان استثناءً قابلًا للإعادة** فيلتقطه المعالجُ القائم ⇒ **مسارٌ واحد**،
    # **وحقلان صريحان** (`cap_owed` / `cap_answered`) لا ثلاثةٌ ضمنيّة، والنصُّ يصف ما وقع لا ما سيقع.
    # **والسقفُ «مستحقٌّ» حتى يُجيب نداءٌ يحمله (مراجعة ٨٣ · R83-1):** كان يُعدّ مُرسَلًا بمجرّد إرساله،
    # فإن انقطع الاتّصالُ أو ردّ المزوّد بـ429 بعد الطلب المسقوف، ذهبت المحاولةُ التالية **بلا سقف**
    # ⇒ صفوفٌ من قراءةٍ كاملة وسجلٌّ مكتوبٌ عليه `effort:low`، وحكمٌ على سقفٍ **لم يُجَب** («لم يُجدِ»
    # وهو لم يُقَرأ أصلًا) — وعلى ٣١٣ يعني شراءَ فشلٍ معروف. فصار الاستحقاقُ لا يسقط إلا بنداءٍ مسقوفٍ
    # **أجاب**، والختمُ يُكتب عند الجواب لا عند الإرسال.
    cap_owed = False           # يجب إرسالُ السقف في المحاولة القادمة
    cap_answered = False       # أُجيب نداءٌ بالسقف ⇒ استُهلك الاستحقاقُ وصار الختمُ صادقًا
    for attempt in range(_ATTEMPTS):
        payload = dict(base_payload)
        capped_now = cap_owed and not cap_answered
        if capped_now:
            # `effort` **وحدَه** — والوثيقةُ تقول «One of the following (not both)» (R81-1)
            payload["reasoning"] = {"effort": REASONING_RETRY_EFFORT}
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers=headers)
        if stats is not None:
            # Every attempt IS one HTTP request. The ledger's `calls` counts
            # pages (one read), so it under-reported the real request count by
            # ~2x — and that wrong number reached a handoff message (audit P2-2).
            stats["request_calls"] = int(stats.get("request_calls") or 0) + 1
            # **R81-3 + R83-1:** الختمُ يُكتب **عند الجواب** لا عند الإرسال — فنداءٌ مسقوفٌ أخفق
            # (شبكةٌ أو 429) لا يُختم سجلُّه، والختمُ يقع في الفرع الذي يستقبل الردَّ أدناه.
        try:
            out = json.loads(urllib.request.urlopen(req, timeout=180).read().decode())
            if stats is not None and isinstance(out.get("usage"), dict):
                # **كلفةُ كلّ محاولةٍ تُجمَع (مراجعة ٨٢ · البند ٢):** كان `stats.update(...)` **يستبدل**
                # كتلةَ الاستهلاك بكتلة **آخر ردّ** ⇒ ثمنُ كلّ محاولةٍ سابقة يُهدَر. وقِيس في المحاكاة
                # قبل الإصلاح: `cost` = الأخيرة وحدها. فيُجمَع كلُّ مفتاحٍ رقميّ هنا؛ **وترشيحُها إلى
                # دفتر الكلفة يبقى في موضعه الواحد** (`tools/scale_slice.py::_sum_dicts`) — ويُنبَّه:
                # مفتاحٌ يُجمَع هنا ثمّ يُرشَّح هناك صامتًا هو عطبُ «ختمٍ يموت عند الحفظ» (مقعدُ المعايير ٣).
                for _k, _v in out["usage"].items():
                    # **والعدُّ يبقى عددًا صحيحًا إن كان كذلك (مراجعة ٨٣ · R83-6):** الجمعُ بـ`float`
                    # جعل كلَّ سجلٍّ جديد يكتب الرموزَ `2468.0` بينما الأصلُ `2468` ⇒ تغييرٌ في صيغة
                    # سجلٍّ حيٌّ بلا سبب. فيُحفظ النوعُ، والكسرُ يُقرَّب عند الكسور وحدها.
                    if isinstance(_v, (int, float)) and not isinstance(_v, bool):
                        _sum = float(stats.get(_k) or 0) + _v
                        stats[_k] = int(_sum) if _sum.is_integer() else round(_sum, 6)
            choice = (out.get("choices") or [{}])[0] or {}
            content = (choice.get("message") or {}).get("content")
            # **أُجيبَ النداءُ (ولو بجوابٍ غيرِ صالح) ⇒ استحقاقُ السقف يُستهلَك والختمُ يصير صادقًا**
            # (R83-1): فيُعلَن هنا، في موضع استقبال الردّ — لا عند الإرسال.
            if capped_now:
                cap_answered = True
                if stats is not None:
                    stats["reasoning"] = f"effort:{REASONING_RETRY_EFFORT}"
            # **ما يُنهي القراءة: قطعٌ أو فارغ** (قرارُ المالك ٢ · R82-4). والقطعُ **حتميٌّ** على صفحاتٍ
            # بعينها (قِيس: ٣٩٩٦ من ٤٠٠٠ ثمّ ٧٩٩٦ من ٨٠٠٠) ⇒ فلا يُعاد شراءُ الفشل نفسِه: إن كان السقفُ
            # قد أُرسل فعلًا، خرج الخطأُ المسمّى **فورًا وبلا انتظار**؛ وإن لم يُرسَل، أُشعِل للأتى ثمّ
            # رُمي **قابلًا للإعادة** فيلتقطه المعالجُ القائم (نفسُ التصنيف ونفسُ التراجع، مسارٌ واحد).
            finish = choice.get("finish_reason")
            if finish == "length" or not str(content or "").strip():
                why = "بلغ حدَّ الرموز" if finish == "length" else "أعاد محتوى فارغًا"
                if cap_answered or attempt == _ATTEMPTS - 1:
                    # سقفٌ **أُجيب** ولم يُجدِ، أو **آخرُ محاولة** ⇒ الخطأُ باسمه **فورًا** (R83-5):
                    # `AnswerTruncated` لا `VLM JSON`، وبلا انتظارٍ وبلا إعادة.
                    detail = (f" — وقد أُرسل السقفُ (`reasoning.effort={REASONING_RETRY_EFFORT}`) "
                              "وأُجيب، ولم يُجدِ ⇒ **لا ثالثة**"
                              if cap_answered else
                              " في **آخر محاولة** — فلا محاولةَ تُرسَل بعدها")
                    raise AnswerTruncated(
                        f"الجوابُ غيرُ صالح: المزوّدُ {why}{detail}: كلُّ إعادةٍ تدفع ثمنَ الفشل "
                        "نفسِه. يُخفض المطلوبُ من الصفحة أو تُقسَّم القراءةُ، ويُعرض على المالك باسمه")
                cap_owed = True
                raise ValueError(f"VLM unusable answer: المزوّدُ {why}")
            return parse(content) if parse else content
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < _ATTEMPTS - 1:
                time.sleep(delay); delay *= 2
                continue
            raise RuntimeError(f"VLM HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError,
                http.client.HTTPException) as e:
            if attempt < _ATTEMPTS - 1:
                time.sleep(delay); delay *= 2
                continue
            raise RuntimeError(f"VLM network: {e}") from e
        except (json.JSONDecodeError, ValueError) as e:
            # الجوابُ الفارغُ والقطعُ يمرّان من هنا **قبل** إرسال السقف، فيُعادان **مرّةً واحدة**؛
            # وبعد إرسال السقف يخرج `AnswerTruncated` من الفرع أعلاه (وهو `RuntimeError` فلا يمرّ من هنا).
            last_error = e
            # **وما يعود به الجوابُ المسقوفُ يُنهي القراءة (R82-2 · ومقعدُ المواصفة ٧):** إن كان
            # المزوّدُ قد أُرسل إليه السقفُ فعاد بجوابٍ **تالف** (لا مقطوعًا ولا فارغًا — فهذان خرجا من
            # الفرع أعلاه)، فلا محاولةَ ثالثة: خطأٌ مسمًّى بسببٍ من نوعه، **بلا انتظار**.
            if cap_answered:
                raise RuntimeError(f"VLM JSON: {e}") from e
            if attempt < _ATTEMPTS - 1:
                time.sleep(delay); delay *= 2
                continue
            raise RuntimeError(f"VLM JSON: {e}") from e
    # The cause is named, not swallowed: «retries exhausted» alone told nobody
    # whether the provider was down, the JSON was malformed, or the answer came
    # back empty (each needs a different response).
    raise RuntimeError(
        f"VLM retries exhausted — استُنفدت الإعاداتُ ({_ATTEMPTS}) دون جوابٍ صالح؛ "
        f"آخرُ سبب: {last_error}. ولا إعادةَ بعدها: تُعرض على المالك باسمها")



def _rows_from_content(content: str) -> list[dict]:
    """Raw answer text -> row dicts (runs inside the retry loop)."""
    data = _extract_json(content)
    vlm_rows = data if isinstance(data, list) else data.get("rows", [])
    rows = []
    for r in vlm_rows:
        raw_mv = r.get("amount") or r.get("movement")
        raw_bal = r.get("balance")
        desc = r.get("desc") or r.get("desc_main")
        rows.append({
            "movement": _parse_amount(raw_mv),
            "balance": _parse_amount(raw_bal),
            "desc": desc,
            "date": _clean_date(r.get("greg") or r.get("date"), desc),
            # الشاهد الثاني: العمود المطبوع كما رآه القارئ (يجوز أن يكون None —
            # حينها لا شاهد، ولا يُخترع). السلسلة تبقى الحَكَم؛ العمود يقابلها.
            "printed_col": _norm_col(r.get("col")),
            # RAW printed tokens kept alongside: the era detector fingerprints
            # pages from what was ON the paper, before any normalization.
            "raw_movement": raw_mv,
            "raw_balance": raw_bal,
            # The printed page number rides on the first row (FRONTIER rule 5):
            # position != identity in a scan — this is the scan-order truth.
            "page_no": r.get("page_no"),
        })
    return rows


def read_rows_vlm(image_path: str, prompt: str | None = None,
                  max_tokens: int = 4000, stats: dict | None = None) -> list[dict]:
    """One page image -> [{'movement': Decimal|None, 'balance': Decimal|None,
                           'desc': str|None, 'date': str|None,
                           'raw_movement': str|None, 'raw_balance': str|None}].

    Uses the FROZEN v2 prompt by default (`FRONTIER_PROMPT_V2`) — the same one the
    629-page corpus was read with since `reader_stamp` was added; `v1` is the
    earlier frozen prompt, kept for comparison runs. (The docstring here claimed
    the default was v1 while the code read v2 — a document contradicting code is a
    defect, not a note: FMEA FM-2.) Pass `prompt=STRUCTURE_AWARE_PROMPT` for
    red-band anatomy reads, or a `TOP_BAND_PROMPT.format(...)` for boundary
    recovery.

    Raises RuntimeError after retries; caller decides suspect handling.
    """
    user_prompt = prompt or FRONTIER_PROMPT_V2
    b64 = base64.b64encode(open(image_path, "rb").read()).decode()

    def _parse(content: str):
        rows = _rows_from_content(content)
        if rows and stats is not None:
            val = _parse_amount(rows[0].get("page_no"))
            if val is not None and val == int(val):
                stats["page_no"] = int(val)   # printed number = scan-order truth
        return rows

    return chat_vlm_image(b64, user_prompt, max_tokens, stats, parse=_parse)


_OPENING_MARKERS = ("افتتاح", "سابق")


def reread_boundary(image_path: str, prev_closing, page_no: int = 1,
                    stats: dict | None = None):
    """Targeted top-band re-read for an unverifiable page-start row.

    The workshop's «reread بالجوار» mechanism applied automatically: when the
    first row of a page cannot be chain-verified (anchor), re-read with the
    frozen TOP_BAND_PROMPT (Trap-5 boundary recovery — built for exactly
    this). A candidate is accepted ONLY when its own (amount, balance) pair
    closes against prev_closing — never a guess. Returns the |movement| as
    Decimal, or None.
    """
    prompt = TOP_BAND_PROMPT.format(page_no=page_no,
                                    prev_closing=str(prev_closing))
    b64 = base64.b64encode(open(image_path, "rb").read()).decode()

    def _pairs(content: str) -> list[tuple]:
        data = _extract_json(content)
        raw = data.get("rows", []) if isinstance(data, dict) else data
        pairs = []
        for r in raw or []:
            mv = _parse_amount(r.get("movement") or r.get("amount"))
            bal = _parse_amount(r.get("balance"))
            if mv is not None and bal is not None:
                pairs.append((mv, bal))
        return pairs

    pairs = chat_vlm_image(b64, prompt, max_tokens=1200, stats=stats,
                           parse=_pairs)
    for mv, bal in pairs or []:
        delta = bal - prev_closing
        if delta != 0 and abs(delta) == mv:
            return mv
    return None


def recover_anchor(raw_rows: list[dict], prev_closing, image_path: str,
                   page_no: int, stats: dict | None = None):
    """Resolve an anchor's missing movement through a verified re-read.

    Acceptance is triple-strict: the re-read must produce a self-consistent
    (amount, balance) pair AND the amount must equal the ORIGINAL row's
    balance delta — so a corrected value can never contradict the chain that
    follows. Returns (rows, recovered|None); rows are patched only on success.
    """
    if not raw_rows or prev_closing is None:
        return raw_rows, None
    first = raw_rows[0]
    if first.get("balance") is None:
        return raw_rows, None
    delta = first["balance"] - prev_closing
    if delta == 0:
        return raw_rows, None  # carry — not an anchor case
    try:
        got = reread_boundary(image_path, prev_closing, page_no, stats)
    except Exception:  # noqa: BLE001 — recovery must never kill a run
        got = None
    if got is None or got != abs(delta):
        return raw_rows, None
    # القراءة الجديدة للصفّ الأول هي **المطبوعة الصحيحة** (الورق نفسه أُعيد قراءته)،
    # فيجب أن تحملها خانة «الحركة كما طُبعت» مع الرقمية — وإلا تناقض عمودا الصفّ في
    # الملف المُسلَّم بلا تنبيه (٢٤ صفّاً: أوّل صفّ في كل صفحة استُدركت آلياً).
    # كشفه مدقّق خارجي، والبوابة لم تكن تراه لأنها تُقارن الرقمي بالسلسلة لا العمودين.
    patched = [dict(first, movement=got, raw_movement=got)] + list(raw_rows[1:])
    return patched, got


def _looks_opening(r: dict) -> bool:
    """Opening/carry rows print افتتاح/سابق descriptions; anything else with a
    printed amount is a transaction we must not swallow."""
    d = r.get("desc") or ""
    return any(m in d for m in _OPENING_MARKERS)


_JUNK_DATES = {"none", "null", "nan", "nil", "غير مقروء", "غير واضح", "-", "--", "?"}
_DATE_IN_TEXT = re.compile(r"[0-9٠-٩۰-۹]{8}")


def _ascii_digits(text: str) -> str:
    out = []
    for ch in text:
        o = ord(ch)
        if 0x0660 <= o <= 0x0669:
            out.append(chr(ord("0") + o - 0x0660))
        elif 0x06F0 <= o <= 0x06F9:
            out.append(chr(ord("0") + o - 0x06F0))
        else:
            out.append(ch)
    return "".join(out)


def _is_gregorian(candidate: str) -> bool:
    """8 خانات تُقرأ سنة-شهر-يوم في نطاق معقول (1900–2100)."""
    d = _ascii_digits(candidate)
    if len(d) != 8 or not d.isdigit():
        return False
    year, month, day = int(d[:4]), int(d[4:6]), int(d[6:8])
    return 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31


def _norm_col(value) -> str | None:
    """العمود المطبوع → debit/credit. لا تخمين: ما لا يُفهم يعود None."""
    t = str(value or "").strip().lower()
    if not t:
        return None
    if t in {"debit", "dr", "d", "مدين"} or "مدين" in t or "سحب" in t:
        return "debit"
    if (t in {"credit", "cr", "c", "دائن"} or "دائن" in t
            or "ايداع" in t or "إيداع" in t):
        return "credit"
    return None


def _clean_date(value, desc=None) -> str | None:
    """تاريخ نظيف: «None» النصّية ليست تاريخاً، ونصّها يُقرأ من الوصف عند غيابها.

    الحالة المقيسة: النموذج أعاد التاريخ **داخل الوصف** وترك خانته، فكتب القارئ
    «None» نصّاً. تلك الكلمة مرّت تاريخاً مطبوعاً، ثم **ورثها كل صفّ بعدها** حتى
    ضاعت تواريخ صفحتين كاملتين (10 و9 صفوف) في جولة إعادة القراءة.

    والورق يطبع **تاريخين** في الوصف (هجري ثم ميلادي)، فيُختار الأول الذي يُقرأ
    ميلادياً في نطاق معقول — لا أول ثماني خانات، لأنها الهجرية (١٤٤٥…) فتُرفض
    لاحقاً وتُحتسب الصفحة بلا تواريخ.
    """
    text = str(value or "").strip()
    if text.lower() in _JUNK_DATES:
        text = ""
    if not text and desc:
        for hit in _DATE_IN_TEXT.finditer(str(desc)):
            cand = hit.group(0)
            if _is_gregorian(cand):
                text = cand
                break
        else:
            hit = _DATE_IN_TEXT.search(str(desc))
            text = hit.group(0) if hit else ""
    return text or None


def fill_missing_dates(rows: list[dict]) -> int:
    """Statements print the date ONCE per group; siblings ship a blank cell.

    Carry the last printed date forward onto real transaction rows so an
    Excel/PDF export is complete, and MARK the origin (`date_source`) — an
    inherited date must never look printed. Opening/carry/boundary rows keep
    an empty date: their line is not a transaction and nothing may be invented.

    Returns the number of rows filled.
    """
    last: str | None = None
    filled = 0
    for r in rows:
        d = _clean_date(r.get("date"), r.get("desc")) or ""
        if d:
            if str(r.get("date") or "") != d:
                # تاريخ مُستعاد من الوصف (أو منظَّف من «None») — يُكتب في خانته
                r["date"] = d
                r["date_source"] = "recovered-from-description"
            last = d
            r.setdefault("date_source", "printed")
            continue
        if r.get("date") is not None:
            r["date"] = None      # «None» نصّية تُفرَّغ: ليست تاريخاً ولا تُورَّث
        if (last and r.get("kind") != "opening" and not r.get("boundary")
                and (r.get("side") or r.get("movement") is not None)):
            r["date"] = last
            r["date_source"] = "inherited"
            filled += 1
    return filled


def chain_derive(rows: list[dict], prev_balance: Decimal | None = None) -> list[dict]:
    """Balance chain is the arbiter: movement/side derived; VLM mv cross-checks.

    Row 0 of a fresh read = opening (its printed balance starts the chain).

    prev_balance (closing of the PREVIOUS page) enables cross-page continuity —
    the first balance row of a new page is NOT blindly an opening:
    - delta == 0                → carried balance row (رصيد سابق).
    - delta == the printed amt  → a REAL transaction starting the page (a scan
      boundary must not swallow its movement: a transfer +1000 turning 676 into
      1676 was once displayed as "opening 1676", losing the operation entirely).
    - anything else (incl. unreadable amt) → opening anchor; a movement is NEVER
      fabricated across a boundary we cannot verify.

    Suspect rows (|Δ| != printed mv) get ok=False; the caller re-reads them.
    Scale guard (×100 ambiguity, 629-page case): when a printed balance breaks
    the chain but ×100 fits (or vice versa), the chain value wins and the row is
    marked scale_fixed — never silently scaled.
    None balances (VLM null) don't crash the walk; they mark gaps.
    """
    out: list[dict] = []
    prev: Decimal | None = prev_balance
    boundary_pending = prev_balance is not None
    for r in rows:
        bal = r["balance"]
        if bal is None:
            out.append({**r, "derived_movement": None, "side": "",
                        "ok": False, "opening": False, "scale_fixed": False,
                        "boundary": None})
            prev = None  # chain broken; next row re-anchors
            boundary_pending = False
            continue
        if boundary_pending:
            boundary_pending = False
            delta = bal - prev
            printed = r["movement"]
            if delta == 0:
                out.append({**r, "derived_movement": Decimal("0"), "side": "",
                            "ok": True, "opening": True, "scale_fixed": False,
                            "boundary": "carry"})
            elif printed is not None and printed == abs(delta):
                side = "credit" if delta > 0 else "debit"
                out.append({**r, "derived_movement": abs(delta), "side": side,
                            "ok": True, "opening": False, "scale_fixed": False,
                            "boundary": "txn"})
            else:
                out.append({**r, "derived_movement": Decimal("0"), "side": "",
                            "ok": True, "opening": True, "scale_fixed": False,
                            "boundary": "anchor"})
        elif prev is None:
            printed = r["movement"]
            if printed is not None and not _looks_opening(r):
                # Fresh start whose opening row was not read (VLM occasionally
                # misses the dots-zero line): the row demonstrably IS a
                # transaction (printed amount + a real description) — keep its
                # movement visible; side stays undecided (no previous balance
                # to derive it from — never guess).
                out.append({**r, "derived_movement": printed, "side": "",
                            "ok": True, "opening": False, "scale_fixed": False,
                            "boundary": None})
            else:
                out.append({**r, "derived_movement": Decimal("0"), "side": "",
                            "ok": True, "opening": True, "scale_fixed": False,
                            "boundary": None})
        else:
            delta = bal - prev
            mv = abs(delta)
            side = "credit" if delta > 0 else "debit" if delta < 0 else ""
            printed = r["movement"]
            ok = printed is None or printed == mv
            scale_fixed = False
            if not ok and printed is not None and printed != 0:
                # ×100 ambiguity: printed*100 == mv or printed == mv*100
                if printed * 100 == mv or printed == mv * 100:
                    ok, scale_fixed = True, True
            out.append({**r, "derived_movement": mv, "side": side,
                        "ok": ok, "opening": False, "scale_fixed": scale_fixed,
                        "boundary": None})
        prev = bal
    return out


if __name__ == "__main__":
    import sys

    rows = read_rows_vlm(sys.argv[1])
    for r in chain_derive(rows):
        mark = "✓" if r["ok"] else "✗"
        print(f"{mark} bal={r['balance']} mv={r['movement']} "
              f"derived={r['derived_movement']} side={r['side']}")
