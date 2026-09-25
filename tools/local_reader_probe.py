"""«قياس ٤» — **أداةُ القارئ المحلّيّ**: كم يسترجع قارئٌ محلّيٌّ مجّانيّ (بلا سحابة) من ورقة كشفٍ ممسوحة؟

**ما يقيسه (وحدُّه المُعلَن):** استرجاعُ **نصِّ** المبالغ والأرصدة المطبوعة، مقابل الحقيقة الأرضيّة في
`data/training/<التصميم>/pg-<رقم>/label.json`. و**لا** يقيس إغلاقَ السلسلة ولا مطابقةَ التذييل — تلك
بوّابةُ «ب-٤» وحدَها، وهذا مِقياسٌ واحدٌ منها.

**لماذا في المستودع:** رقمٌ بلا أداته ليس دليلًا — من أراد إعادةَ القياس يُشغّل:

    python tools/local_reader_probe.py            # يحتاج Vision (ماك)
    python tools/local_reader_probe.py --list     # الصفحاتُ المُختارة بلا قراءة (يعمل في أي بيئة)
    python tools/local_reader_probe.py --pages 187

**المحرّك:** macOS Vision (`VNRecognizeTextRequest`) عبر `pyobjc` في **بيئةٍ معزولة** — ليست من
متطلّبات المشروع. غيابُه يُطفئ الأداة برسالةٍ ورمزِ خروج ٢، ولا يكسر شيئًا (نصفُ المقارنة يعمل بلا محرّك).

**قاعدةُ الصفحات (مكتوبةٌ لتُعاد، لا لتُوصف):** من تصميمٍ واحد، تُرتَّب الصفحاتُ التي فيها `page.png` و
`label.json` و`len(rows) >= 5` بترتيب الرقم، ثم تُؤخذ ٥ موزّعةً `[i*len//5 for i in range(5)]`.
حصيلةُ القاعدة اليوم: `PAGES` أدناه — و`--list` يُظهرها من القرص بلا قراءةِ صورة.

**قاعدةُ الأرقام (درسُ أ-٧):** الفواصلُ العربيّة تُوحَّد **بحكم موقعها**: آخرُ فاصلٍ يليه رقمان ⇒ عشريّ،
وما عداه ⇒ آلاف. وتُقاس **ثلاثُ** قواعدِ مطابقةٍ لا واحدة، لأنّ الواحدة قد تكذب:
`شكل` (الكانونيّ نصًّا) · `قيمة` (Decimal) · `أرقام` (مجرَّدةٌ من كل فاصل).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from decimal import Decimal, InvalidOperation

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGES = (1, 187, 320, 404, 539)
DESIGN_ENV = "data/training"          # التصميمُ يُكتشف من القرص ولا يُكتب في الشيفرة (معرّفٌ في النشرة)
MIN_ROWS = 5
SELECT_N = 5

AR_INDIC = {ord(c): ord("0") + i for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}
AR_EXTENDED = {ord(c): ord("0") + i for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")}
ALL_SEPS = ".,،٫٬"
_SEPS = "[" + re.escape(ALL_SEPS) + "]"
TOKEN = re.compile(r"\d[\d" + re.escape(ALL_SEPS) + r"]*\d|\d")
TRAILING_TWO = re.compile(_SEPS + r"(\d{2})$")


def to_ascii_digits(s: str) -> str:
    """عربيّة-هندية (٠-٩) وفارسيّة (۰-۹) ⇒ لاتينيّة."""
    return s.translate(AR_INDIC).translate(AR_EXTENDED)


def canonical(tok: str) -> str | None:
    """القاعدةُ الأولى: **شكلٌ** كانونيٌّ — الفاصلةُ العشريّةُ تُحدَّد بموقعها (آخر فاصلتين رقمًا)."""
    t = to_ascii_digits(tok).strip()
    if not any(ch.isdigit() for ch in t):
        return None
    m = TRAILING_TWO.search(t)
    if m:
        head = re.sub(_SEPS, "", t[: m.start()])
        if head:
            return f"{head}.{m.group(1)}"
    digits = re.sub(_SEPS, "", t)
    return digits or None


def value_of(tok: str) -> Decimal | None:
    """القاعدةُ الثانية: **قيمةٌ** عدديّة — وهي القاعدةُ التي جاء منها الرقمُ المنشور."""
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


def numeric_sets(text: str) -> dict[str, set[str]]:
    """يجمع ثلاثَ مجموعاتٍ من نصٍّ واحد: شكل · قيمة · أرقام."""
    out: dict[str, set[str]] = {"شكل": set(), "قيمة": set(), "أرقام": set()}
    for raw in TOKEN.findall(to_ascii_digits(text)):
        c = canonical(raw)
        if c:
            out["شكل"].add(c)
        v = value_of(raw)
        if v is not None:
            out["قيمة"].add(str(v))
        d = digits_of(raw)
        if d and len(d) >= 2:
            out["أرقام"].add(d)
    return out


def design_dir(design: str | None = None) -> pathlib.Path:
    """مجلّدُ التصميم: صريحًا، أو **مُكتشفًا من القرص** (فتصميمُ الحزمة لا يُكتب في الشيفرة)."""
    base = ROOT / DESIGN_ENV
    if design:
        return base / design
    dirs = sorted(p for p in base.glob("*") if p.is_dir() and any(p.glob("pg-*")))
    if not dirs:
        return base / "-"                     # لا وجود ⇒ يُعالجه `eligible` بالفراغ لا بالانفجار
    return dirs[0]


def eligible(design: str | None = None) -> list[tuple[pathlib.Path, dict, list]]:
    """الصفحاتُ المُؤهَّلة بترتيب الرقم (تُبنى من القرص — وهي مصدرُ `PAGES`)."""
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


def selected(pages: tuple[int, ...] = PAGES, design: str | None = None) -> list[tuple[pathlib.Path, dict, list]]:
    """يختار الأرقامَ المطلوبة من المُؤهَّلة (ويُسقط برسالةٍ ما ليس مؤهَّلًا)."""
    pool = {int(lab["page"]): (d, lab, rows) for d, lab, rows in eligible(design)}
    out = []
    for p in pages:
        if p not in pool:
            raise SystemExit(f"صفحةٌ غيرُ مؤهَّلة: {p} (المُؤهَّلُ اليوم: {sorted(pool)})")
        out.append(pool[p])
    return out


def _truth_form(val) -> str:
    """الرقمُ في `label.json` عددٌ لا نصّ (`999.9` كمثال) ⇒ يُصاغ كما يُطبع بكسرين، ولا يُقاس على `str()`."""
    if isinstance(val, bool) or not isinstance(val, (int, float, Decimal)):
        return str(val)
    d = Decimal(str(val))
    return str(int(d)) if d == d.to_integral_value() else f"{d:.2f}"


def truth_sets(rows: list) -> dict[str, dict[str, set[str]]]:
    """الحقيقةُ الأرضيّة **مفصولةً بكل قاعدةٍ على حِدة** — خلطُ القواعد في مجموعةٍ واحدة يخلق مطابقاتٍ كاذبة."""
    out: dict[str, dict[str, set[str]]] = {k: {"شكل": set(), "قيمة": set(), "أرقام": set()}
                                           for k in ("مبالغ", "أرصدة")}
    for r in rows:
        amt = r.get("printed_amount") or r.get("proven_amount")
        for group, val in (("مبالغ", amt), ("أرصدة", r.get("balance"))):
            if val in (None, ""):
                continue
            s = _truth_form(val)
            for name, form in (("شكل", canonical(s)), ("قيمة", value_of(s)), ("أرقام", digits_of(s))):
                if form not in (None, ""):
                    out[group][name].add(str(form))
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
        return PAGES
    try:
        return tuple(int(x) for x in raw.replace(" ", "").split(",") if x)
    except ValueError as exc:
        raise SystemExit(f"--pages يحتاج أرقامًا مفصولةً بفواصل: {raw}") from exc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="قياسٌ محلّيّ لاسترجاع المبالغ والأرصدة من صور الكشوف")
    ap.add_argument("--list", action="store_true", help="اسرد الصفحات المؤهَّلة والمختارة (بلا قراءة)")
    ap.add_argument("--pages", help="أرقامُ صفحاتٍ بديلةٌ مفصولةٌ بفواصل")
    ap.add_argument("--design", default=None, help="معرّفُ تصميم الحزمة (والافتراض: يُكتشف من القرص)")
    args = ap.parse_args(argv)

    if args.list:
        pool = eligible(args.design)
        if not pool:
            print(f"لا بياناتِ تدريبٍ محلّيّة للتصميم {args.design or '(غيرُ مُكتشف)'} — الحزمةُ لا تُشحن، "
                  f"والقياسُ يحتاج نسخةً محلّيّة من `data/training/`")
            return 3
        print(f"المُؤهَّل: {len(pool)} صفحة (≥{MIN_ROWS} صفوف) · التصميم: {design_dir(args.design).name}")
        print("المختارُ بقاعدة التوزيع: " + ", ".join(f"pg-{lab['page']}" for _, lab, _ in
                                                       selected(PAGES, args.design)))
        return 0

    pages = _parse_pages(args.pages)
    rule_names = ("شكل", "قيمة", "أرقام")
    totals = {k: [0, 0] for k in ("مبالغ", "أرصدة")}
    print(f"{'صفحة':>6} {'صفوف':>5} " + " ".join(f"{n:>9}" for n in rule_names) + f" {'أرصدة':>9}")
    for d, lab, rows in selected(pages, args.design):
        try:
            found = numeric_sets(ocr(d / "page.png"))
        except RuntimeError as exc:
            print(f"⛔ {exc}")
            return 2
        truth = truth_sets(rows)
        hits = {name: len(truth["مبالغ"][name] & found[name]) for name in rule_names}
        bh = len(truth["أرصدة"]["قيمة"] & found["قيمة"])
        totals["مبالغ"][0] += len(truth["مبالغ"]["قيمة"])
        totals["مبالغ"][1] += hits["قيمة"]
        totals["أرصدة"][0] += len(truth["أرصدة"]["قيمة"])
        totals["أرصدة"][1] += bh
        print(f"{lab['page']:>6} {len(rows):>5} " + " ".join(f"{hits[n]:>9}" for n in rule_names)
              + f" {bh:>9}")

    amt_n, amt_h = totals["مبالغ"]
    bal_n, bal_h = totals["أرصدة"]
    print("-" * 58)
    print(f"قاعدةُ «قيمة» (المنشورة): المبالغ {amt_h}/{amt_n} = {100 * amt_h / amt_n:.1f}٪ · "
          f"الأرصدة {bal_h}/{bal_n} = {100 * bal_h / bal_n:.1f}٪")
    print("حدُّ القياس: استرجاعُ نصٍّ من الورق — لا إغلاقَ سلسلةٍ ولا مطابقةَ تذييل ولا شكلَ صفّ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
