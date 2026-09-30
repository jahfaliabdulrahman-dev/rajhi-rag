"""بناءُ «التذييلات المطبوعة» بصيغةٍ واحدة — يستهلكه التطبيقُ ومسارُ القياس (R77 · مراجعة ٧٧).

**العلّةُ التي وُلد منها هذا الملفّ:** التطبيقُ كان يبني هذه البنية **داخل حلقة القراءة** في `app.py`،
فلا يستطيع مستهلكٌ آخر (حِيازةُ قياسٍ أو أداة) إنتاجَها بالصيغة نفسِها إلا بنسخِها ⇒ **ونسخةٌ ثانيةٌ
تزيغ بصمت**. فالصيغةُ الآن هنا، ويرثها الطرفان من مصدرٍ واحد.

**العقدُ:** لكلّ صفحةٍ `{page, debits, credits, balance, verdict, basis}` — والأرقامُ **كما ظهرت في
الورقة** (نصًّا)، ولا تُعاد للجمع ولا تُخمَّن. وقيمةٌ لم تُقرأ تبقى `None` ⇒ الأداةُ تسمّيها `لم يُقرأ`.
"""
from __future__ import annotations

FIELDS = ("debits", "credits", "balance")


def _as_text(value, money=None):
    """نصٌّ كما هو، أو رقمٌ بصيغة العرض — و`None` يبقى `None` (يُعلَن لا يُخمَّن)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return (money or str)(value)


def _field(reading, name: str, money=None):
    if reading is None:
        return None
    if isinstance(reading, dict):
        return _as_text(reading.get(name), money)
    return _as_text(getattr(reading, name, None), money)


def printed_footers_from(readings: dict, checks, money=None) -> dict:
    """`{page: {...}}` من قراءاتٍ (`FooterReading` أو `dict`) وأحكامٍ (قائمةُ `footer_checks` أو خريطة).

    `checks` تُقبل بصيغتَي المستهلكَين القائمين: قائمةُ `app.py` (`{page, status, basis}`) وقائمةُ
    `slice_report.json` (`per_page` بمفتاح `footer` للوضع) — فالمصدرُ واحدٌ والصيغةُ واحدة.
    """
    if isinstance(checks, dict):
        by_page = {int(k): v for k, v in checks.items()}
    else:
        by_page = {int(c["page"]): c for c in (checks or []) if c.get("page") is not None}
    out: dict[int, dict] = {}
    for pg, reading in (readings or {}).items():
        pg = int(pg)
        chk = by_page.get(pg) or {}
        out[pg] = {
            "page": pg,
            "debits": _field(reading, "debits", money),
            "credits": _field(reading, "credits", money),
            "balance": _field(reading, "balance", money),
            "verdict": str(chk.get("status") or chk.get("footer") or "unchecked"),
            "basis": str(chk.get("basis") or chk.get("note") or ""),
        }
    return out
