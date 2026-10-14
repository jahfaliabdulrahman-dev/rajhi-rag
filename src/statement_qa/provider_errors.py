"""**رفضُ المزوّد يُقرأ من نوعه لا من نصّه** (R117-3 · R117-8 · مراجعة ١١٧).

**العطبُ المقيس:** كان الكاشفُ **قائمةَ كلماتٍ على نصّ الخطأ** (`"402"`, `"credit"`,
`"insufficient"`, `"key limit"`, `"quota"`). وقِيس بمسبارٍ بلا كلفة على `main` أنّ شكلين
موثَّقين عند OpenRouter **لا يُلتقَطان**:

* **حدُّ المفتاح** ⇒ **٤٠٣** وحقلُ `error.metadata.limit_source = "openrouter_key_limit"`،
  والوثائقُ تقول صراحةً: **افرِع على `limit_source` لا على نصّ الرسالة**؛
* **لا مضيفَ تحت الحدّ** ⇒ **٥٠٣** («no available model provider that meets your routing
  requirements») — وهو ما يُنتجه `provider.max_price` حين لا يبقى مضيفٌ تحت الحدّ.

فما لا يُلتقَط **يُسجَّل جوابًا خاطئًا** بدل توقّفٍ مُسمّى — وهو عينُ ما منعه القرار. والمعلومةُ
الصحيحة في الاستثناء نفسه: `status_code` و`body` (قِيس على `openai.APIStatusError`).

**والطبقةُ الثانية أيضًا مُقاسة:** `langchain-openai` لا يمرّر خطأَ `openai` كما هو دائمًا —
بل **يرفع أصنافًا وارثةً منه** (`OpenAIPermissionDeniedError` لـ٤٠٣ و`OpenAIAPIError`
لـ٥٠٣)، ويرث `status_code` و`body` من الأصل ⇒ فالقراءةُ **بالسمة** تُصيب الأصلَ والوارثَ معًا،
والقراءةُ بـ`isinstance` على صنفٍ واحد تُخطئ نصفَ الحالات.

**وحدُّ هذا الملفّ مُعلَن:** ثلاثةُ أصنافٍ موثَّقة (٤٠٢ · ٤٠٣ · ٥٠٣) — وما عداها يُعاد رفعُه كما هو
(لا يُبتلع خطأٌ مجهول، ولا يُسمّى باسمٍ لا يخصّه).
"""
from __future__ import annotations

#: ٤٠٢ — نفادُ رصيد الحساب (OpenRouter).
OUT_OF_CREDIT = "provider_out_of_credit"
#: ٤٠٣ — حدُّ المفتاح: `error.metadata.limit_source` (الموثَّق: `openrouter_key_limit`).
KEY_LIMIT = "provider_key_limit"
#: ٥٠٣ — لا مضيفَ يخدم النموذجَ تحت `provider.max_price`.
NO_HOST_UNDER_PRICE = "provider_no_host_under_price"

#: الأصنافُ التي تُوقف القياسَ توقّفًا مُسمًّى (وتُعرَض للمستخدم برسالةٍ عربيّة).
PROVIDER_REFUSALS = (OUT_OF_CREDIT, KEY_LIMIT, NO_HOST_UNDER_PRICE)


def status_code(err) -> int | None:
    """رمزُ الحالة من الاستثناء — بالسمة (فيرثها صنفُ المكتبة الوارث أيضًا)."""
    code = getattr(err, "status_code", None)
    if code is None:
        code = getattr(getattr(err, "response", None), "status_code", None)
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None


def _find_key(obj, key: str):
    """أوّلُ قيمةٍ للحقل في جسمٍ متداخل — **الشكلُ موثَّقٌ غيرُ مُقيَّد** فالبحثُ في الشجرة.

    (قِيس في الوثائق: `error.metadata.limit_source`؛ ويُقرأ كذلك لو جاء الحقلُ في جذر الجسم.)
    """
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find_key(v, key)
            if found is not None:
                return found
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found = _find_key(v, key)
            if found is not None:
                return found
    return None


def limit_source(err) -> str | None:
    """`limit_source` من جسم الاستثناء (يُسجَّل مع الحكم — ولا يُشترَط لتصنيفه)."""
    body = getattr(err, "body", None)
    if isinstance(body, str):
        import json

        try:
            body = json.loads(body)
        except ValueError:
            return None
    src = _find_key(body, "limit_source")
    return str(src) if src else None


def classify(err) -> str | None:
    """رمزُ الرفض المُسمّى من **نوع** الخطأ (لا من نصّه) — و`None` لما ليس رفضَ مزوّدٍ موثَّقًا."""
    code = status_code(err)
    if code == 402:
        return OUT_OF_CREDIT
    if code == 403:
        return KEY_LIMIT                       # والوثائق: افرِع على limit_source لا على النصّ
    if code == 503:
        return NO_HOST_UNDER_PRICE
    return None


def answer_text(kind: str, err=None) -> str:
    """رسالةُ المستخدم العربيّة لحالةٍ مُسمّاة — **ولا نصَّ إنجليزيًّا من المكتبة على الشاشة**."""
    if kind == OUT_OF_CREDIT:
        return ("⛔ **رصيدُ حساب النموذج لا يكفي (402)**: المزوّد رفض الطلبَ فلا أُجيب من الكشف، "
                "ولن أخترع رقمًا. زِد الرصيدَ أو استعمل مفتاحًا آخر ثمّ أعد السؤال.")
    if kind == KEY_LIMIT:
        src = limit_source(err) if err is not None else None
        named = f" · limit_source={src}" if src else ""
        return ("⛔ **بلغ المفتاحُ حدَّ صرفه عند المزوّد (403" + named + ")**: رُفض الطلبُ قبل أن "
                "يُحاسَب، فلا أُجيب. ارفع حدَّ المفتاح (أو استعمل مفتاحًا آخر) ثمّ أعد السؤال.")
    if kind == NO_HOST_UNDER_PRICE:
        return ("⛔ **لا مضيفَ يخدم النموذجَ تحت حدّ السعر المُرسَل (503)**: لم يُشترَ نداءٌ أغلى من "
                "الحدّ، ولم أُجب. وحدُّ السعر إعدادٌ مُعلَن، فرفعُه قرارُ المالك.")
    return "⛔ رُفض الطلبُ عند المزوّد، فلا أُجيب."
