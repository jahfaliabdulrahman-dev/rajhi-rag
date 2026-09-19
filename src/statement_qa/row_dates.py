"""تواريخ الصفوف: من خانة التاريخ، أو من نصّ السطر نفسه — بتسمية المصدر لا بتخمينه.

القاعدة (من عقد القبول القديم، ٦·٢): **التاريخ من الصفّ نفسه فقط** — لا صفّ يأخذ
تاريخ جاره أبداً. وهذا الملف يبقى داخل القاعدة: التاريخ من الخانة، فإن فرغت فمن
نصّ السطر **نفسه** (حيث يطبع البنك التاريخ الميلادي والهجري داخل وصف الحركة)،
وإن لم يوجد فليس حركة (سطر رصيد افتتاحي أو عنوان ملخّص) أو مفقود معلن.

ولا يُخفى المصدر: كل تاريخ يحمل `date_source` — ولهذا يُصدَّر في ورقة الحركات
بعمود «حالة التاريخ» بلفظه (من الخانة / من نصّ السطر / ليس حركة / بلا تاريخ).
"""
from __future__ import annotations

import re

_D8 = re.compile(r"[0-9٠-٩۰-۹]{8}")
_DSEP = re.compile(r"^([0-9٠-٩۰-۹]{4})[/\-\.]([0-9٠-٩۰-۹]{1,2})[/\-\.]([0-9٠-٩۰-۹]{1,2})$")
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
# أسطر الورق التي ليست حركة: أرصدة افتتاحية وعناوين ملخّصات.
_NOT_MOVEMENT = ("الرصيد الافتتاح", "الحوالات الواردة", "الحوالات الصادرة",
                 "اجمالي", "إجمالي", "المجموع", "الملخص", "عدد العمليات")


def ascii_digits(value: str) -> str:
    """أرقام عربية-هندية وفارسية ⇒ لاتينية (بلا مسّ غير الأرقام)."""
    return str(value).translate(_AR)


def plausible_gregorian(run: str) -> bool:
    """2013-11-32 ليس تاريخاً: السنة معقولة والشهر واليوم في مداهما."""
    if len(run) != 8 or not run.isdigit():
        return False
    y, m, d = int(run[:4]), int(run[4:6]), int(run[6:8])
    return 1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31


def parse_cell(value) -> str:
    """خانة التاريخ ⇒ ``YYYYMMDD`` أو ''. تقبل 8 أرقام أو صيغة بفواصل.

    القارئ يعيد أحياناً ``2016/08/08`` وأحياناً ``20160808`` — ورفضُ إحداهما
    يُعلن نقصاً كاذباً (وقع فعلاً: 117 صفّاً ظُنّت بلا تاريخ وهي تحمله).
    """
    text = ascii_digits(str(value or "").strip())
    if not text or text.lower() in {"none", "null", "nan"}:
        return ""
    if plausible_gregorian(text):
        return text
    m = _DSEP.match(text)
    if m:
        yyyy, mm, dd = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        joined = f"{yyyy}{mm}{dd}"
        return joined if plausible_gregorian(joined) else ""
    return ""


def _plausible_hijri(run: str) -> bool:
    """مدى التقويم الهجري — لأن سنة ١٤٤٣ لا تمرّ من مدى الميلادي (وقد مرّت المشكلة)."""
    if len(run) != 8 or not run.isdigit():
        return False
    y, m, d = int(run[:4]), int(run[4:6]), int(run[6:8])
    return 1300 <= y <= 1500 and 1 <= m <= 12 and 1 <= d <= 30


def text_dates(desc: str) -> tuple[str | None, str | None]:
    """(ميلادي، هجري) من نصّ السطر — أول مرشّح معقول لكلٍّ منهما."""
    greg = hij = None
    for raw in _D8.findall(ascii_digits(desc or "")):
        if greg is None and raw[:2] in ("19", "20") and plausible_gregorian(raw):
            greg = raw
        elif hij is None and raw[:2] == "14" and _plausible_hijri(raw):
            hij = raw
    return greg, hij


def is_not_movement(desc: str) -> bool:
    """سطر رصيد افتتاحي أو عنوان ملخّص — لا يُطالب بتاريخ حركة."""
    text = (desc or "").strip()
    return any(text.startswith(k) or text == k for k in _NOT_MOVEMENT)


def resolve(row: dict) -> dict:
    """يُصنّف تاريخ الصفّ ويُعلن مصدره. لا يُغيّر الورق: يقرأه فقط.

    يُرجع {"date", "date_source", "date_text_mismatch"}:
      - `cell`           خانة التاريخ في الورق
      - `text`           التاريخ مطبوع داخل وصف نفس السطر (يُصدَّر بلفظه)
      - `not_a_movement` سطر ليس حركة
      - `missing`        لا تاريخ في الخانة ولا في النصّ ⇒ يُعلن نقصاً
    """
    cell = parse_cell(row.get("date"))
    greg, _hij = text_dates(str(row.get("desc") or ""))
    if cell:
        return {"date": cell, "date_source": "cell",
                "date_text_mismatch": bool(greg and greg != cell)}
    if greg:
        return {"date": greg, "date_source": "text", "date_text_mismatch": False}
    if is_not_movement(str(row.get("desc") or "")):
        return {"date": None, "date_source": "not_a_movement",
                "date_text_mismatch": False}
    return {"date": None, "date_source": "missing", "date_text_mismatch": False}
