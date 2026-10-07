"""**صفوفُ عقد الدفتر** (`ledger.COLUMNS` · ٢٢ عمودًا) — تُبنى في **موضعٍ واحد** يقرؤه مساران:

* سطرُ الأوامر: `tools.to_xlsx.load` يقرأ كاشَ التشغيل (`results/pg-*.json`) ثمّ ينادي هنا؛
* والتطبيق: `app.py` ينادي هنا ببياناته في الذاكرة (قراءاتُه وأحكامُه وأرقامُه المطبوعة).

**ولماذا في `statement_qa` لا في `tools/`:** مدخلاتُه **وسائطُ لا ملفّات** — فالتطبيقُ لا يكتب كاشَ
`results/`، ولا يجوز أن يُلزَم بكتابته ليجد ما يقرؤه (والكاتبُ يقرأ ما يكتبه غيره: نسختان تزيغان صامتتين).

**والعلّةُ المقيسة (قرارُ المالك 2026-10-07 · الخيار (أ) · مراجعة ٩٦):** صفوفُ التطبيق كانت **٩ حقولٍ من
٢٢** ⇒ فزرُّ التنزيل **لا يُنتج ملفًّا**:
`IntegrityError: NOT NULL constraint failed: rows_verified.row_no` (على `main`)، ثمّ `KeyError: None`
عند `tools/to_xlsx.py:995` بعد ترقيم الصفوف — قِيسا بالتنفيذ، وكلٌّ منهما من غياب العقد لا من عطبٍ سطريّ.
"""
from __future__ import annotations

from decimal import Decimal

from statement_qa.row_audit import DEBIT_ONLY_DESCRIPTIONS

#: الوصفُ الذي لا يكون دائنًا في هذا الكشف — تُقرأ في `_shift_suspect`.
DEBIT_ONLY = DEBIT_ONLY_DESCRIPTIONS

_DIGIT_MAP = {chr(0x0660 + i): str(i) for i in range(10)}
_DIGIT_MAP.update({chr(0x06F0 + i): str(i) for i in range(10)})


def to_ascii_digits(raw: str) -> str:
    """كل مجموعات الأرقام → لاتينية. الصيغة المختلطة تُطبَّع بلا استثناء."""
    return "".join(_DIGIT_MAP.get(ch, ch) for ch in raw)


def normalize_date(raw: str | None) -> tuple[str, str, int | None]:
    """(ISO date | '', status, year) — YYYYMMDD كما طُبع، بمجموعة أرقام أيّاً كانت.

    Returns `iso=''` when the value cannot honestly be called a date; the status
    says which kind of failure it is, so the summary can count them instead of
    hiding them behind an empty cell.
    """
    if raw is None or not str(raw).strip():
        return "", "missing", None
    digits = "".join(ch for ch in to_ascii_digits(str(raw)) if ch.isdigit())
    if len(digits) != 8:
        return "", "incomplete", None
    year, month, day = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
    if not (1900 <= year <= 2100) or not (1 <= month <= 12) or not (1 <= day <= 31):
        return "", "implausible", None
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}", "ok", year


def _dec(value) -> Decimal | None:
    """الرقم كـDecimal — السلسلة تعمل بـDecimal لا بنصوص."""
    if value is None:
        return None
    try:
        return Decimal(str(to_ascii_digits(str(value)).replace(",", "")))
    except (ArithmeticError, ValueError):
        return None


def _num0(value) -> Decimal | None:
    """القيمة كـDecimal للجمع والمقارنة (لا للعرض)."""
    return _dec(value)


def _row_state(der: dict) -> str:
    """حكم السلسلة على الصفّ — بصياغة يقرؤها محاسب لا مبرمج."""
    if der.get("balance") is None:
        return "بلا رصيد مقروء — خارج السلسلة"
    mv = der.get("derived_movement")
    if mv is None:
        return "بلا حركة مقروءة"
    if der.get("opening"):
        return "رصيد مرحّل/افتتاحي (ليس حركة)"
    if Decimal(str(mv)) == 0:
        # سطر إجماليات قرأه القارئ صفّاً: لا فرق رصيد فيه، ومبلغه المطبوع
        # (الإجمالي التراكمي) لا يساوي صفراً ⇒ يُسمّى بما هو لا بما ظهر به.
        note = (" — ومبلغه المطبوع لا يطابق فرق الرصيد (إجماليات مُقروءة حركة)"
                if der.get("ok") is False else "")
        return f"لا حركة فيه: سطر إجماليات أو صفّ مكرّر{note}"
    if der.get("ok") is False:
        return "مشكوك: المبلغ المطبوع لا يطابق فرق الرصيد"
    return "حركة مثبتة بالسلسلة"


def _assertion_source(state: str, page_flags: dict) -> str:
    """من أين جاء **إثبات** الحركة — يُعلن بلفظه، ولا يُستنتج من اسم العمود.

    المشكلة (رفعها مدقّق خارجي): عمود «الحركة المثبتة بالسلسلة» يحمل في مرساة
    الفجوة **المبلغ المطبوع**، لأن السلسلة لا تُقفل صفّاً يبتلع فرقُ رصيده ورقةً
    غائبة. فالقيمة صحيحة والعمود يكذب عليها. والعلاج صنفٌ لا صفّان: عمود يعلن
    مصدر الإثبات لكل حركة، ويُنسب إصلاح القراءة (استدراك/إعادة قراءة/تحكيم)
    إلى صفحته — فالصفوف المستدركة كانت صامتة عن أن رصيدها من قراءةٍ مصلَحة.
    """
    if state.startswith("حركة — مرساة"):
        base = ("الورق المطبوع: مبلغ المرساة — ولا تُقفلها السلسلة "
                "(ورقة غائبة قبلها فلا رصيد سابق)")
    elif state.startswith("حركة مثبتة"):
        base = "السلسلة: فرق رصيدين متتاليين"
    else:
        return ""                      # ليست حركة: لا مصدر إثبات يُطلب منها
    read = []
    if page_flags.get("recovered"):
        read.append("استدراك آلي (قيمة متوقَّعة من دلتا التذييل)")
    if page_flags.get("reread"):
        read.append("إعادة قراءة محكَّمة")
    if page_flags.get("arbitrated"):
        read.append("تحكيم موثَّق بمصدره (قيمة مطبوعة قُرئت بعين)")
    return base + (" · القراءة: " + " + ".join(read) if read else "")


def _shift_suspect(row: dict, der: dict) -> str:
    """وصف لا يمكن أن يكون دائناً + مبلغ دائن ⇒ الوصف أُزيح عن مبلغه."""
    if der.get("side") != "credit":
        return ""
    desc = str(row.get("desc") or "")
    hit = next((d for d in DEBIT_ONLY if d in desc), None)
    return (f"الوصف «{hit}» لا يكون دائناً في هذا الكشف — الوصف أُزيح عن مبلغه"
            if hit else "")


def _row_date_source(row: dict) -> str:
    """مصدر تاريخ الصفّ بحكم القانون — لا بالتخمين."""
    from statement_qa.row_dates import resolve
    try:
        return str(resolve(row)["date_source"])
    except Exception:                                    # noqa: BLE001
        return "unknown"


def build_page_rows(page: int, raw_rows: list[dict], derived: list[dict],
                    verdict: dict | None, page_flags: dict,
                    page_no=None) -> list[dict]:
    """**صفوفُ صفحةٍ واحدة بعقد الدفتر** — الدالّةُ الوحيدة التي تبني العقد.

    الوسائطُ صريحةٌ لا ملفّات، فيناديها الطريقان ببياناتهما:
    `raw_rows` كما قرأها القارئ · `derived` أحكامَ السلسلة لكل صفّ (وقد تكون هي نفسَها
    حين يحمل القارئُ الحكمَ معه) · `verdict` حكمَ الصفحة (`footer` و`rows`) ·
    `page_flags` أعلامَ الصفحة (`recovered`/`reread`/`arbitrated` — يقرؤها `_assertion_source`) ·
    `page_no` **الرقمَ المطبوع** كما قُرئ من الورقة (لا يُخترع: يبقى `None` إن لم يُقرأ).
    """
    verdict = verdict or {}
    out: list[dict] = []
    for i, (row, der) in enumerate(zip(raw_rows, derived), start=1):
        iso, status, year = normalize_date(row.get("date"))
        # **سطرٌ بلا رصيد مطبوع ليس حركة**: كل حركة في هذا الكشف تحمل رصيداً
        # جارياً؛ والذي لا يحمله هو سطر ملخّص الحساب (اجمالي الايداعات ·
        # اجمالي السحوبات · رصيد الاقفال …) أو الرصيد الافتتاحي. ووسمه هنا
        # يُخرجه من «الحركات» ومن «بلا تاريخ» ومن «ما لم يُثبت» معاً —
        # وهو بريء من الثلاثة: لا سلسلة تُقاس عليه ولا تاريخ يُطلب منه.
        is_movement = row.get("balance") is not None
        if not is_movement and status == "missing":
            status = "not_a_movement"
        # **مرساةُ فجوة**: مبلغٌ مطبوع ورصيدٌ مطبوع ⇒ حركة فعليّة، لكن فرق
        # الرصيد يبتلع ورقةً غائبة فلا تُقفله السلسلة. ووسمُها «ليس حركة»
        # كان خطأً يُنكر حركةً مبصوطة على الورق.
        state = ("حركة — مرساة بعد ورقة غائبة (المبلغ مطبوع ولا تُقفله السلسلة)"
                 if (is_movement and der.get("opening")
                     and _num0(row.get("movement")))
                 else (_row_state(der) if is_movement
                       else "سطر ملخّص/افتتاحي — ليست حركة"))
        out.append({
            "page": page,
            "row_no": i,
            "printed_page": page_no,
            "date": row.get("date"),
            "date_iso": iso,
            "date_status": status,
            # مصدر التاريخ: من خانة الورق أو من نصّ السطر نفسه (تعميم لاحق على
            # صفحات قُرئت قبل وجود القانون) — يُعرض بلفظه في ورقة الحركات.
            # لا يُختلق مصدر: إن لم يُعلن الكاش مصدراً نسأل قانون
            # التواريخ عن الصفّ نفسه (قد يكون missing أو ليس حركة)
            # — وإلا كُتب «من خانة الورق» على صفّ لا تاريخ له (كشفه مدقّق خارجي).
            "date_source": str(row.get("date_source")
                               or _row_date_source(row)),
            "year": year,
            "desc": row.get("desc"),
            # ⚠️ بنية الكاش (تُقرأ قبل أي إصلاح يمسّها): المجلد `results/` يحمل
            # ملفات `pg-NNN.json` وصفوفها تحت المفتاح **`raw_rows`** — لا `rows`.
            # وقراءة المفتاح الخطأ تُرجع [] بصمت ⇒ إصلاحات «ناجحة» بلا صفّ واحد
            # (وقع: ثلاث محاولات لتصحيح خطّ عمود «كما طُبعت» أنتجت صفراً).
            "printed_movement": row.get("raw_movement") or row.get("movement"),
            "printed_balance": row.get("raw_balance") or row.get("balance"),
            "movement": row.get("movement"),
            "balance": row.get("balance"),
            # **مرساة الفجوة**: السلسلة لا تُقفل صفّاً يبتلع فرقُ رصيده ورقةً
            # غائبة، فيبقى `derived_movement` صفراً والورق يطبع ٢٥.٠٠ ⇒ تناقضٌ
            # داخلي بين عمودين (رفعه مدقّق ثلاث مرات). والصواب: المرساة تُثبت
            # **مبلغها المطبوع** بنفسها — ولا يدخل «مدين/دائن» فلا تتغيّر المجاميع
            # (الفجوة محسوبة في قيودها المستقلّة)، والوسم يبقى في «حكم السلسلة».
            "derived_movement": (_num0(row.get("movement"))
                                 if (is_movement and der.get("opening")
                                     and _num0(row.get("movement")))
                                 else der.get("derived_movement")),
            "side": der.get("side") or "",
            "opening": bool(der.get("opening")),
            "chain_ok": der.get("ok"),
            "row_state": state,
            "source": _assertion_source(state, page_flags),
            "shift": _shift_suspect(row, der),
            "footer": verdict.get("footer"),
            "counted": verdict.get("rows"),
        })
    return out
