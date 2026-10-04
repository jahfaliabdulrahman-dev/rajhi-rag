"""عدُّ الصفوف بترميز التاريخ — **معياران مُسمَّيان، ووحدةٌ تُختار بالسؤال**.

**العِلّة (مقيسة):** سؤالُ الحزمة «كم صفًّا في الكشف كُتب تاريخُه بأرقامٍ عربيّةٍ-هندية؟» انتهى **بمهلة**
مرّتين: لا سبيلَ للعدّ بترميز التاريخ ⇒ الوكيلُ يستنطق ٥٧٩٢ صفًّا بأدواته.

**والقياسُ كشف ثلاثَ دلالاتٍ لا واحدة** (وهذا هو الدرس): ① **الحاكم** يعدّ حقلَ `date` **المخزَّن**
(المجموعتان معًا: ٥٦٦٢) ② و**المطبوع** في صدر الوصف مجموعةٌ أخرى (٣٤٠٧) ③ و**الوحدة**: الحاكم يعدّ
**صفوفًا** والأداةُ كانت تعدّ **حركات** (فارقُ ٣ صفوفٍ في هذا الكشف). فصار المعياران مُسمَّيين صراحةً،
ووحدةُ العدّ تُختار بالسؤال — **ويُعلَن في الجواب أيُّهما عُدّ**.
"""

from __future__ import annotations

import pytest
from decimal import Decimal

# **والحارسُ على التبعيّات لا على الاستيراد** (نمطُ `test_answer_type` المُثبت): `qa_tools` تُزيّن
# أدواتها بـ`@tool` من LangChain ⇒ ففي بيئة الـCI الخفيفة **يسقط الاستيراد** فتُخطَأ المجموعةُ كلُّها
# (قِيس: ٤/٤ فاشلة في `ci-light` و`ci-claims`) — وكان الملفُّ **خارج قائمة الـCI** فيفشل **صامتًا**.
_DEPS = []
for _mod in ("langchain",):
    try:
        __import__(_mod)
    except ImportError:                           # noqa: PERF203
        _DEPS.append(_mod)
pytestmark = pytest.mark.skipif(
    bool(_DEPS), reason=f"أدواتُ الطبقة تحتاج {'، '.join(_DEPS)} — تُقاس في البيئة الكاملة")

from statement_qa.qa_tools import make_qa_tools


def _row(page: int, desc: str, stored: str | None, kind: str = "txn", side: str = "credit") -> dict:
    return {"page": page, "kind": kind, "balance": Decimal("100.00"),
            "movement": None if kind != "txn" else Decimal("10.00"),
            "side": side, "ok": True, "desc": desc, "date": stored}


# المطبوع: عربيٌّ-هنديّ (U+0660) للصفّين ١-٢ · ممتدّ (U+06F0) للصفّ ٣ · لاتينيّ ٤ · بلا ٥
# والمخزَّن: ممتدٌّ للصفوف ١-٣ · بلا للصفّين ٤-٥ · **والصفُّ ٦ ليس حركة** (افتتاحٌ بمخزَّنٍ عربي-هنديّ)
ROWS = [
    _row(1, "١٤٣٥٠١١٨ تحويل وارد", "۲۰۱۳۱۱۰۸"),      # مطبوع: عربي-هندي · مخزَّن: ممتد
    _row(1, "١٤٣٥٠١١٩ سحب", "۲۰۱۳۱۱۰۹"),              # مطبوع: عربي-هندي · مخزَّن: ممتد
    _row(2, "۲۰۱۳۱۱۰۸ تحويل", "۲۰۱۳۱۱۰۸"),             # مطبوع: ممتد
    _row(2, "14350118 transfer", None),                # مطبوع: لاتينيّ · مخزَّن: بلا
    _row(3, "سحب الصراف الآلي", None),                 # بلا تاريخٍ مطبوع
    _row(3, "رصيد سابق ١٤٣٥٠١٢٠", "۲۰۱۳۱۱۱۰", kind="opening"),   # **صفٌّ لا حركة**
]


def _count(**kw) -> str:
    return {t.name: t for t in make_qa_tools(ROWS)}["count_movements"].invoke(kw)


def _n(**kw) -> int:
    return int(_count(**kw).split("العدد = ")[1].split(" ")[0])


def test_the_two_encodings_are_separate_notions() -> None:
    """**المخزَّنُ ليس المطبوع:** ستّةُ صفوفٍ تُعطي ٤ مخزَّنًا عربيًّا-هنديًّا و٢ مطبوعًا كذلك.

    الثمنُ إن سقط: يُخلط الرقمان (٥٦٦٢ مقابل ٣٤٠٧ في الكشف الحقيقيّ) — وكلاهما «صحيحُ الشكل».
    """
    assert _n(date_encoding="arabic_ind") == 4, _count(date_encoding="arabic_ind")
    assert _n(printed_date_encoding="arabic_ind") == 2, _count(printed_date_encoding="arabic_ind")


def test_the_unit_follows_the_question_rows_not_movements() -> None:
    """**وحدةُ العدّ تُعلَن:** سؤالُ التاريخ يعدّ **الصفوف** (ومنها صفٌّ ليس حركة) — والافتراضُّ الحركات.

    الثمنُ إن سقط: فارقُ ٣ صفوفٍ في الكشف الحقيقيّ (٥٦٦٢ مقابل ٥٦٥٩) ⇒ جوابٌ لا يطابق سؤالَه.
    """
    assert _n(date_encoding="arabic_ind") == 4          # صفوف: ١،٢،٣ + الافتتاح
    assert _n() == 5                                    # حركات: خمسٌ فقط
    assert _n(printed_date_encoding="arabic_ind") == 2  # والصفُّ الافتتاحي مطبوعُه عربيٌّ-هنديّ أيضًا؟ لا
    assert "صفًّا" in _count(date_encoding="arabic_ind"), "الوحدةُ لا تُعلن في الجواب"
    assert "حركة" in _count(), "الافتراضُّ (بلا معيار) يبقى الحركات"


def test_every_notion_partitions_its_rows() -> None:
    """**تغطيةٌ لا فجوة:** لكلّ معيارٍ تُجمع مجموعاتُه إلى عدد الصفوف/الحركات نفسه."""
    stored = {e: _n(date_encoding=e) for e in ("arabic_ind", "latin", "none")}
    printed = {e: _n(printed_date_encoding=e) for e in ("arabic_ind", "extended", "latin", "none")}
    assert stored == {"arabic_ind": 4, "latin": 0, "none": 2}, stored
    assert sum(stored.values()) == len(ROWS)
    assert printed == {"arabic_ind": 2, "extended": 1, "latin": 1, "none": 2}, printed
    assert sum(printed.values()) == len(ROWS), "فجوةٌ: صفٌّ لم يُعدَّ في أيّ مجموعة"


def test_the_filters_compose_and_declare_their_scope() -> None:
    """**والقدرةُ تُركَّب:** معيارُ التاريخ فلترٌ كسائر الفلاتر — ويُعلن نطاقُه في الجواب."""
    assert _n(side="credit", date_encoding="arabic_ind") == 4
    assert _n(side="debit", date_encoding="arabic_ind") == 0
    out = _count(date_encoding="arabic_ind")
    assert "ترميزُ التاريخ المخزَّن = arabic_ind" in out, out
    assert "ترميزُ التاريخ المطبوع = arabic_ind" in _count(printed_date_encoding="arabic_ind")
