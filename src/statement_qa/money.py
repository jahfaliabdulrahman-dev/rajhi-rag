"""المال: نصٌّ من العقد أو رقمٌ حسابيّ ⇒ نصٌّ مُنسَّق — **موضعٌ واحدٌ لكلّ الواجهات**.

**العطبُ الذي يمنعه (مقيس):** العقدُ يخزّن المال `TEXT` (المالُ لا يُطبَع عائمًا)، و`"{:,.2f}".format(str)`
يرفع `ValueError` ⇒ فسقطت أداةُ الوكيل `page_summary`، وكان في `render` و`app` مثلُه.
**وغيرُ الرقمِ يُعرَض كما هو** ولا يُبتلع: إخفاؤه يجعل الصّامتَ يُقرأ نجاحًا.
**وبلا تبعيّات:** تُستورَد في أضيق خطوةِ CI (لا LangChainَ ولا numpy).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

_MONEY = "{:,.2f}"


def money(value, *, dash: str = "") -> str:
    """مالٌ ⇒ نصٌّ مُنسَّق. `None`/الفراغ ⇒ `dash`؛ وغيرُ الرقميّ ⇒ كما هو."""
    if value is None or value == "":
        return dash
    if isinstance(value, (int, float)):
        return _MONEY.format(value)
    text = str(value).strip()
    try:
        return _MONEY.format(Decimal(text.replace(",", "")))
    except (InvalidOperation, ArithmeticError, ValueError):              # noqa: PERF203
        return text


def amount(value) -> "Decimal | None":
    """مالٌ ⇒ `Decimal` للمقارنة والجمع — **موضعُ التحويل الواحد** كما أنّ `money` موضعُ التنسيق.

    **وكان هذا منطقًا ثانيًا في `qa_tools` (`_dec`)**: نسخةٌ من السطر نفسه في ملفٍّ آخر ⇒ افتراقٌ
    صامتٌ ينتظر (R93-7). و`None` هنا تعني **«لم يُقرأ رقمًا»** لا «صفر» — فيُعدّها الجامعُ في
    «غير محسوم» ولا تُبتلع.
    """
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ArithmeticError, ValueError):              # noqa: PERF203
        return None


