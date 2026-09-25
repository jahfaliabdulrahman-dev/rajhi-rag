"""«قياس ٤» — **أداةُ القارئ المحلّيّ**: كم يسترجع قارئٌ محلّيٌّ مجّانيّ (بلا سحابة) من ورقة كشفٍ ممسوحة؟

**ما يقيسه (وحدُّه المُعلَن):** استرجاعُ **نصِّ** المبالغ والأرصدة المطبوعة، مقابل الحقيقة الأرضيّة في
`data/training/<التصميم>/pg-<رقم>/label.json` (حقلُ `printed_amount` — ما على الورق — و`balance`).
و**لا** يقيس إغلاقَ السلسلة ولا مطابقةَ التذييل — تلك بوّابةُ «ب-٤» وحدَها، وهذا مِقياسٌ واحدٌ منها.

**لماذا في المستودع:** رقمٌ بلا أداته ليس دليلًا — من أراد إعادةَ القياس يُشغّل:

    python tools/local_reader_probe.py            # يحتاج Vision (ماك)
    python tools/local_reader_probe.py --list     # المجموعةُ المُجمَّدة والمُؤهَّلُ الحاليّ (بلا قراءة)
    python tools/local_reader_probe.py --pages 187
    python tools/local_reader_probe.py --design <معرّف>   # والافتراضُ يُكتشف من القرص

**رموزُ الخروج (كلُّها مُعلَنةٌ ومُختبَرة):** ٠ قياسٌ تمّ · ٢ محرّكُ Vision غائبٌ (إطفاءٌ برسالة) ·
٣ لا بياناتِ تدريبٍ محلّيّة **أو لا مقامَ قابلًا للقياس** (لا مبلغَ مطبوعًا في الصفحات المطلوبة) ·
٤ صفحةٌ مطلوبةٌ غيرُ مؤهَّلة (والرسالةُ تسمّي المؤهَّلَ اليوم) · ٥ وسيطٌ مشوَّه (`--pages` · أو عَلَمٌ غيرُ معروف).

**الترتيبُ مهمّ:** غيابُ البيانات يُسمّى (٣) **قبل** أيّ طلبِ صفحة — وإلّا صار غيابُها «صفحةً غيرَ مؤهَّلة» (٤).

**المحرّك:** macOS Vision (`VNRecognizeTextRequest`) عبر `pyobjc` في **بيئةٍ معزولة** — ليست من
متطلّبات المشروع. غيابُه يُطفئ الأداة برسالة، ولا يكسر شيئًا (نصفُ المقارنة يعمل بلا محرّك).

**الصفحاتُ الخمسُ ثابتٌ مُجمَّدٌ مُعلَن:** `PUBLISHED_PAGES` هي الصفحاتُ التي قِيس عليها الرقمُ المنشور.
اشتُقّت مرّةً واحدةً بقاعدةِ توزيعٍ على المُؤهَّل (`[i*len//5 for i in range(5)]`)، ثم **جُمِّدت** — لأنّ
المُؤهَّلَ نفسَه يتغيّر مع كلّ دفعةِ التقاطٍ جديد، فإعادةُ تطبيق القاعدة اليومَ تُعطي أرقامًا أخرى. فالخيارُ
المُعلَنُ هو التجميدُ باسمِه، لا ادّعاءُ أنّ القاعدةَ تُنتجها في كلّ وقت. و`--list` يطبع المجموعةَ المُجمَّدة
والمُؤهَّلَ الحاليَّ معًا فلا يختلطان.

**قاعدةُ الأرقام (درسُ أ-٧):** الفواصلُ العربيّة تُوحَّد **بحكم موقعها**: آخرُ فاصلٍ يليه كسرٌ (خانةٌ أو
خانتان) ⇒ عشريّ، وما عداه ⇒ آلاف. وتُقاس **ثلاثُ** قواعدِ مطابقةٍ لا واحدة: `شكل` (الكانونيّ نصًّا) ·
`قيمة` (`Decimal` — وهي التي أنتجت الرقمَ المنشور) · `أرقام` (مجرَّدةٌ من كل فاصل).
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

# الأسماءُ الثلاثة في موضعٍ واحد — والتوقيعُ يقول نوعَ كلّ مجموعة: «شكل» و«أرقام» نصّان، و«قيمة» أعداد.
RULES: tuple[str, ...] = ("شكل", "قيمة", "أرقام")
RuleSets = dict[str, set]

EXIT_OK, EXIT_NO_ENGINE, EXIT_NO_DATA, EXIT_NOT_ELIGIBLE, EXIT_BAD_ARGS = 0, 2, 3, 4, 5

AR_INDIC = {ord(c): ord("0") + i for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}
AR_EXTENDED = {ord(c): ord("0") + i for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")}
ALL_SEPS = ".,،٫٬"
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
    """
    t = to_ascii_digits(tok).strip()
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
    """القاعدةُ الثانية: **قيمةٌ** عدديّة (`Decimal` لا نصًّا) — وهي القاعدةُ التي جاء منها الرقمُ المنشور.

    `Decimal("999") == Decimal("999.00")` بينما `"999" != "999.00"`: من قارن النصَّ أهدر استرجاعًا كان
    بيده (قِيست الفجوة: ٣٧.١٪ ⟶ ٤٨.٦٪ على الصفحات الخمس).
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


def numeric_sets(text: str) -> RuleSets:
    """ثلاثُ مجموعاتٍ من نصٍّ واحد: `شكل` (نصّ) · `قيمة` (`Decimal`) · `أرقام` (نصّ، ≥خانتين)."""
    out: RuleSets = {name: set() for name in RULES}
    for raw in TOKEN.findall(to_ascii_digits(text)):
        c = canonical(raw)
        if c:
            out["شكل"].add(c)
        v = value_of(raw)
        if v is not None:
            out["قيمة"].add(v)
        d = digits_of(raw)
        if _accept_digits(d):
            out["أرقام"].add(d)
    return out


def design_candidates() -> list[pathlib.Path]:
    """كلُّ تصميمٍ في `data/training/` فيه صفحاتٌ (قد يوجد أكثر من واحد)."""
    base = ROOT / DESIGN_ENV
    return sorted(p for p in base.glob("*") if p.is_dir() and any(p.glob("pg-*")))


def design_dir(design: str | None = None) -> pathlib.Path:
    """مجلّدُ التصميم: صريحًا، أو **الأوّلُ الذي يحمل الصفحاتِ المُجمَّدة** فلا يُعاد قياسٌ على غيرها."""
    if design:
        return (ROOT / DESIGN_ENV) / design
    dirs = design_candidates()
    for d in dirs:
        # من الأرقام التي تحملها الحقيقةُ لا من اسم المجلّد (الأسماءُ مُصفَّرة: pg-001)
        pool = {int(lab["page"]) for _, lab, _ in eligible(d.name)}
        if set(PUBLISHED_PAGES) <= pool:
            return d
    return dirs[0] if dirs else (ROOT / DESIGN_ENV / "-")


def eligible(design: str | None = None) -> list[tuple[pathlib.Path, dict, list]]:
    """الصفحاتُ المُؤهَّلة بترتيب الرقم: فيها `page.png` و`label.json` و`len(rows) >= MIN_ROWS`."""
    out = []
    for d in sorted(design_dir(design).glob("pg-*"), key=lambda p: int(p.name.split("-")[1])):
        lj, png = d / "label.json", d / "page.png"
        if not (png.exists() and lj.exists()):
            continue
        lab = json.loads(lj.read_text(encoding="utf-8"))
        rows = lab.get("rows") or []
        if len(rows) >= MIN_ROWS:
            out.append((d, lab, rows))
    return out


def selected(pages: tuple[int, ...] = PUBLISHED_PAGES,
             design: str | None = None) -> list[tuple[pathlib.Path, dict, list]]:
    """يجد الأرقامَ المطلوبة في المُؤهَّل، ويرفع `IneligiblePage` باسمِ الصفحة والمؤهَّلِ اليوم."""
    pool = {int(lab["page"]): (d, lab, rows) for d, lab, rows in eligible(design)}
    out = []
    for p in pages:
        if p not in pool:
            raise IneligiblePage(f"صفحةٌ غيرُ مؤهَّلة: {p} (المُؤهَّلُ اليوم: {sorted(pool)})")
        out.append(pool[p])
    return out


def _truth_form(val) -> str:
    """الرقمُ في `label.json` عددٌ لا نصّ (`999.9` كمثال) ⇒ يُصاغ كما يُطبع بكسرين، ولا يُقاس على `str()`."""
    if isinstance(val, bool) or not isinstance(val, (int, float, Decimal)):
        return str(val)
    d = Decimal(str(val))
    return str(int(d)) if d == d.to_integral_value() else f"{d:.2f}"


def truth_sets(rows: list) -> dict[str, RuleSets]:
    """الحقيقةُ الأرضيّة **مفصولةً بكل قاعدةٍ على حِدة** — خلطُ القواعد في مجموعةٍ واحدة يخلق مطابقاتٍ كاذبة.

    والقياسُ على **`printed_amount`** وحدَه: هو ما على الورق، وهو ما يُقابله القارئ. وصفٌّ بلا
    `printed_amount` يُسقَط من العمود — لا يُقابَل بمقدارٍ مشتقٍّ من السلسلة لم يُطبَع.
    """
    out: dict[str, RuleSets] = {k: {name: set() for name in RULES} for k in ("مبالغ", "أرصدة")}
    for r in rows:
        for group, val in (("مبالغ", r.get("printed_amount")), ("أرصدة", r.get("balance"))):
            if val in (None, ""):
                continue
            s = _truth_form(val)
            for name, form in (("شكل", canonical(s)), ("قيمة", value_of(s)), ("أرقام", digits_of(s))):
                if name == "أرقام":
                    if _accept_digits(form):
                        out[group][name].add(form)
                elif form not in (None, ""):
                    out[group][name].add(form)
    return out


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


def _list_lines(design: str | None) -> list[str]:
    pool = eligible(design)
    if not pool:
        return [_no_data_message(design)]
    return [
        f"التصميمُ المُكتشف: {design_dir(design).name} · المُؤهَّلُ الآن: {len(pool)} صفحة (≥{MIN_ROWS} صفوف)",
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

    if args.list:
        lines = _list_lines(args.design)
        print("\n".join(lines))
        return EXIT_NO_DATA if lines[0].startswith("لا بياناتِ") else EXIT_OK

    try:
        pages = _parse_pages(args.pages)   # **الوسيطُ يُدقَّق قبل البيانات:** لا يُقال «لا بيانات» لوسيطٍ مشوَّه
    except BadArguments as exc:
        print(f"⛔ وسيطٌ مشوَّه: {exc}")
        return EXIT_BAD_ARGS

    if not eligible(args.design):
        # **غيابُ البيانات يُسمّى (٣) قبل أيّ طلبِ صفحة** — وإلّا سُمّي «صفحةً غيرَ مؤهَّلة» (٤) كذبًا.
        print(f"⛔ {_no_data_message(args.design)}")
        return EXIT_NO_DATA
    try:
        chosen = selected(pages, args.design)
    except IneligiblePage as exc:
        print(f"⛔ {exc}")
        return EXIT_NOT_ELIGIBLE

    totals = {k: [0, 0] for k in ("مبالغ", "أرصدة")}
    print(f"{'صفحة':>6} {'صفوف':>5} " + " ".join(f"{n:>9}" for n in RULES) + f" {'أرصدة':>9}")
    for d, lab, rows in chosen:
        try:
            found = numeric_sets(ocr(d / "page.png"))
        except RuntimeError as exc:
            print(f"⛔ {exc}")
            return EXIT_NO_ENGINE
        truth = truth_sets(rows)
        hits = {name: len(truth["مبالغ"][name] & found[name]) for name in RULES}
        bh = len(truth["أرصدة"]["قيمة"] & found["قيمة"])
        totals["مبالغ"][0] += len(truth["مبالغ"]["قيمة"])
        totals["مبالغ"][1] += hits["قيمة"]
        totals["أرصدة"][0] += len(truth["أرصدة"]["قيمة"])
        totals["أرصدة"][1] += bh
        print(f"{lab['page']:>6} {len(rows):>5} " + " ".join(f"{hits[n]:>9}" for n in RULES)
              + f" {bh:>9}")

    amt_n, amt_h = totals["مبالغ"]
    bal_n, bal_h = totals["أرصدة"]
    print("-" * 58)
    if amt_n == 0 or bal_n == 0:
        # **لا نسبةَ بمقامٍ صفريّ:** كان هذا ينفجر بـ`ZeroDivisionError` (تتبّعٌ خامٌ ورمز ١) لمّا تُسقَط
        # كلُّ الصفوف بلا مبلغٍ مطبوع؛ والرفضُ يُسمّى ولا يُحسَب رقمٌ كاذب.
        missing = "المبالغ" if amt_n == 0 else "الأرصدة"
        print(f"⛔ لا مقامَ قابلًا للقياس: لا {missing} مطبوعةً في الصفحات المطلوبة ⇒ لا نسبةَ تُحسَب "
              f"(المبالغ {amt_h}/{amt_n} · الأرصدة {bal_h}/{bal_n})")
        return EXIT_NO_DATA
    print(f"قاعدةُ «قيمة» (المنشورة): المبالغ {amt_h}/{amt_n} = {100 * amt_h / amt_n:.1f}٪ · "
          f"الأرصدة {bal_h}/{bal_n} = {100 * bal_h / bal_n:.1f}٪")
    print("حدُّ القياس: استرجاعُ نصٍّ من الورق — لا إغلاقَ سلسلةٍ ولا مطابقةَ تذييل ولا شكلَ صفّ.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
