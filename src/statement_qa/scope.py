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
    "رقم الجوال", "رقم جوال", "رقم هاتف", "الهوية", "رقم الهوية", "العنوان",
    "عنوان صاحب", "الإيميل", "إيميل",
    "الايميل", "البريد الإلكتروني", "تاريخ الميلاد", "رقم البطاقة",
    "الرقم السري", "كلمة المرور",
)

REFUSAL = "غير موجود في الكشف"

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_YEAR = re.compile(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)")
_PAGE = re.compile(r"الصفح(?:ة|ات)?\s*([0-9٠-٩۰-۹]{1,4})")
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
    return (text or "").translate(_AR_DIGITS).replace("٬", ",")


def _has_our_bank(q: str) -> bool:
    low = q.lower()
    return any(k in low for k in OUR_BANK)


def years_in(q: str) -> list[int]:
    return [int(m.group(1)) for m in _YEAR.finditer(_norm(q))]


def page_in(q: str) -> int | None:
    m = _PAGE.search(_norm(q))
    return int(m.group(1)) if m else None


def amounts_in(q: str) -> list[Decimal]:
    out = []
    for m in _AMOUNT.finditer(_norm(q)):
        raw = m.group(1).replace(",", "")
        if raw.count(".") > 1 or len(raw.replace(".", "")) < 1:
            continue
        try:
            out.append(Decimal(raw).quantize(Decimal("0.01")))
        except (InvalidOperation, ValueError):
            continue
    return out


def classify(question: str, years=(), max_page: int | None = None,
             amounts=frozenset()) -> Scope:
    """Decide the question's scope from its text and the data. No model, no luck.

    `years` = the years the statement actually covers; `max_page` = the last page
    number present; `amounts` = every riyal figure the rows carry. Pass None/empty
    when the caller has no data (RAG-only mode) — the gate then stays open, which
    is the honest default: it can only refuse what it can prove.
    """
    q = question or ""
    low = q.lower()

    # 1) another bank named — unless the owner's bank is the one named
    if not _has_our_bank(q):
        bank = next((b for b in _STRONG_ONLY if _mentions(q, b)), None)
        if bank is None and "بنك" in q:
            bank = next((b for b in OTHER_BANKS_WEAK if _mentions(q, b)), None)
        if bank:
            return Scope(
                "out_of_scope", f"سؤال عن {bank}",
                f"{REFUSAL} — هذا الكشف يخصّ مصرف الراجحي، وسؤالك عن {bank} "
                f"(مصرف آخر). لا أستطيع الجواب عنه من كشف الراجحي، ولا أُخمّن.")

    # 2) personal data a statement never carries
    for marker in PERSONAL_MARKERS:
        if marker in q:
            return Scope(
                "out_of_scope", marker,
                f"{REFUSAL} — الكشف لا يحمل «{marker}» ولا أي بيانات شخصية "
                f"من هذا النوع. الأرقام التي أستطيع إثباتها هي الحركات "
                f"والأرصدة والإجماليات المطبوعة.")

    # 3) a year the statement does not cover
    if years:
        known = {int(y) for y in years}
        for y in years_in(q):
            if y not in known:
                span = (f"{min(known)}–{max(known)}" if len(known) > 1
                        else str(next(iter(known))))
                return Scope(
                    "no_such_data", f"سنة خارج المدى ({y})",
                    f"{REFUSAL} — لا توجد حركات في سنة {y}؛ فترة هذا الكشف "
                    f"{span}. لم أعرض أي مبلغ لأن لا شيء يسنده.")

    # 4) a page past the last one
    page = page_in(q)
    if max_page is not None and page is not None and page > max_page:
        return Scope(
            "no_such_data", f"صفحة خارج الملف ({page})",
            f"{REFUSAL} — الكشف ينتهي عند صفحة {max_page}، فلا صفحة {page} فيه.")

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
