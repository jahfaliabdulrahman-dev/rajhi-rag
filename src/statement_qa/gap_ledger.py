"""قيود الفجوة: الأوراق الغائبة من المسح تُحسَب لا تُفترض.

المشكلة التي يحلّها
-------------------
الورق الغائب من المسح (٤ أوراق في حالة الراجحي) يحمل حركات **مطبوع تأثيرها** في
التذييل التراكمي وفي الأرصدة العابرة، لكن صفوفه غير موجودة عندنا. فمجموع صفوفنا
أقلّ من ملخص البنك بمقدار حركاته، والهوية الحسابية `افتتاح + Σدائن − Σمدين =
الإقفال` تنكسر بمقدار **صافي** تلك الأوراق — وهو ليس صفراً بالضرورة.

العلاج: قيد مسمّى لكل مجموعة أوراق غائبة، بمقدارَيْه من **زيادتَي التذييل
المطبوع**، و**شاهد مستقل**: عبور الرصيد بين آخر رصيد مطبوع قبل الفجوة وأول رصيد
بعدها. الشاهدان يجب أن يتفقا على الصافي — فإن اختلفا فالقيد غير مُثبت ولا يُدرج
كأنه حقيقة، بل يُعلَّم.

لماذا لا "صافي صفر"
-------------------
افتراض أن الأوراق الغائبة متعادلة (مدين == دائن) يُغلق الهوية بالبناء لا
بالقياس. في حالة الراجحي كذّبه الرصيد: العبور المقيس +1,453.52 بينما الافتراض
يقتضي 0.00 — أي أن الأوراق الغائبة كان صافيها دائناً.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

TOL = Decimal("0.01")


@dataclass
class PageFacts:
    """ما نعرفه عن صفحة ممسوحة — من الورق ومن حسابنا."""

    page: int
    printed: dict[str, Decimal] = field(default_factory=dict)   # التراكمي كما طُبع
    own: dict[str, Decimal] = field(default_factory=dict)       # مجموعنا بالسلسلة
    first_balance: Decimal | None = None
    last_balance: Decimal | None = None
    missing_sheets: tuple[int, ...] = ()


def _d(v) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v).replace(",", ""))
    except (ArithmeticError, ValueError):
        return None


def build_gap_entries(facts: list[PageFacts]) -> list[dict]:
    """يُخرج قيداً لكل مجموعة أوراق غائبة، بمقدارَيْه وشاهده المستقل.

    القيد يُدرج **فقط** إذا توفّر: التذييل التراكمي للصفحة السابقة، والتذييل
    التراكمي للصفحة التالية للفجوة، ومجموع الأخيرة بحسابنا، ورصيدا الحدّين.
    وإلا يُعاد قيد بحالة `unproven` — يُذكر ولا يُحتسب.
    """
    entries: list[dict] = []
    for i, cur in enumerate(facts):
        if not cur.missing_sheets:
            continue
        prev = facts[i - 1] if i else None
        gap = {"after_page": prev.page if prev else None,
               "before_page": cur.page,
               "missing_sheets": list(cur.missing_sheets),
               "debits": None, "credits": None, "net": None, "crossing": None,
               "witnesses_agree": False, "status": "unproven",
               "note": ""}
        if prev is None or not prev.printed or not cur.printed:
            gap["note"] = "لا تذييل مطبوع قبل الفجوة — يتعذّر عزل حركات الأوراق الغائبة"
            entries.append(gap)
            continue
        inc_d, inc_c = _d(cur.printed.get("debits")), _d(cur.printed.get("credits"))
        pre_d, pre_c = _d(prev.printed.get("debits")), _d(prev.printed.get("credits"))
        if inc_d is None or inc_c is None or pre_d is None or pre_c is None:
            gap["note"] = "تذييل تراكمي ناقص — لا يُحتسب القيد"
            entries.append(gap)
            continue
        own_d = _d(cur.own.get("debits")) or Decimal("0")
        own_c = _d(cur.own.get("credits")) or Decimal("0")
        gap["debits"] = (inc_d - pre_d) - own_d
        gap["credits"] = (inc_c - pre_c) - own_c
        gap["net"] = gap["credits"] - gap["debits"]
        if prev.last_balance is not None and cur.first_balance is not None:
            gap["crossing"] = cur.first_balance - prev.last_balance
            gap["witnesses_agree"] = abs(gap["crossing"] - gap["net"]) <= TOL
            gap["status"] = "proven" if gap["witnesses_agree"] else "disagreed"
            if not gap["witnesses_agree"]:
                gap["note"] = ("الشاهدان اختلفا: زيادة التذييل تقول صافياً "
                               f"{gap['net']} وعبور الرصيد يقول {gap['crossing']}")
        else:
            gap["note"] = "رصيد حدّي غير مقروء — الشاهد الثاني غائب"
        entries.append(gap)
    return entries


def debit_credit(movement, side: str) -> tuple[Decimal | None, Decimal | None]:
    """الصفّ → (مدين، دائن) كما يطبع البنك: عمودان موجبان لا إشارات."""
    v = _d(movement)
    if v is None or v == 0:
        return None, None
    if side == "debit":
        return v, None
    if side == "credit":
        return None, v
    return None, None


def identity(opening, debits, credits) -> Decimal:
    """افتتاح + Σدائن − Σمدين — يُقارن بالإقفال المطبوع."""
    return (_d(opening) or Decimal("0")) + (_d(credits) or Decimal("0")) \
        - (_d(debits) or Decimal("0"))
