"""Deterministic scope gate — the answers that must not depend on a model.

WHY THIS EXISTS
The expanded refusal test measured three defects in the question layer:

* asked for a balance **at another bank**, the agent refused on one run and
  answered with a Rajhi balance on the next — the same question, two behaviours;
* asked about a **year outside the statement's period** it produced a figure;
* asked whether a **non-existent amount** existed, it confirmed one.

They share one cause: a question whose PREMISE lies outside the document was
handed to a model holding tools, and the model did the most helpful-looking
thing. Helpfulness is not a safety property, and a prompt is not a guarantee.

So these cases are decided from the question text and the data BEFORE any model
call, which makes the answer identical on every run:

* ``out_of_scope`` — another bank, or personal data a statement never carries;
* ``no_such_data`` — a year outside the period, a page past the last one, an
  amount no row carries (answered from the rows, not from a guess);
* ``in_scope``     — everything else, untouched.

The gate is deliberately narrow. A gate that swallows real questions is worse
than no gate at all, which is why the in-scope tests in the suite outnumber the
refusal tests.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

OUR_BANK = ("الراجحي", "rajhi", "alrajhi")

# Banks that are NOT the one this project reads. Kept as data, not prose.
# TWO lists, because Arabic glues its words together. «ساب» (SABB) lives inside
# «حِساب» (account), and «الرياض» is a city in an ATM description long before it
# is a bank — containment matching refused «ما رصيد الحساب؟», the one question
# this project exists to answer. (Measured, not feared: four of six sentences.)
OTHER_BANKS_STRONG = (
    "الأهلي", "الاهلي", "سامبا", "البلاد", "الإنماء", "الانماء", "ساب",
    "stc bank", "بنك الرياض", "بنك الأهلي", "الرياض",
)
# Real words on their own: they gate only when the question says «بنك».
OTHER_BANKS_WEAK = ("الرياض", "الخليج", "الجزيرة", "العربي", "الاستثمار",
                    "الفرنسي")
_STRONG_ONLY = tuple(b for b in OTHER_BANKS_STRONG if b not in OTHER_BANKS_WEAK)
_AR_CHARS = "\u0621-\u064A\u0660-\u0669"


def _mentions(text: str, token: str) -> bool:
    """Whole-token match, Arabic-aware.

    Arabic writes its words unspaced, so `token in text` matches inside longer
    words — the defect an external audit found by running it. A token is only a
    mention when no Arabic letter touches it on either side.
    """
    t = re.escape(token.strip())
    left = r"(?<![A-Za-z])" if token[0].isascii() else f"(?<![{_AR_CHARS}])"
    right = r"(?![A-Za-z])" if token[-1].isascii() else f"(?![{_AR_CHARS}])"
    return re.search(left + t + right, text) is not None

# Data a statement does not carry, whatever else it says.
# «الجوال» alone is NOT here on purpose: «فاتورة الجوال» is a real row in this
# statement, and a marker that refuses a real question is worse than none.
PERSONAL_MARKERS = (
    "رقم الجوال", "رقم جوال", "رقم هاتف", "الهوية", "رقم الهوية",
    "عنوان صاحب", "الإيميل", "إيميل",
    "الايميل", "البريد الإلكتروني", "تاريخ الميلاد", "رقم البطاقة",
    "الرقم السري", "كلمة المرور",
)

REFUSAL = "غير موجود في الكشف"

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_YEAR = re.compile(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)")
#: **قارئُ الصفحة الواحد (بوّابةُ المُنتِج · R105-4):** كان في المستودع قارئان لرقم الصفحة —
#: هذا (`_PAGE`) وآخرُ في `qa.py` — **يفترقان** على الصيغ: «صفحة ٧٠٠» بلا «ال» · «الصفحه» بالهاء ·
#: «الصفحتين ٢ و٣» (المثنّى) · `page 700` · والمدى «١٠–١٢» (كان يُسقط ١١ صامتًا).
#: فصار **قارئٌ واحدٌ هنا يُعيد قائمةً**، تستعمله البوّابةُ والاسترجاعُ معًا؛ ومنعُ تعدّد القارئين
#: هو نصُّ قاعدة «لا آليّةَ ثانيةٌ بجانب آليّةٍ معطوبة» — والبديلُ ترقيعٌ لا إصلاح.
#: **وحدُّه مُعلَن:** المدى يُفكّ بسقف `_MAX_RANGE` (فلا يُفكّ «١–١٠٠٠» من خطأٍ مطبعيّ إلى ألف صفحة)،
#: والأرقامُ تُقرأ من **نافذةٍ ملتصقةٍ بكلمة الصفحة** (فلا تُلتقط «٥» من «الصفحة ٤ من ٥»).
_PAGE_WORDS = re.compile(r"(?:ال)?صفح(?:ة|ه|تين|تان|ات)|pages?|page", re.IGNORECASE)
_PAGE_NUMBERS = re.compile(r"\s*(?:من\s*)?\d+(?:\s*(?:و|,|،|–|—|-|إلى|and|to)\s*\d+)*")
_RANGE_SPLIT = re.compile(r"\s*(?:–|—|-|إلى|to)\s*")
_LIST_SPLIT = re.compile(r"\s*(?:و|,|،|and)\s*")
_MAX_RANGE = 50
_AMOUNT = re.compile(r"([0-9٠-٩۰-۹][0-9٠-٩۰-۹,٬.]*[0-9٠-٩۰-۹])")

# «Does this amount exist?» — the only shape where an absent amount is an answer.
EXISTENCE_MARKERS = ("هل يوجد", "هل هناك", "هل توجد", "هل تم", "يوجد تحويل",
                     "يوجد حركة", "هل حصل")
# …and never when the figure is a threshold rather than a payment.
COMPARISON_MARKERS = ("أكثر من", "اكثر من", "أقل من", "اقل من", "تتجاوز",
                      "يتجاوز", "أكبر", "اكبر", "أصغر", "اصغر", "بين ",
                      "فوق", "تحت", "أعلى", "أدنى")


@dataclass
class Scope:
    kind: str                      # in_scope | out_of_scope | no_such_data
    reason: str = ""
    answer: str = ""
    matches: list = field(default_factory=list)


def _norm(text: str) -> str:
    return (text or "").translate(_AR_DIGITS).replace("٬", ",").replace("٫", ".")


def _has_our_bank(q: str) -> bool:
    low = q.lower()
    return any(k in low for k in OUR_BANK)


def years_in(q: str) -> list[int]:
    return [int(m.group(1)) for m in _YEAR.finditer(_norm(q))]


def _numbers_in(window: str) -> list[int]:
    """أرقامُ النافذة — **والمدى يُفكّ** («١٠–١٢» ⇒ ١٠ · ١١ · ١٢)، والمفصولُ يُجمَع («٢ و٣» ⇒ ٢ · ٣)."""
    out: list[int] = []
    for part in _LIST_SPLIT.split(window.strip()):
        nums = [int(x) for x in re.findall(r"\d+", part)]
        if (len(nums) == 2 and _RANGE_SPLIT.search(part)
                and 0 < nums[1] - nums[0] <= _MAX_RANGE):
            out.extend(range(nums[0], nums[1] + 1))
        else:
            out.extend(nums)
    return out


def _page_windows(text: str):
    """نوافذُ الصفحة في نصٍّ مُطبَّع الأرقام: (بداية · نهاية · أرقامها) — **مصدرُ `pages_in` الوحيد**،
    ويقرؤها قارئُ المبلغ ليعرف أنّ «١٢» في «الصفحة ١٢» رقمُ صفحةٍ لا مبلغ (دورٌ واحدٌ لكلّ رقم)."""
    for m in _PAGE_WORDS.finditer(text):
        window = _PAGE_NUMBERS.match(text, m.end())
        if window:
            yield window.start(), window.end(), _numbers_in(window.group(0))


def pages_in(q: str) -> list[int]:
    """**قارئُ الصفحة الواحد** — كلُّ صفحةٍ يسمّيها السؤال، بترتيبها وبلا تكرار، والمدى مُفكوك.

    (الصيغُ المسمّاة في البوّابة: «الصفحة ٧» · «صفحة ٧٠٠» · «الصفحه ٧٠٠» · «الصفحتين ٢ و٣» ·
    `page 700` · و«الصفحات ١٠–١٢».) **والدالّةُ خالصةٌ** فتُقاس بلا نموذجٍ وبلا كلفة.
    """
    out: list[int] = []
    for _s, _e, nums in _page_windows(_norm(q)):
        for v in nums:
            if v not in out:
                out.append(v)
    return out


def page_in(q: str) -> int | None:
    """أوّلُ صفحةٍ يسمّيها السؤال — واجهةٌ رقيقةٌ فوق `pages_in` لمن يسأل «أيّ صفحة؟» وحدَها."""
    pages = pages_in(q)
    return pages[0] if pages else None


#: **دورٌ واحدٌ لكلّ رقمٍ في السؤال.** كان كلُّ رقمٍ يُقرأ مبلغًا: السنةُ (٢٠٢٤ ⇒ 2,024.00) ورقمُ الصفحة
#: (١٢ ⇒ 12.00) ويومُ التاريخ (١٥/٠٣ ⇒ 15.00)، ثمّ يُرفض السؤالُ لأنّ «المبلغ» غيرُ موجود. والمبلغُ الآن
#: **ما يسمّيه السؤالُ مالًا** — رقمٌ تلاصقه كلمةُ عملة (ريال · ر.س · SAR) أو تسبقه كلمةُ «مبلغ» — وليس
#: داخل نافذة صفحة (`_page_windows`) ولا جزءًا من مركّبٍ بشرطةٍ أو مائل (تاريخ · مدى · مرجع).
#: **وما يُهمَل مُعلَن:** «هل يوجد سحب 777؟» بلا كلمة مال يمرّ إلى الوكيل وأدواته بدل رفضٍ حتميّ.
_NUM_RUN = re.compile(r"\d(?:[\d,./-]*\d)?")
_CURRENCY_AFTER = re.compile(r"\s*(?:ريال|ريالا|ريالات|ر\.?\s?س|sar|sr)(?![\w])", re.IGNORECASE)
_AMOUNT_BEFORE = re.compile(r"(?:^|[^\w])(?:[وفبل]|بال|ال)?مبلغ(?:ا|\s+(?:قدره|وقدره))?\s*$")


def _money_value(raw: str) -> Decimal | None:
    """قيمةُ رمزٍ ماليّ: الفاصلةُ آلافٌ، **إلّا الأخيرةَ تتبعها خانتان بلا نقطة** («500,00») فهي عشريّة."""
    if raw.count(".") > 1:
        return None
    if "." not in raw and re.search(r",\d{2}$", raw):
        raw = raw[:-3].replace(",", "") + "." + raw[-2:]
    try:
        return Decimal(raw.replace(",", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _money_spans(text: str) -> list[tuple[int, int, Decimal]]:
    """الأرقامُ التي يسمّيها السؤالُ مالًا — في نصٍّ مُطبَّع الأرقام."""
    paged = [(a, b) for a, b, _n in _page_windows(text)]
    out = []
    for m in _NUM_RUN.finditer(text):
        raw = m.group(0)
        if "/" in raw or "-" in raw:                       # تاريخ · مدى · مرجع — ليس مبلغًا
            continue
        if any(a <= m.start() < b for a, b in paged):      # رقمُ صفحة
            continue
        named = (_CURRENCY_AFTER.match(text, m.end())
                 or _AMOUNT_BEFORE.search(text, 0, m.start()))
        if not named:
            continue
        v = _money_value(raw)
        if v is not None:
            out.append((m.start(), m.end(), v))
    return out


def amounts_in(q: str) -> list[Decimal]:
    return [v for _a, _b, v in _money_spans(_norm(q))]


def _years_not_money(q: str) -> list[int]:
    """سنواتُ السؤال **إلّا رقمًا سمّاه مالًا** («بمبلغ 2000 ريال» ليس سنة 2000)."""
    text = _norm(q)
    money = [(a, b) for a, b, _v in _money_spans(text)]
    return [int(m.group(1)) for m in _YEAR.finditer(text)
            if not any(a <= m.start() < b for a, b in money)]


#: **المصرفُ الآخر يُرفض حين يكون موضعَ الحساب المسؤول عنه، لا طرفًا في حركة.** «كم رصيدي في الأهلي؟»
#: يسأل عن حسابٍ ليس هذا الكشف — يُثبَت من الكشف نفسه (هو كشفُ الراجحي). أمّا «تحويلٌ إلى بنك الرياض»
#: و«دفعتُ للمستشفى الأهلي» فحركاتٌ في هذا الكشف تُجيب عنها أدواتُه. فالرفضُ يحتاج الأمرين معًا:
#: ① السؤالُ يطلب صفةَ حساب (رصيد · كشف · حساب)، ② والمصرفُ **موضعُه**: يحكمه حرفُ ظرفٍ (في · لدى ·
#: عند · بـ) أو يضاف إليه الحسابُ مباشرةً («رصيد بنك الرياض»). وما سوى ذلك (إلى · من · لـ · «صراف بنك
#: الرياض») طرفٌ أو وصفٌ في حركة ⇒ يمرّ. **والحكمُ بالإثبات لا بالاستثناء:** ما لا يُثبت موضعًا يمرّ.
_ACCOUNT_WORD = re.compile(r"^(?:[وف])?(?:[بلك])?(?:ال)?(?:رصيد|كشف|حساب)(?:ي|ه|ها|نا|ك|كم|ات|اتي)?$")
_BANK_HEAD = re.compile(r"^(?:[وف])?(?P<cl>[بلك])?(?:ال|ل)?(?:بنك|مصرف)$")
_LOCUS_WORDS = {"في", "لدي", "عند"}       # مُطبَّعة: «لدى» ⇒ «لدي»


def _tokens(q: str) -> list[str]:
    from statement_qa.ledger import norm_ar              # المُطبِّعُ الواحد (هو مُطبِّعُ `row_fts`)
    return re.findall(r"[^\W_]+", norm_ar(q).lower())


def _readings(tok: str):
    """قراءاتُ الكلمة بلواصقها: (الحرفُ الملصق · الأصل) — «للاهلي» ⇒ (ل · الاهلي)، «بساب» ⇒ (ب · ساب)."""
    t = tok[1:] if tok[:1] in "وف" and len(tok) > 3 else tok
    yield "", tok
    yield "", t
    if t.startswith("لل"):
        yield "ل", "ال" + t[2:]
    if t[:1] in "بلك":
        yield t[0], t[1:]


def _bank_as_account(q: str) -> str | None:
    """اسمُ المصرف الآخر **حين يكون موضعَ الحساب المسؤول عنه** — وإلّا None."""
    from statement_qa.ledger import norm_ar
    toks = _tokens(q)
    if not any(_ACCOUNT_WORD.match(t) for t in toks):
        return None
    strong = {norm_ar(b).lower(): b for b in _STRONG_ONLY}
    weak = {norm_ar(b): b for b in OTHER_BANKS_WEAK}
    for i, t in enumerate(toks):
        head = _BANK_HEAD.match(toks[i - 1]) if i > 0 else None
        hit = next(((cl, strong.get(base) or (weak.get(base) if head else None))
                    for cl, base in _readings(t)
                    if strong.get(base) or (head and weak.get(base))), None)
        if hit is None and t == "bank" and i > 0 and toks[i - 1] == "stc":
            hit, head = ("", "stc bank"), None             # الاسمُ كلمتان: «stc bank»
        if hit is None:
            continue
        cl, name = hit
        start = i - 1 if (head or name == "stc bank") else i
        if head:
            cl = head.group("cl") or ""
        prev = toks[start - 1] if start > 0 else ""
        if cl == "ب" or prev in _LOCUS_WORDS or _ACCOUNT_WORD.match(prev):
            return name                                    # موضعُ الحساب المسؤول عنه
    return None


_HOLDER = re.compile(r"^(?:[وفبل]|لل)?(?:ال)?صاحب")
_ADDRESS = re.compile(r"^(?:[وفبل])?(?:ال)?عنوان(?P<own>ي|ه)?$")


def _holder_address(q: str) -> bool:
    """«العنوان» بياناتٌ شخصيّة **حين يُنسب إلى صاحب الحساب** — لا حين يكون اسمًا («فندق العنوان»)."""
    toks = _tokens(q)
    addr = [m for m in (_ADDRESS.match(t) for t in toks) if m]
    return bool(addr) and (any(m.group("own") for m in addr)
                           or any(_HOLDER.match(t) for t in toks))


def classify(question: str, years=(), max_page: int | None = None,
             amounts=frozenset(), *, n_pages: int | None = None,
             pages_read=frozenset()) -> Scope:
    """Decide the question's scope from its text and the data. No model, no luck.

    `years` = the years the statement actually covers; `max_page` = the last page
    number present; `amounts` = every riyal figure the rows carry; `pages_read` =
    the pages that actually produced rows; `n_pages` = the document's page count
    (the only fact the rows cannot tell). Pass None/empty when the caller has no
    data (RAG-only mode) — the gate then stays open, which is the honest default:
    it can only refuse what it can prove.
    """
    q = question or ""

    # 1) another bank as the place of the account asked about — unless ours is named
    if not _has_our_bank(q):
        bank = _bank_as_account(q)
        if bank:
            return Scope(
                "out_of_scope", f"سؤال عن {bank}",
                f"{REFUSAL} — هذا الكشف يخصّ مصرف الراجحي، وسؤالك عن {bank} "
                f"(مصرف آخر). لا أستطيع الجواب عنه من كشف الراجحي، ولا أُخمّن.")

    # 2) personal data a statement never carries
    #    («العنوان» وحدَه ليس في القائمة: «فندق العنوان» اسمٌ في حركة. يُرفض حين يُنسب إلى صاحب الحساب.)
    asked = [m for m in PERSONAL_MARKERS if m in q] or (["العنوان"] if _holder_address(q) else [])
    if asked:
        marker = asked[0]
        return Scope(
            "out_of_scope", marker,
            f"{REFUSAL} — الكشف لا يحمل «{marker}» ولا أي بيانات شخصية "
            f"من هذا النوع. الأرقام التي أستطيع إثباتها هي الحركات "
            f"والأرصدة والإجماليات المطبوعة.")

    # 3) a year the statement does not cover
    if years:
        known = {int(y) for y in years}
        for y in _years_not_money(q):
            if y not in known:
                span = (f"{min(known)}–{max(known)}" if len(known) > 1
                        else str(next(iter(known))))
                return Scope(
                    "no_such_data", f"سنة خارج المدى ({y})",
                    f"{REFUSAL} — لا توجد حركات في سنة {y}؛ فترة هذا الكشف "
                    f"{span}. لم أعرض أي مبلغ لأن لا شيء يسنده.")

    # 4) أيُّ صفحةٍ لا سطورَ لها — **ثلاثةُ أصنافٍ مُسمّاة، ولكلٍّ قولُه الصادقُ وحدَه**
    #    (بوّابةُ المُنتِج · R105-4 · ثمّ R115-7 · ثمّ R117-2): كان الفحصُ يقرأ أوّلَ صفحةٍ بقارئٍ
    #    أضيقَ من قارئ الاسترجاع ⇒ فسؤالٌ يقول «كم عدد الحركات في صفحة ٧٠٠؟» (بلا «ال») **يمرّ إلى
    #    النموذج**؛ والقارئُ اليوم واحدٌ (`pages_in`) فالحكمان لا يفترقان.
    #
    #    **(R115-7 · مراجعة ١١٥ · ثمّ R117-2 · مراجعة ١١٧): لا يُدَّعى عن الكشف ما لم يُقرأ،
    #    ولا يُقال عن صفحةٍ موجودةٍ إنّها غيرُ موجودة.** والقاعدةُ ثلاثيّة:
    #      ① صفحةٌ تفوق **عددَ صفحات المستند** (`n_pages`) ⇒ «خارج الملف» بحقّ، ويُعلَن انتهاؤه.
    #      ② صفحةٌ **داخلةٌ فيه** ولا سطورَ لها **فوق أقصى صفحةٍ فيها سطورٌ** (`max_page`) ⇒
    #         تُسمّى داخلةً ولم تُقرأ سطورُها في الجدول — **ولا تُسمّى غيرَ موجودة**.
    #      ③ صفحةٌ داخلةٌ **في مدى ما قُرئ** (`max_page`) وبلا سطورٍ (`pages_read`) ⇒ تُسمّى كذلك،
    #         **ولا يُقال إنّ الكشف خلا منها** (الجدولُ هو ما لا سطورَ فيه، لا المستند).
    #    و`pages_read` = الصفحاتُ التي أنتجت صفوفًا فعلًا؛ و`n_pages` لا يُشتقّ من الصفوف بل
    #    **يمرّره من يعرفه** (التطبيقُ من الملفّ · والقياسُ من `build_rows`) — وبهذا صار عدُّ
    #    الصفحات **شرطًا للصدق لا تحسينًا مُعلَنًا** (كان هذا القولَ في هذا الموضع، وهو تضييقٌ
    #    لمعنى بند القرار — سُحِب في مراجعة ١١٧ بتاريخه).
    named = pages_in(q)
    if named:
        outside = [p for p in named if n_pages is not None and p > n_pages]
        if outside:
            listed = "، ".join(str(p) for p in outside)
            return Scope(
                "no_such_data", f"صفحة خارج الملف ({listed})",
                f"{REFUSAL} — الكشف ينتهي عند صفحة {n_pages}، فلا صفحة {listed} فيه.")
        unread = [p for p in named
                  if (max_page is not None and p > max_page)
                  or (pages_read and p not in pages_read)]
        if unread:
            listed = "، ".join(str(p) for p in unread)
            if n_pages is not None:
                head = (f"**الصفحةُ {listed} داخلةٌ في الكشف** ({n_pages} صفحة)"
                        + (f"، وأقصى صفحةٍ فيها سطورٌ في الجدول الذي أعمل عليه {max_page}."
                           if max_page is not None else "."))
            elif max_page is not None:
                head = (f"**الصفحةُ {listed}** لا سطورَ لها في الجدول الذي أعمل عليه "
                        f"(أقصى صفحةٍ فيه سطورٌ {max_page})، وعددُ صفحات المستند غيرُ مُعلَن.")
            else:
                head = f"**الصفحةُ {listed}** لا سطورَ لها في الجدول الذي أعمل عليه."
            return Scope(
                "no_such_data", f"صفحةٌ لا سطورَ مقروءةً لها ({listed})",
                f"{head} لم تُقرأ سطورُها فيه بعد ⇒ فلا أُجيب عمّا لا سطرَ لي فيه، "
                f"ولا أُعلن انتهاءَ الكشف من غياب سطورِها.")


    # 5) an amount no row carries — and ONLY when the question asks about the
    #    existence of that amount. «الحركات التي تتجاوز ٥٠٠» names a threshold,
    #    not a payment: refusing it as «no such amount» would be the gate
    #    swallowing a real question, which is the one failure mode worse than
    #    the defects it was built for.
    if amounts and any(m in q for m in EXISTENCE_MARKERS) and not any(
            m in q for m in COMPARISON_MARKERS):
        known = set(amounts)
        for a in amounts_in(q):
            if a not in known:
                shown = f"{a:,.2f}"
                return Scope(
                    "no_such_data", f"مبلغ غير موجود ({shown})",
                    f"{REFUSAL} — لا توجد أي حركة بمبلغ {shown} في هذا الكشف "
                    f"(بحث حتمي في كل الصفوف). لم أؤكّد مبلغاً لا سند له.")
    return Scope("in_scope")
