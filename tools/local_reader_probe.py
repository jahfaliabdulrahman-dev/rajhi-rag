"""«قياس ٤» — **أداةُ القارئ المحلّيّ**: كم يسترجع قارئٌ محلّيٌّ مجّانيّ (بلا سحابة) من ورقة كشفٍ ممسوحة؟

**ما يقيسه (وحدُّه المُعلَن):** استرجاعُ **نصِّ** المبالغ والأرصدة المطبوعة، مقابل الحقيقة الأرضيّة في
`data/training/<التصميم>/pg-<NNN>/label.json` (حقلُ `printed_amount` — ما على الورق نصًّا كما طُبع — و`balance`).
و**لا** يقيس إغلاقَ السلسلة ولا مطابقةَ التذييل — تلك بوّابةُ «ب-٤» وحدَها، وهذا مِقياسٌ واحدٌ منها.

**القاعدةُ المُعلَنة (وحدَها) — «الورق» `ورق`:** تُحسب مطابقةً **الصيغةُ التي يطبعها العمودُ بكسره من خانتين**،
فلا تُحتسب قيمةٌ قُرئت بلا كسرٍ إصابةً. سُببُها مقيس (مراجعة ٦٤): قاعدةُ `قيمة` (تساوي `Decimal` مهما كانت
الصيغة) تحتسب **إصاباتٍ عارضة** — رمزٌ تائه من خانةٍ واحدة يطابق مبلغًا خانتُه الصحيحة مفردة (٩ من أصل ٤٦
صفًّا) ⇒ **٤ من ١٧ إصابةً ليست قراءة**. فالأرقامُ المنشورةُ هي أرقامُ `ورق`، والثلاثُ الأخرى عدساتٌ تشخيصيّة.

**والوحدتان معًا (اللبسُ بينهما كان عطبًا معلَنًا):** **الصفوف — ٤٦** (وهي التي يخدمها حكمُ «صفٌّ ناقصُ مبلغٍ
= صفٌّ لا يُغلق») و**القيمُ المتمايزةُ في كلّ صفحة — ٣٥** (وحدةُ القياس الأولى، تُذكر للاستمراريّة).
و`شكل` · `قيمة` · `أرقام` تُطبع كلُّها في المخرَج لتُرى — **كلُّ عدسةٍ بمقامها** — ولا يُنشَر منها رقمٌ كمقياس.
و**الاشتقاقُ واحدٌ للطرفين** (`canonical` ⇐ `lenses_of`): لا نسختان تفترقان في الإشارة ولا في حدّ الإدراج،
و**المقامُ يُرشَّح بالقاعدة المُعلَنة نفسِها** ويُطبَع عددُ المُسقَط بها كي لا يُفرَّغ بصمت.

**حدُّ القياس (مُعلَن):** المطابقةُ على مستوى **الصفحة** لا الصفّ في العمود — لا ربطَ بعمودٍ ولا إحداثيّات
(فالرقمُ عضويّةٌ في الصفحة كلِّها)، ويُقاس الصفُّ بأنّ مبلغَه المطبوعَ ظهر في رموز الصفحة ⇒ **الرقمُ حدٌّ أعلى
متفائل لا أسفل**، ولا يُتّخذ مِقياسَ درجةٍ لنموذجٍ لاحق وحدَه. والإشارةُ (مدين/دائن) تُسقَط من الطرفين:
رمزُ المحرّك لا يحملها، فإبقاؤها كانت تُحيل الأرصدةَ السالبةَ متعذِّرةَ الإصابة بحكم البناء لا بحكم المحرّك.

**لماذا في المستودع:** رقمٌ بلا أداته ليس دليلًا — من أراد إعادةَ القياس يُشغّل:

    python tools/local_reader_probe.py            # يحتاج Vision (ماك)
    python tools/local_reader_probe.py --list     # المجموعةُ المُجمَّدة والمُؤهَّلُ الحاليّ (بلا قراءة)
    python tools/local_reader_probe.py --pages 187
    python tools/local_reader_probe.py --design <معرّف>   # والافتراضُ يُكتشف من القرص

**رموزُ الخروج (كلُّها مُعلَنةٌ ومُختبَرة):** ٠ قياسٌ تمّ · ٢ محرّكُ Vision غائبٌ (إطفاءٌ برسالة) ·
٣ لا بياناتِ تدريبٍ محلّيّة **أو لا مقامَ قابلًا للقياس** (لا مبلغَ مطبوعًا أو لا رصيدَ مطبوعًا في الصفحات
المطلوبة) **أو صفرُ إصاباتٍ في كلّها** (قاعدة ٩: الصفرُ بالضبط علامةُ قياسٍ ميتٍ لا نموذجٍ فاشل، فلا يُنشَر
«٠.٠٪» قياسًا تمّ) · ٤ صفحةٌ مطلوبةٌ غيرُ مؤهَّلة (والرسالةُ تسمّي المؤهَّلَ اليوم) · ٥ وسيطٌ مشوَّه
(`--pages` · أو عَلَمٌ غيرُ معروف). و**نصٌّ فارغٌ من المحرّك يُسمّى** بسطر ⚠ باسم صفحته.

**الترتيبُ مهمّ:** غيابُ البيانات يُسمّى (٣) **قبل** أيّ طلبِ صفحة — وإلّا صار غيابُها «صفحةً غيرَ مؤهَّلة» (٤).

**المحرّك:** macOS Vision (`VNRecognizeTextRequest`) عبر `pyobjc` في **بيئةٍ معزولة** — ليست من
متطلّبات المشروع. غيابُه يُطفئ الأداة برسالة، ولا يكسر شيئًا (نصفُ المقارنة يعمل بلا محرّك).

**الصفحاتُ الخمسُ ثابتٌ مُجمَّدٌ مُعلَن:** `PUBLISHED_PAGES` هي الصفحاتُ التي قِيس عليها الرقمُ المنشور.
اشتُقّت مرّةً واحدةً بقاعدةِ توزيعٍ على المُؤهَّل (`[i*len//5 for i in range(5)]`)، ثم **جُمِّدت** — لأنّ
المُؤهَّلَ نفسَه يتغيّر مع كلّ دفعةِ التقاطٍ جديد، فإعادةُ تطبيق القاعدة اليومَ تُعطي أرقامًا أخرى. فالخيارُ
المُعلَنُ هو التجميدُ باسمِه، لا ادّعاءُ أنّ القاعدةَ تُنتجها في كلّ وقت. و`--list` يطبع المجموعةَ المُجمَّدة
والمُؤهَّلَ الحاليَّ معًا فلا يختلطان.

**قاعدةُ الأرقام (درسُ أ-٧):** الفواصلُ العربيّة تُوحَّد **بحكم موقعها**: آخرُ فاصلٍ يليه كسرٌ (خانةٌ أو
خانتان) ⇒ عشريّ، وما عداه ⇒ آلاف. ومن الصيغةِ الكانونيّةِ تُشتقّ **أربعُ** عدسات: `ورق` (المُعلَنة: كانونيٌّ
**بكسرِ خانتين** كما يطبعه العمود) · `شكل` (الكانونيُّ نصًّا، بكسرٍ أو بلا كسر) · `قيمة` (`Decimal` — تتجاوز
الصيغة فتُعارُ إصاباتٍ عارضة، **لا تُنشر**) · `أرقام` (مجرَّدةٌ من كل فاصل).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from decimal import Decimal, InvalidOperation

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESIGN_ENV = "data/training"            # التصميمُ يُكتشف من القرص ولا يُكتب في الشيفرة (معرّفٌ في النشرة)
MIN_ROWS = 5
MIN_DIGITS_FOR_DIGITS_RULE = 2
PUBLISHED_PAGES = (1, 187, 320, 404, 539)

# العدساتُ الأربع في موضعٍ واحد: **الأولى هي المُعلَنة** (بصيغة الورق)، والثلاثُ بعدها تشخيصيّةٌ لا تُنشَر.
# و«ورق» و«شكل» و«أرقام» نصٌّ، و«قيمة» أعدادٌ (`Decimal`).
RULES: tuple[str, ...] = ("ورق", "شكل", "قيمة", "أرقام")
PUBLISHED_RULE = RULES[0]               # لا يُنشَر رقمٌ من غيرها
RuleSets = dict[str, set]

PAPER_FRACTION_DIGITS = 2               # ما يطبعه العمود: كسرٌ من خانتين — وهو شرطُ المطابقة المُعلَنة
SINGLE_INTEGER_DIGIT = 1                # يُعلَن منفصلًا: مبلغٌ خانته الصحيحة مفردة ⇒ رمزٌ تائه يطابقه

EXIT_OK, EXIT_NO_ENGINE, EXIT_NO_DATA, EXIT_NOT_ELIGIBLE, EXIT_BAD_ARGS = 0, 2, 3, 4, 5

_SCAN_CACHE: dict[pathlib.Path, list] = {}   # مسحٌ واحدٌ لكلّ مجلّد (المفتاحُ المسارُ لا الاسم) — يُصفَّر في `main`

AR_INDIC = {ord(c): ord("0") + i for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}
AR_EXTENDED = {ord(c): ord("0") + i for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")}
ALL_SEPS = ".,،٫٬"
SIGN_CHARS = "-−–—"                     # إشارةُ السالب بأنواعها: تُسقَط من الطرفين (المحرّكُ لا يحملها)
_SEPS = "[" + re.escape(ALL_SEPS) + "]"
TOKEN = re.compile(r"\d[\d" + re.escape(ALL_SEPS) + r"]*\d|\d")
TRAILING_FRACTION = re.compile(_SEPS + r"(\d{1,2})$")


class IneligiblePage(Exception):
    """صفحةٌ مطلوبةٌ ليست في المُؤهَّل — رسالةٌ مسمّاة ⇒ رمزُ خروجٍ مسمّى (لا موتٌ صامتٌ برمز ١)."""


class BadArguments(Exception):
    """وسيطٌ مشوَّه — رمزٌ مسمّى (٥): لا موتٌ برمز ١، ولا التباسٌ برمز «المحرّك غائب» (٢)."""


def to_ascii_digits(s: str) -> str:
    """عربيّة-هندية (٠-٩) وفارسيّة (۰-۹) ⇒ لاتينيّة."""
    return s.translate(AR_INDIC).translate(AR_EXTENDED)


def canonical(tok: str) -> str | None:
    """القاعدةُ الأولى: **شكلٌ** كانونيٌّ — الفاصلةُ العشريّةُ تُحدَّد بموقعها (آخرُ فاصلٍ ويليه كسرٌ).

    والكسرُ المقبولُ خانةٌ أو خانتان: ورقةٌ تطبع «٩٩٩٫٩» لا يجوز أن تُقرأ «٩٩٩٩» (عطبٌ مقيسٌ في الاتّجاه
    المقابل: «٩٩٩٫٠٠» ⇐ «٩٩٩٫٠»).

    **والإشارةُ تُسقَط هنا — وهذا موضعُ الإسقاط الوحيد للطرفين:** قِيس (مقعد البنية) أنّ رمزَ المحرّك لا
    يحمل إشارةً أصلًا، فإبقاؤها في الورق كان يُحيل الأرصدةَ السالبةَ **متعذِّرةَ الإصابة بحكم البناء لا بحكم
    المحرّك** (١٨ حقلًا موقَّعًا في ١٢ صفحةً من ٢٨٢). فالمقياسُ يقيس الأرقامَ لا الإشارة — ويُعلَن ذلك.
    """
    t = to_ascii_digits(tok).strip().lstrip(SIGN_CHARS)
    if not any(ch.isdigit() for ch in t):
        return None
    m = TRAILING_FRACTION.search(t)
    if m:
        head = re.sub(_SEPS, "", t[: m.start()])
        if head:
            return f"{head}.{m.group(1)}"
    digits = re.sub(_SEPS, "", t)
    return digits or None


def value_of(tok: str) -> Decimal | None:
    """عدسةٌ **تشخيصيّةٌ لا تُنشَر**: تتجاوز الصيغة (`Decimal`) فتُعارُ إصاباتٍ عارضة — قِيس (مراجعة ٦٤)
    أنّ ٤ من ١٧ إصابةً في هذه الصفحات تطابقها رموزٌ بلا كسر (رمزٌ تائه يطابق مبلغًا صحيحُه خانةٌ واحدة).
    """
    c = canonical(tok)
    if c is None:
        return None
    try:
        return Decimal(c)
    except InvalidOperation:
        return None


def digits_of(tok: str) -> str | None:
    """القاعدةُ الثالثة: **أرقامٌ مجرَّدة** من كل فاصل — تتحمّل إسقاطَ المحرّك للفاصلة."""
    d = re.sub(_SEPS, "", to_ascii_digits(tok))
    return (d.lstrip("0") or "0") if d else None


def _accept_digits(form) -> bool:
    """حدُّ الإدراج لقاعدة «أرقام» — مطبَّقٌ على الطرفين (المحرّك والحقيقة) فلا يبقى في المقام ما لا يُطابَق."""
    return form not in (None, "") and len(str(form)) >= MIN_DIGITS_FOR_DIGITS_RULE


def has_paper_shape(canon: str | None) -> bool:
    """هل الصيغةُ الكانونيّةُ كما يطبعها العمود (بكسرٍ من خانتين)؟ — شرطُ المطابقة المُعلَنة."""
    if not canon:
        return False
    m = re.search(r"\.(\d+)$", canon)
    return bool(m) and len(m.group(1)) == PAPER_FRACTION_DIGITS


def integer_digits_of(canon: str | None) -> int:
    """عددُ خانات الجزء الصحيح — لإعلان المبالغ ذات الخانة الواحدة منفصلةً (وهي التي يطابقها رمزٌ تائه)."""
    if not canon:
        return 0
    return len(canon.split(".")[0].lstrip("0") or "0")


def lenses_of(canon: str | None) -> RuleSets:
    """**الاشتقاقُ الوحيد**: من صيغةٍ كانونيّةٍ واحدة تُشتقّ العدساتُ الأربع — يستعملُه طرفا المقابلة معًا.

    كان بناءُ العدسات مكتوبًا **مرّتين** (للمحرّك وللورق) ⇒ افتراقٌ صامتٌ قابلٌ للوقوع، وهو ما قِيس فعلًا
    في الإشارة وحدِّ الإدراج (مقعد البنية). فصار البناءُ في موضعٍ واحد — والأرقامُ المنشورةُ لا تتغيّر.
    """
    out: RuleSets = {name: set() for name in RULES}
    if not canon:
        return out
    out["شكل"].add(canon)
    if has_paper_shape(canon):
        out["ورق"].add(canon)
    try:
        out["قيمة"].add(Decimal(canon))
    except InvalidOperation:
        pass
    d = re.sub(_SEPS, "", canon).lstrip("0") or "0"
    if _accept_digits(d):
        out["أرقام"].add(d)
    return out


def _merge(dst: RuleSets, src: RuleSets) -> None:
    for name in RULES:
        dst[name] |= src[name]


def numeric_sets(text: str) -> RuleSets:
    """عدساتُ نصٍّ مقروء: كلُّ رمزٍ على المنظِّم الواحد ثم على `lenses_of` — **بلا اشتقاقٍ ثانٍ**."""
    out: RuleSets = {name: set() for name in RULES}
    for raw in TOKEN.findall(to_ascii_digits(text)):
        _merge(out, lenses_of(canonical(raw)))
    return out


def design_candidates() -> list[pathlib.Path]:
    """كلُّ تصميمٍ في `data/training/` فيه صفحاتٌ (قد يوجد أكثر من واحد)."""
    base = ROOT / DESIGN_ENV
    return sorted(p for p in base.glob("*") if p.is_dir() and any(p.glob("pg-*")))


def resolve_design(design: str | None = None) -> pathlib.Path:
    """**«أيُّ تصميم؟» في دالّةٍ واحدة** — كانت `eligible` تحمل سؤالين: «أيُّ تصميم؟» و«امسح واحدًا».

    صريحًا، أو **الأوّلُ الذي يحمل الصفحاتِ المُجمَّدة** فلا يُعاد قياسٌ على غيرها (والسقوطُ إلى الأوّل
    إن لم يحملها أحدٌ يُعلَن بحكم `selected`).
    """
    if design:
        return ROOT / DESIGN_ENV / design
    dirs = design_candidates()
    for d in dirs:
        # من الأرقام التي تحملها الحقيقةُ لا من اسم المجلّد (الأسماءُ مُصفَّرة: pg-001)
        if set(PUBLISHED_PAGES) <= {int(lab["page"]) for _, lab, _ in eligible(d)}:
            return d
    return dirs[0] if dirs else (ROOT / DESIGN_ENV / "-")


def _scan_one(path: pathlib.Path) -> list[tuple[pathlib.Path, dict, list]]:
    """مسحٌ خامٌّ لمجلّدٍ **واحد**: فيه `page.png` و`label.json` و`len(rows) >= MIN_ROWS`."""
    out = []
    for d in sorted(path.glob("pg-*"), key=lambda p: int(p.name.split("-")[1])):
        lj, png = d / "label.json", d / "page.png"
        if not (png.exists() and lj.exists()):
            continue
        lab = json.loads(lj.read_text(encoding="utf-8"))
        rows = lab.get("rows") or []
        if len(rows) >= MIN_ROWS:
            out.append((d, lab, rows))
    return out


def forget_scan_cache() -> None:
    """يُصفَّر المسحُ المخزَّن: يُنادى في بداية `main`، وفي الاختبارات التي تُبدّل الدوالّ."""
    _SCAN_CACHE.clear()


def eligible(design: str | pathlib.Path | None = None) -> list[tuple[pathlib.Path, dict, list]]:
    """الصفحاتُ المُؤهَّلة بترتيب الرقم — **بمسحٍ واحدٍ لكلّ مجلّدٍ في الوظيفة الواحدة**.

    كان المسحُ يتكرّر: `resolve_design` تمسح للتصفية، ثم `main` تمسح ثانيةً، ثم `--list` ثالثةً (قِيس في
    مراجعة ٦٤: ٥٧٧ قراءةَ `label.json` لـ٢٩٤ ملفًا في تشغيلٍ عاديّ، و٨٧١ في `--list`). والمرجعُ المخزَّن
    هو نفسُه الذي يُعاد ⇒ لا نسخةَ تُبدَّل تحت مستهلك. **والمفتاحُ المسارُ المُحلَّل لا الاسم**: اسمٌ واحدٌ
    لشجرتين مختلفتين كان يُعيد مسحَ الشجرة الأولى صامتًا (قِيس في مقعد البنية).
    """
    if design is None:
        path = resolve_design()
    else:
        given = pathlib.Path(design)
        path = given if given.is_absolute() else ROOT / DESIGN_ENV / design
    if path not in _SCAN_CACHE:
        _SCAN_CACHE[path] = _scan_one(path)
    return _SCAN_CACHE[path]


def selected(pages: tuple[int, ...] = PUBLISHED_PAGES, design: str | None = None,
             pool: list | None = None) -> list[tuple[pathlib.Path, dict, list]]:
    """يجد الأرقامَ المطلوبة في المُؤهَّل، ويرفع `IneligiblePage` باسمِ الصفحة والمؤهَّلِ اليوم.

    `pool` يُمرَّر من `main` فيُمسَح القرصُ مرّةً واحدة (وكان يُمسَح مرّتين).
    """
    rows = eligible(design) if pool is None else pool
    by_page = {int(lab["page"]): (d, lab, r) for d, lab, r in rows}
    out = []
    for p in pages:
        if p not in by_page:
            raise IneligiblePage(f"صفحةٌ غيرُ مؤهَّلة: {p} (المُؤهَّلُ اليوم: {sorted(by_page)})")
        out.append(by_page[p])
    return out


def _truth_form(val) -> str:
    """صياغةُ الرقم من `label.json`: النصُّ كما طُبع يُمرّ كما هو (وقِيس: ٤٦/٤٦ من صفحات القياس نصوصٌ)،
    والعددُ (لو جاء) يُصاغ بكسرين — فالقارئُ يقابِل **ما على الورق**، ولا يُقاس على `str()` عددٍ خامّ."""
    if isinstance(val, bool) or not isinstance(val, (int, float, Decimal)):
        return str(val)
    d = Decimal(str(val))
    return str(int(d)) if d == d.to_integral_value() else f"{d:.2f}"


def truth_sets(rows: list) -> dict[str, RuleSets]:
    """الحقيقةُ الأرضيّة **مفصولةً بكل عدسةٍ على حِدة** — خلطُ العدسات في مجموعةٍ واحدة يخلق مطابقاتٍ كاذبة.

    والقياسُ على **`printed_amount`** وحدَه: هو ما على الورق، وهو ما يُقابله القارئ. وصفٌّ بلا
    `printed_amount` يُسقَط من العمود — لا يُقابَل بمقدارٍ مشتقٍّ من السلسلة لم يُطبَع.
    و**`ورق` (المُعلَنة)**: كانونيٌّ بكسرِ خانتين كما يطبعه العمود (والملفّاتُ نصٌّ كما طُبع: قِيس ٤٦/٤٦).
    """
    out: dict[str, RuleSets] = {k: {name: set() for name in RULES} for k in ("مبالغ", "أرصدة")}
    for r in rows:
        for group, val in (("مبالغ", r.get("printed_amount")), ("أرصدة", r.get("balance"))):
            if val in (None, ""):
                continue
            # **الاشتقاقُ الوحيد للطرفين**: منظِّمٌ واحد (`canonical`) ثم أربعُ عدساتٍ من موضعٍ واحد
            _merge(out[group], lenses_of(canonical(_truth_form(val))))
    return out


def row_counts(rows: list, found: RuleSets, rule: str = PUBLISHED_RULE) -> tuple[int, int, int, int]:
    """**اشتقاقٌ صفّيّ واحد** — لا نسخةٌ ثانية من اشتقاق مبلغ الصفّ:
    (المطابَقة · المقامُ المرشَّحُ بالصيغة · المُسقَطُ بالصيغة · ما خانته الصحيحة مفردة).

    والمقامُ يُرشَّح بالقاعدة المُعلَنة نفسِها كما تُرشَّح عيّنةُ القيم — فلا يُقاس بخانتين في المطابقة
    ويُقسَم على صفٍّ لا يجوز أن يُطابَق. ويُطبَع عددُ المُسقَط كي **لا يُفرَّغ المقامُ بصمت** (قِيس في
    مقعد المواصفة: صفٌّ بمبلغٍ بكسورٍ من خانةٍ واحدة كان يختفي من البسط والمقام بلا عدّاد).
    """
    hit = total = dropped = single = 0
    for r in rows:
        val = r.get("printed_amount")
        if val in (None, ""):
            continue
        c = canonical(_truth_form(val))
        if not c or not has_paper_shape(c):
            dropped += 1                      # صيغةٌ لا تُطابَق بها القاعدةُ المُعلَنة ⇒ خارجَ المقام، ويُعلَن
            continue
        total += 1
        if integer_digits_of(c) == SINGLE_INTEGER_DIGIT:
            single += 1
        if c in found[rule]:
            hit += 1
    return hit, total, dropped, single


def ocr(path: pathlib.Path) -> str:
    """قراءةٌ محلّيّة بالمحرّك المدمج — بلا شبكة · بلا مفتاح · بلا نموذجٍ مُنزَّل."""
    try:
        import Quartz
        import Vision
        from Foundation import NSURL
    except ImportError as exc:  # pragma: no cover - يعتمد على المنصّة
        raise RuntimeError(
            "محرّكُ macOS Vision غيرُ متاحٍ في هذه البيئة ⇒ "
            "`python3 -m venv <بيئة> && pip install pyobjc-framework-Vision` "
            "(بيئةٌ معزولة، وليست من متطلّبات المشروع)"
        ) from exc
    url = NSURL.fileURLWithPath_(str(path))
    src = Quartz.CGImageSourceCreateWithURL(url, None)
    cg = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setRecognitionLanguages_(["ar-SA", "en-US"])
    req.setUsesLanguageCorrection_(True)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
    handler.performRequests_error_([req], None)
    lines = []
    for obs in (req.results() or []):
        cands = obs.topCandidates_(1)
        if cands and len(cands):
            lines.append(cands[0].string())
    return "\n".join(lines)


def _parse_pages(raw: str | None) -> tuple[int, ...]:
    if not raw:
        return PUBLISHED_PAGES
    try:
        return tuple(int(x) for x in raw.replace(" ", "").split(",") if x)
    except ValueError as exc:
        raise BadArguments(f"--pages يحتاج أرقامًا مفصولةً بفواصل: {raw}") from exc


def _no_data_message(design: str | None) -> str:
    return (f"لا بياناتِ تدريبٍ محلّيّة للتصميم {design or '(غيرُ مُكتشف)'} — الحزمةُ لا تُشحن، "
            f"والقياسُ يحتاج نسخةً محلّيّة من `data/training/`")


def _list_lines(design: str | None, pool: list | None = None) -> list[str]:
    pool = eligible(design) if pool is None else pool
    if not pool:
        return [_no_data_message(design)]
    return [
        f"التصميمُ المُكتشف: {resolve_design(design).name} · المُؤهَّلُ الآن: {len(pool)} صفحة (≥{MIN_ROWS} صفوف)",
        "الصفحاتُ المُجمَّدةُ المنشورة: " + ", ".join(f"pg-{p}" for p in PUBLISHED_PAGES),
        "وهي ثابتٌ مُعلَنٌ لا مُشتقٌّ في كلّ وقت: مُؤهَّلُ تصميمٍ آخرَ لا يُنتجها.",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="قياسٌ محلّيّ لاسترجاع المبالغ والأرصدة من صور الكشوف",
                                exit_on_error=False)
    ap.add_argument("--list", action="store_true", help="اسرد التصميمَ المُكتشف والصفحاتِ المُجمَّدة والمُؤهَّل")
    ap.add_argument("--pages", help="أرقامُ صفحاتٍ بديلةٌ مفصولةٌ بفواصل")
    ap.add_argument("--design", default=None, help="معرّفُ تصميم الحزمة (والافتراض: يُكتشف من القرص)")
    try:
        args, extra = ap.parse_known_args(argv)
    except argparse.ArgumentError as exc:
        print(f"⛔ وسيطٌ مشوَّه: {exc}")
        return EXIT_BAD_ARGS
    if extra:      # **عَلَمٌ غيرُ معروف:** يُسمّى بالرمز ٥ — وكان `parse_args` يموت بـ٢ (رمزِ المحرّك)
        print(f"⛔ وسيطٌ مشوَّه: {' '.join(extra)}")
        return EXIT_BAD_ARGS

    try:
        pages = _parse_pages(args.pages)   # **الوسيطُ يُدقَّق قبل كلّ شيء** — و`--list` ليس استثناءً
    except BadArguments as exc:
        print(f"⛔ وسيطٌ مشوَّه: {exc}")
        return EXIT_BAD_ARGS

    forget_scan_cache()                    # كلُّ تشغيلٍ يبدأ بمسحٍ نظيف: المخزَّنُ لا يعبر التشغيلات
    pool = eligible(args.design)           # **مسحٌ واحد يُعاد استعمالُه** (كان يُمسَح مرّتين: هنا وفي `selected`)
    if args.list:
        lines = _list_lines(args.design, pool)
        print("\n".join(lines))
        return EXIT_NO_DATA if lines[0].startswith("لا بياناتِ") else EXIT_OK

    if not pool:
        # **غيابُ البيانات يُسمّى (٣) قبل أيّ طلبِ صفحة** — وإلّا سُمّي «صفحةً غيرَ مؤهَّلة» (٤) كذبًا.
        print(f"⛔ {_no_data_message(args.design)}")
        return EXIT_NO_DATA
    try:
        chosen = selected(pages, args.design, pool)
    except IneligiblePage as exc:
        print(f"⛔ {exc}")
        return EXIT_NOT_ELIGIBLE

    totals = {k: [0, 0] for k in ("مبالغ", "أرصدة")}   # [المقام, البسط] — بالمُعلَنة «ورق» على القيم المتمايزة
    lens_hits = {name: 0 for name in RULES}            # عدّاتُ العدسات: تُرى للتشخيص ولا يُنشَر منها رقم
    lens_den = {name: 0 for name in RULES}             # **ولكلّ عدسةٍ مقامُها** (لا تُقسَم كلُّها على مقام غيرها)
    rows_hit = rows_all = rows_dropped = rows_single = 0
    print(f"{'صفحة':>6} {'صفوف':>5} " + " ".join(f"{n:>9}" for n in RULES) + f" {'أرصدة':>9}")
    for d, lab, rows in chosen:
        try:
            text = ocr(d / "page.png")
        except RuntimeError as exc:
            print(f"⛔ {exc}")
            return EXIT_NO_ENGINE
        if not text.strip():
            # **نصٌّ فارغٌ يُسمّى** (قاعدة ٩): محرّكٌ لم يُرجع حرفًا ليس قاعدةً أُغلقت — وصفرُ إصاباتٍ ليس قياسًا.
            print(f"⚠ صفحة {lab['page']}: المحرّكُ أعاد نصًّا فارغًا — لا شيءَ يُقاس فيها")
        found = numeric_sets(text)
        truth = truth_sets(rows)
        hits = {name: len(truth["مبالغ"][name] & found[name]) for name in RULES}
        den = {name: len(truth["مبالغ"][name]) for name in RULES}
        bh = len(truth["أرصدة"][PUBLISHED_RULE] & found[PUBLISHED_RULE])
        rh, rt, rd, single = row_counts(rows, found)
        for name in RULES:
            lens_hits[name] += hits[name]
            lens_den[name] += den[name]
        rows_hit += rh
        rows_all += rt
        rows_dropped += rd
        rows_single += single
        totals["مبالغ"][0] += den[PUBLISHED_RULE]
        totals["مبالغ"][1] += hits[PUBLISHED_RULE]
        totals["أرصدة"][0] += len(truth["أرصدة"][PUBLISHED_RULE])
        totals["أرصدة"][1] += bh
        print(f"{lab['page']:>6} {len(rows):>5} " + " ".join(f"{hits[n]:>9}" for n in RULES)
              + f" {bh:>9}")

    amt_n, amt_h = totals["مبالغ"]
    bal_n, bal_h = totals["أرصدة"]
    print("-" * 78)
    if amt_n == 0 or bal_n == 0:
        # **لا نسبةَ بمقامٍ صفريّ:** كان هذا ينفجر بـ`ZeroDivisionError` (تتبّعٌ خامٌ ورمز ١) لمّا تُسقَط
        # كلُّ الصفوف بلا مبلغٍ مطبوع؛ والرفضُ يُسمّى ولا يُحسَب رقمٌ كاذب.
        missing = "المبالغ" if amt_n == 0 else "الأرصدة"
        print(f"⛔ لا مقامَ قابلًا للقياس: لا {missing} مطبوعةً في الصفحات المطلوبة ⇒ لا نسبةَ تُحسَب "
              f"(المبالغ {amt_h}/{amt_n} · الأرصدة {bal_h}/{bal_n} · الصفوف {rows_hit}/{rows_all})")
        return EXIT_NO_DATA
    if amt_h == 0 and bal_h == 0 and rows_hit == 0:
        # **الصفرُ بالضبط يُستثنى ولو كان ممكنًا** (قاعدة ٩): صفرُ إصاباتٍ علامةُ مسارٍ مكسورٍ أو محرّكٍ أعمى،
        # لا نتيجةُ نموذجٍ فاشل — والمقامُ غيرُ صفريّ هنا، فالرفضُ يُسمّى ولا يُنشَر «٠.٠٪» قياسًا تمّ.
        print(f"⛔ صفرُ إصاباتٍ في كلّ الصفحات ⇒ علامةُ قياسٍ ميتٍ لا نموذجٍ فاشل: راجع الصورَ والمحرّكَ "
              f"(المقامات: المبالغ {amt_n} · الأرصدة {bal_n} · الصفوف {rows_all})")
        return EXIT_NO_DATA
    print(f"قاعدةُ «{PUBLISHED_RULE}» (**المُعلَنة** — بصيغة الورق بكسره من خانتين): القيمُ المتمايزةُ في كلّ "
          f"صفحة — المبالغ {amt_h}/{amt_n} = {100 * amt_h / amt_n:.1f}٪ · "
          f"الأرصدة {bal_h}/{bal_n} = {100 * bal_h / bal_n:.1f}٪")
    dropped = f" · مُسقَطٌ بصيغته: {rows_dropped}" if rows_dropped else ""
    print(f"وعلى مستوى **الصفّ** (وحدةُ الحكم: «صفٌّ ناقصُ مبلغٍ = صفٌّ لا يُغلق»): "
          f"المبالغ {rows_hit}/{rows_all} = {100 * rows_hit / rows_all:.1f}٪{dropped}")
    print("عدساتٌ تشخيصيّة (تُرى ولا تُنشَر) — كلُّ عدسةٍ **بمقامها**: "
          + " · ".join(f"{n} {lens_hits[n]}/{lens_den[n]}" for n in RULES[1:])
          + f" · فرقُ «قيمة» عن «ورق» (إصاباتٌ عارضة، قد يزيدها رمزٌ بكسرٍ من خانة): "
            f"{lens_hits['قيمة'] - lens_hits[PUBLISHED_RULE]}")
    print(f"مبالغُ خانتها الصحيحة مفردة (تُعلَن منفصلةً — رمزٌ تائه يطابقها): {rows_single} من {rows_all} صفًّا")
    print("حُدودُ القياس (مُعلَنة): (١) المطابقةُ عضويّةٌ في الصفحة — لا ربطَ بعمودٍ ولا إحداثيّات ⇒ الرقمُ "
          "**حدٌّ أعلى** متفائل لا أسفل، ولا يُتّخذ مِقياسَ درجةٍ لنموذجٍ لاحق وحدَه؛ (٢) الإشارةُ (مدين/دائن) "
          "تُسقَط من الطرفين؛ (٣) استرجاعُ نصٍّ فقط — لا إغلاقَ سلسلةٍ ولا مطابقةَ تذييل ولا شكلَ صفّ.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
