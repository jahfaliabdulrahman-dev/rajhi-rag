"""حدودُ صفوف الكشف الممسوح من مواضع الحبر وحدها — بلا OCR ولا نموذج.

## لماذا

نموذجُ الرؤية يقرأ الأرقام جيّدًا لكنه يُخطئ **حدودَ الصفّ**: الوصفُ ينزاح صفًّا كاملًا والمبالغُ
صحيحة (`HARD_RULES["desc_shift"]`). وحدودُ الصفّ في هذا الكشف لا تحتاج قراءةً أصلًا:

- **الرصيدُ الجاري يُطبع في السطر الأوّل من كلّ حركة**، والوصفُ يمتدّ تحته (تأكيدُ المالك،
  ومقيسٌ على العيّنات) ⇒ **كلُّ حبرٍ في شريط الرصيد = مرساةُ صفّ**. العثورُ على مكان رقمٍ أوثقُ
  بكثيرٍ من قراءته.
- **الصفُّ يبدأ من سطر مرساته وينتهي قبل سطر المرساة التالية مباشرة** — لا في منتصف المسافة،
  وإلا انقسم وصفُ الصفّ الأعلى.
- **وصفُ آخر حركةٍ قد يُكمَل أعلى الصفحة التالية**: حبرٌ في شريط الوصف فوق أوّل مرساة ولا رصيدَ
  معه ⇒ **تكملةٌ** لآخر صفٍّ في الصفحة السابقة (`link_pages`)، ويُلصقان صورةً واحدة (`stitch`).
- **التاريخُ على سطر المرساة نفسه شاهدٌ لا مرساة**: أسطرُ وصفٍ طويلة تمتدّ إلى شريط التاريخ.

## القالب

نموذجٌ واحدٌ للورقة، مقيسٌ على ١٤ صفحةً ممسوحة (2013 · 2019 · 2022 · 2024 · صفحة الملخّص):
الرأسُ في كلّ صفحة، ولا رؤوسَ أعمدةٍ مطبوعة، وما يتغيّر بين أجيال الطباعة **صيغةُ الأرقام لا
مواضعُها**. الإحداثياتُ أدناه بوحدة «بكسل عند 100dpi» وتُضرب في `dpi/100`. والصفحةُ يُفترض أنها
مستقيمة (الميلُ تقيسه `tools/page_gate.py`).

## ثلاثةُ دروسٍ من القياس (لا تُنسى)

1. **لا تحت 150dpi:** «١» عرضُه بكسلٌ واحد عند 100dpi و«٠» نقطة ⇒ فاتت أغلبُ أرصدة 2013.
2. **الرصيدُ «٠٫٠٠» أضعفُ مرساة** (نقاطٌ فقط، وحافّتُها العليا أدنى من سطر التاريخ) ⇒ المطابقةُ
   بالتداخل لا بالحافّة العليا.
3. **عنوانُ «الرصيد الافتتاحي» أطولُ من أرقامه** ⇒ ما يقع في سطر المرساة جزءٌ منها لا تكملة.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

MIN_DPI = 150
INK = 150                      # رمادي أغمق من هذا = حبر (أرقام 2013 أفتح وأرقّ)

# --- القالب (بكسل عند 100dpi) ------------------------------------------------
BALANCE_X = (95, 180)          # الرصيد الجاري — المرساة
CREDIT_X = (225, 300)          # الدائن (المدين ملاصقٌ للوصف فلا يُفصل بالموضع)
DATE_X = (625, 712)            # التاريخان الهجري والميلادي — شاهد
DESC_X = (330, 712)            # الوصف بعرضه
HEADER_X, HEADER_Y = (380, 600), (300, 378)    # سطر الـIBAN — آخرُ الرأس
FOOTER_X, FOOTER_Y = (640, 720), (900, 1060)   # عنوان «العملة» (٩٧٦–٩٨٦ في كل صفحة)
BELOW_HEADER = 20              # بدايةُ منطقة الجدول تحت سطر الـIBAN
GAP = 3                        # فراغٌ أقصر من هذا لا يفصل سطرين
MIN_H = 2                      # أقصرُ حبرٍ يُعدّ سطرًا («٠٫٠٠» نحو ٣)
PAD = 3                        # هامشُ القصّ حول الحبر
SLACK = 2                      # سماحُ التداخل بين المرساة وشاهدها
RISE = 10                      # مدى البحث عن الوادي فوق أرقام المرساة («الافتتاحي» مقيسٌ ٧)


@dataclass
class Band:
    """صفُّ حركةٍ واحد (بكسل بدقّة الصورة)."""
    top: int
    bottom: int
    anchor: tuple[int, int]        # سطر الرصيد
    dated: bool                    # تاريخٌ على سطر المرساة
    credit_ink: bool               # حبرٌ في عمود الدائن على سطر المرساة


@dataclass
class PageBands:
    dpi: int
    kind: str                      # transactions | first | summary | unknown
    zone: tuple[int, int] | None   # منطقة الجدول
    bands: list[Band] = field(default_factory=list)
    orphan: tuple[int, int] | None = None   # تكملةُ وصفٍ من الصفحة السابقة
    extra_date_lines: int = 0      # حبرٌ في شريط التاريخ بلا مرساة (وصفٌ طويل) — للإعلام

    def suspects(self) -> list[int]:
        """مراسٍ بلا تاريخ — عدا صفّ الرصيد الافتتاحي في الصفحة الأولى."""
        return [i for i, b in enumerate(self.bands)
                if not b.dated and not (self.kind == "first" and i == 0)]

    def to_dict(self) -> dict:
        return asdict(self)


def _px(units: float, k: float) -> int:
    return int(round(units * k))


def _runs(ink: np.ndarray, x: tuple[int, int], y0: int, y1: int,
          k: float) -> list[tuple[int, int]]:
    """سطورُ الحبر في شريطٍ عمودي: [(أعلى، أسفل)] بالبكسل."""
    y0, y1 = max(0, y0), min(ink.shape[0], y1)
    if y1 <= y0:
        return []
    rows = np.flatnonzero(ink[y0:y1, _px(x[0], k):_px(x[1], k)].any(axis=1))
    if rows.size == 0:
        return []
    gap, min_h = max(1, _px(GAP, k)), max(1, _px(MIN_H, k))
    splits = np.flatnonzero(np.diff(rows) > gap)
    starts = np.concatenate(([rows[0]], rows[splits + 1]))
    ends = np.concatenate((rows[splits], [rows[-1]]))
    return [(int(a) + y0, int(b) + y0) for a, b in zip(starts, ends)
            if b - a + 1 >= min_h]


def _overlaps(r: tuple[int, int], a: tuple[int, int], slack: int) -> bool:
    return r[0] <= a[1] + slack and r[1] >= a[0] - slack


def analyze_page(gray: np.ndarray, dpi: int) -> PageBands:
    """صفحةٌ رمادية (H×W، uint8) ⇒ حدودُ صفوفها وتكملتُها ونوعُها."""
    if dpi < MIN_DPI:
        raise ValueError(f"dpi={dpi} < {MIN_DPI}: الأرقامُ الرقيقة تختفي (الدرس ١)")
    k = dpi / 100
    ink = gray < INK
    head = _runs(ink, HEADER_X, _px(HEADER_Y[0], k), _px(HEADER_Y[1], k), k)
    if not head:
        return PageBands(dpi, "unknown", None)
    foot = _runs(ink, FOOTER_X, _px(FOOTER_Y[0], k), _px(FOOTER_Y[1], k), k)
    top = head[-1][1] + _px(BELOW_HEADER, k)
    # العنوانُ **أدنى** حبرٍ في شريطه لا أوّلُه: في الصفحة الممتلئة يقع تاريخُ آخرِ حركةٍ عند ~٩٠٥
    # داخل النافذة نفسها، فأُخذ عنوانًا وقُصّ الصفُّ الأخير — ١٧٧ صفحةً من ٦٢٥ (مقيس على الكاش:
    # القراءةُ الكاملة تزيد صفًّا واحدًا بالضبط، والسلسلةُ تُثبته حركةً حقيقية).
    bottom = (foot[-1][0] if foot else _px(FOOTER_Y[1], k)) - _px(PAD, k)
    zone = (top, bottom)

    anchors = _runs(ink, BALANCE_X, top, bottom, k)
    if not anchors:
        return PageBands(dpi, "unknown", zone)
    dates = _runs(ink, DATE_X, top, bottom, k)
    credit = _runs(ink, CREDIT_X, top, bottom, k)
    desc = _runs(ink, DESC_X, top, bottom, k)
    slack, pad, rise = _px(SLACK, k), _px(PAD, k), _px(RISE, k)

    # بدايةُ سطر المرساة = **الوادي**: أقلُّ صفِّ بكسلاتٍ حبرًا في شريط الوصف فوق أرقامها بمدى RISE،
    # والأدنى عند التساوي. السطورُ في هذه الطباعة شبهُ متلاصقة: قصُّ الحافّة بهامشٍ ثابت يشطر آخرَ
    # سطرٍ من وصف الصفّ الأعلى (قيس على 2019 و2022)، والوادي يقع بين السطرين حيث كانا. وعنوانُ
    # «الرصيد الافتتاحي» فوقه فراغ ⇒ الوادي فوق حروفه، فيبقى في صفّه (الدرس ٣). وصفُّ الوادي
    # نفسُه يُغلق الصفَّ الأعلى: ذيلُ حرفٍ نازلٍ يلامس السطرَ التالي يبقى مع سطره.
    prof = ink[:, _px(DESC_X[0], k):_px(DESC_X[1], k)].sum(axis=1)
    line_tops = []
    for a in anchors:
        lo = max(top, a[0] - rise)
        win = prof[lo:a[0] + 1]
        valley = lo + int(np.flatnonzero(win == win.min())[-1])
        line_tops.append(min(valley + 1, a[0]))

    bands = []
    for i, a in enumerate(anchors):
        if i + 1 < len(anchors):
            end = line_tops[i + 1] - 1
        else:
            tail = [r[1] for r in desc if r[1] >= a[0]]
            end = min(bottom, max([a[1]] + tail) + pad)
        bands.append(Band(top=line_tops[i], bottom=end, anchor=a,
                          dated=any(_overlaps(d, a, slack) for d in dates),
                          credit_ink=any(_overlaps(c, a, slack) for c in credit)))

    dated = sum(b.dated for b in bands)
    if dated == 0:
        kind = "summary"               # صفحةُ الملخّص: أرصدةٌ بلا تواريخ
    elif not bands[0].dated and dated == len(bands) - 1:
        kind = "first"                 # صفُّ «الرصيد الافتتاحي» أوّلًا
    else:
        kind = "transactions"

    orphan = None
    if kind != "summary":
        above = [r for r in desc if r[0] < line_tops[0]]      # سطورٌ بطولٍ أدنى — لا غبارُ مسح
        if above:
            orphan = (max(top, above[0][0] - pad), line_tops[0] - 1)
    extra = sum(not any(_overlaps(d, a, slack) for a in anchors) for d in dates)
    return PageBands(dpi, kind, zone, bands, orphan, extra)


def link_pages(pages, order: list[int] | None = None,
               pairs: dict[tuple[int, int], str] | None = None) -> list[dict]:
    """تكملةُ أعلى الصفحة ⇒ آخرُ صفٍّ في **سابقتها في الترتيب الحقيقي** لا في الملف.

    `pages`: قائمةٌ (المواضعُ فهارسُها) أو {موضع: PageBands}. `order`: الترتيبُ الحقيقي
    (`ordering.footer_order`)؛ وبدونه ترتيبُ الملف. `pairs`: حالةُ كلّ جارَين
    (`ordering.adjacency`):

    - `adjacent` ⇒ الربطُ مؤكَّد (`confirmed: True`).
    - `gap` ⇒ بينهما ورقةٌ غائبة، فالتكملةُ لصفٍّ **ليس عندنا**: صاحبُها غائب، لا تُنسب لغيره.
    - غيرُ ذلك أو بلا `pairs` ⇒ ربطٌ غيرُ مؤكَّد (`confirmed: False`) — يُقرأ ويُعلَّم.

    والتكملةُ في أوّل الترتيب أو بعد صفحةٍ ليست صفحةَ حركات ⇒ صاحبُها غائب: تُعلَّم ولا تُحذف.
    """
    if isinstance(pages, list):
        pages = dict(enumerate(pages))
    order = list(order) if order is not None else sorted(pages)
    links = []
    for i, pos in enumerate(order):
        if pages[pos].orphan is None:
            continue
        prev = order[i - 1] if i else None
        status = (pairs or {}).get((prev, pos))
        owner = pages.get(prev) if prev is not None else None
        if owner is None or not owner.bands or owner.kind not in ("transactions", "first"):
            links.append({"page": pos, "owner_missing": True})
        elif status == "gap":
            links.append({"page": pos, "owner_missing": True, "gap_before": True})
        else:
            links.append({"page": pos, "continues": [prev, len(owner.bands) - 1],
                          "confirmed": status == "adjacent"})
    return links


def stitch(prev_img, band: Band, next_img, orphan: tuple[int, int], sep: int = 6):
    """آخرُ صفٍّ في صفحة + تكملتُه أعلى التالية ⇒ صورةٌ واحدة، بينهما خطٌّ رمادي رفيع.

    فيقرأ النموذجُ الحركةَ كاملةً صفًّا واحدًا، والتكملةُ بلا مبلغ فلا تصير صفًّا زائدًا.
    """
    from PIL import Image, ImageDraw

    a = prev_img.crop((0, band.top, prev_img.width, band.bottom + 1))
    b = next_img.crop((0, orphan[0], next_img.width, orphan[1] + 1))
    out = Image.new(a.mode, (max(a.width, b.width), a.height + sep + b.height), "white")
    out.paste(a, (0, 0))
    out.paste(b, (0, a.height + sep))
    ImageDraw.Draw(out).line([(0, a.height + sep // 2), (out.width, a.height + sep // 2)],
                             fill="gray", width=1)
    return out


def overlay(gray: np.ndarray, pb: PageBands):
    """صورةٌ للمراجعة بالعين: الصفوفُ أحمر · التكملةُ أزرق · منطقةُ الجدول أخضر."""
    from PIL import Image, ImageDraw

    img = Image.fromarray(gray).convert("RGB")
    d = ImageDraw.Draw(img)
    w = img.width
    if pb.zone:
        for y in pb.zone:
            d.line([(0, y), (w, y)], fill=(0, 160, 0), width=2)
    for b in pb.bands:
        d.rectangle([60, b.top, w - 60, b.bottom], outline=(220, 0, 0), width=2)
    if pb.orphan:
        d.rectangle([60, pb.orphan[0], w - 60, pb.orphan[1]], outline=(0, 90, 230), width=2)
    return img
