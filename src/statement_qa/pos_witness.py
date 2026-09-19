"""الشاهد الموضعي: عمودُ المبلغ من **هندسة الورق** لا من قول النموذج.

لماذا هذا الشاهد
----------------
قارئنا يقرأ العمود ويقول «مدين/دائن»، وقد أخطأ مرة في 5,607 صفّاً. والسلسلة تكشف
الخطأ لكنها **داخلية** (فرق رصيدين). فهذا الشاهد مستقلّ تماماً: يكفي أن يقول
النموذج **أين** المبلغ أفقياً، ونقارن الموضع بمواضع العمودين ⇒ العمود يُشتقّ
حسابياً. والقياسات التي بُني عليها:

* إحداثيات النموذج **معيارية** (0..1): عند طلب البكسل المطلق أعطى فضاءً آخر
  (≈0.63 من الأصل)؛ وبالنسبة صار 0.440 ⇒ 728px وهو موضع عمود السحب في الورق.
* إحداثيات النموذج **تقريبية**: خطؤها المقيس 35–105 بكسل — فبلا سنٍّ محلي لم يكن
  تحت 7 من 11 إطاراً أيّ حبر. والسنّ هو ما يحوّل «زعم» إلى «إثبات».
* والصيغة **سطرية** لا JSON: JSON انقطع بسقف المخرَج مرتين وضاع الجواب كله.
"""
from __future__ import annotations

import re
from decimal import Decimal

Row = dict

PROMPT = (
    "انسخ ولا تفسّر. أعد **سطوراً نصّية فقط**، بلا JSON وبلا شرح وبلا مقدمات.\n"
    "السطر الأول للأعمدة:\n"
    "COLS|debit_x=<مركز عمود السحب>|credit_x=<مركز عمود الإيداع>|balance_x=<مركز عمود الرصيد>\n"
    "ثم سطر لكل حركة من أعلى الصفحة إلى أسفلها بالصيغة:\n"
    "ROW|<نص التاريخ>|<x المبلغ>|<y الصف>|<نص المبلغ>|<نص الرصيد>\n"
    "لا تُدرج الوصف: الشاهد يحتاج الموضع والمبلغ والرصيد فقط — والوصف مأخوذ عندنا.\n"
    "كل الإحداثيات **نسبية من 0 إلى 1** (x من العرض، y من الارتفاع)، ثلاث خانات عشرية.\n"
    "x المبلغ = مركزه أفقياً · y الصف = مركز الصف عمودياً. لا تكتب أي شيء آخر."
)

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
INK_THRESHOLD = 185          # الورق هنا نقطي باهت: العتبة مقيسة (صفحة ≈ 249)
INK_MIN = 0.02               # أدنى نسبة حبر تُعدّ إثباتاً لإطار


def parse_lines(text: str) -> tuple[dict[str, float], list[Row]]:
    """مخرَج الشاهد ⇒ (أعمدة، صفوف). السطر المقطوع يُسقط سطراً لا الجواب كله."""
    cols: dict[str, float] = {}
    rows: list[Row] = []
    for raw in str(text or "").splitlines():
        line = raw.strip().strip("`").strip()
        if line.startswith("COLS|"):
            for part in line.split("|")[1:]:
                key, _, value = part.partition("=")
                try:
                    cols[key.strip()] = float(value.strip())
                except ValueError:
                    continue
        elif line.startswith("ROW|"):
            f = [x.strip() for x in line.split("|")[1:]]
            if len(f) < 5:
                continue
            try:
                rows.append({"date": f[0], "x": float(f[1]), "y": float(f[2]),
                             "amount": f[3], "balance": f[4]})
            except ValueError:
                continue                  # سطر مقطوع أو تالف: يُتخطّى بصمتٍ معدود
    return cols, rows


def assign_column(x: float, cols: dict[str, float]) -> str | None:
    """العمود من الموضع الأفقي: أقرب عمود إلى مركز المبلغ."""
    cand = {k: v for k, v in cols.items() if k in ("debit_x", "credit_x")}
    if not cand:
        return None
    near = min(cand, key=lambda k: abs(x - cand[k]))
    return near.replace("_x", "")


def to_decimal(value) -> Decimal | None:
    """أرقام عربية-هندية وفواصل ⇒ Decimal. الفاصلة العشرية العربية «٫» فاصلةٌ لا تُرمى.

    (كشفها اختبار: رمي «٫» كان يحوّل ٠٫٥٠ إلى 050 ⇒ 50. الرقم لا يُقرأ بلا فاصلة.)
    """
    text = (str(value).replace("٫", ".").replace("٬", "").replace("،", "")
            .translate(_DIGITS))
    text = re.sub(r"[^0-9.]", "", text)
    if not text or text.count(".") > 1:
        return None
    try:
        return Decimal(text)
    except ArithmeticError:
        return None


def chain_side(previous_balance, balance) -> str | None:
    """الاتجاه من السلسلة: الرصيد ينخفض ⇒ مدين · يرتفع ⇒ دائن · لا يتحرك ⇒ None."""
    a, b = to_decimal(previous_balance), to_decimal(balance)
    if a is None or b is None or a == b:
        return None
    return "debit" if a > b else "credit"


def compare_with_chain(rows: list[Row], cols: dict[str, float],
                       previous_balance=None) -> dict:
    """مقابلة الهندسة بالسلسلة ⇒ توافق/خلاف/غير محسوم + الصفوف المخالفة بأرقامها.

    و``previous_balance`` يُدخل **الصفّ الأول من كل صفحة** في المقابلة: بدونه كان
    ``range(1, …)`` يُخرج أوّل صفّ في كل صفحة من شاهدين من ثلاثة (٦٢٩ صفّاً، ومنها
    مرساتا الفجوة) — وهذا ما لاحظه مدقّق خارجي: كلّ عيوب الأوسمة كانت صفوفاً أُوَل.
    """
    agree = clash = undetermined = 0
    clashes = []
    pairs = []
    if previous_balance is not None and rows:
        pairs.append((previous_balance, rows[0], 1))
    for i in range(1, len(rows)):
        pairs.append((rows[i - 1].get("balance"), rows[i], i + 1))
    for prev_bal, row, idx in pairs:
        side = chain_side(prev_bal, row.get("balance"))
        xs = row.get("x")
        col = assign_column(float(xs), cols) if isinstance(xs, (int, float)) else None
        if side is None or col is None:
            undetermined += 1
        elif side == col:
            agree += 1
        else:
            clash += 1
            clashes.append({"row": idx, "chain": side, "geometry": col,
                            "amount": row.get("amount")})
    return {"agree": agree, "clash": clash, "undetermined": undetermined,
            "clashes": clashes}


def snap_point(arr, x: int, y: int, ink_frac,
               win: tuple[int, int] = (150, 34),
               radius: tuple[int, int] = (120, 35),
               step: int = 5, margin: float = 0.002) -> tuple[int, int, float]:
    """أقرب كتلة حبر حول النقطة المزعومة — حتمي، بلا نموذج.

    إحداثيات النموذج تقريبية (35–105 بكسل خطأً مقيساً)، والسنّ هو الذي يجعل
    الإطار يقع على حبر فعلاً. ولو قُبل الزعم كما هو لكان الشاهد كاذباً في 7 من 11.

    **والمرشّحون يُفحصون بترتيب الإزاحة، والانتقال يشترط تحسّناً بمقدار ``margin``**:
    فحين يتساوى الحبر في هضبةٍ من المواضع (نافذة أوسع من الكتلة)، لا يُزاح الإطار
    بلا موجب — وهذا عيب كشفه اختبار (كان يقفز 120 بكسل إلى أول موضع متعادل).
    """
    candidates = sorted(
        ((dx, dy) for dy in range(-radius[1], radius[1] + 1, step)
         for dx in range(-radius[0], radius[0] + 1, step)),
        key=lambda d: (d[0] ** 2 + d[1] ** 2, abs(d[0]) + abs(d[1])))
    best, bx, by = -1.0, x, y
    for dx, dy in candidates:
        x0, y0 = x + dx - win[0] // 2, y + dy - win[1] // 2
        frac = ink_frac(x0, y0, x0 + win[0], y0 + win[1])
        if frac > best + margin:
            best, bx, by = frac, x + dx, y + dy
    return bx, by, max(best, 0.0)
