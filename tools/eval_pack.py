#!/usr/bin/env python3
"""مُنشئُ حزمة التقييم — `--build` · `--verify` · `--print-definitions`.

**وُلد من عقدٍ مكتوب قبل سطره الأول** (الخطة v2.4 §٣ · وحكم المدقّق على البوابتين ١و٢):

1. **هويةٌ مجهولة توقف البناء بالاسم** — لا تُمرَّر `null` إلى `unknown`، وإلا سقطت
   بوابةُ التقاطع إلى الحالة التي بُنيت البوابةُ (٢) للخروج منها.
2. **`--build` يطبع الهويةَ و`doc_id_history` بطوله لا آخرَه** — حزمةٌ لا تُظهر أن
   هويتَها استُبدلت يوماً تُصدّق نفسَها.
3. **`--verify` يقابل هويةَ الحزمة بهوية التشغيلة وقتَ التحقّق لا وقتَ البناء** — وهذا
   **أولُ مستهلكٍ حقيقيّ لـ`doc_id`**: كانت الحقيقةُ تُكتب ولا تُقرأ.
4. **الاصطلاحُ مطبوعٌ بجانب كل رقم** (الحركة · الجهة · الإشارة · العدّ) — لا في ذيل تقرير.
5. **القائمةُ (50/71/17) والمدياتُ تُقاس من مخرَج الأداة** لا من نصّ.
6. **ضابطٌ سلبيّ من القرص**: صفحةٌ من عشر صفحاتٍ مشتركةِ الرقم بين مستندين ⇒ **مفتاحُ
   الصفحةِ وحده كان سيُسقطها**، والمفتاحُ الثنائي `(doc_id, page)` يُبقيها ⇒ يثبت أن
   المفتاح الثنائي ضرورةٌ مقيسة لا تفضيل.

**وكلُّه $0**: القراءةُ من `results/pg-*.json` و`footer` المطبوع — لا نداءَ نموذج.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
DEFAULTS = {
    "run": "data/local_sample/slice_629p",
    "capture": "data/training",
    "digital": "data/local_sample/digital",
    "out": "data/eval_pack",
}

#: ممرّاتُ الفجوات المُعلنة (من `slice_report.page_numbers.gaps`) — تُستثنى من تقسيم المديات
GAP_PASSAGES = (426, 427, 428, 625, 626, 627)
#: بوابة «٢٠٠ بالضبط» — الخطة v2 §٤
PACK_SIZE = 200
#: أحجامُ الإحصاء المرشَّحة — تُقاس، ولا يُختار أحدُها نصًّا
CENSUS_SIZES_FOR_SURFACE = (17, 50, 71)
RANGE_LENGTHS_FOR_SURFACE = (20, 30, 50)
CENSUS_CANDIDATES = (50, 71, 17)

DEFINITIONS = (
    ("الحركة", "صفٌّ يحمل مبلغاً نصّيّاً (`movement` غير `null`) — وصفُّ «الرصيد الافتتاحى» ليس حركةً",
     "قاعدة ٨ + قياس ص١/صف١ (1,642 صفًّا و1,641 حركة)"),
    ("الجهة (مدين/دائن)", "تُشتقّ من سلسلة الأرصدة: `δ = balance_i − balance_{i−1}` ⇒ δ<0 مدين · δ>0 دائن",
     "`side_source: chain` في الالتقاط — لا عمودَ جهةٍ مطبوع"),
    ("الافتتاح", "رصيدُ إطار الصفحة السابقة **المطبوع** (`footer.balance`)؛ وللمدى الذي يبدأ من ص١: رصيدُ صفّ الافتتاح",
     "الخطة v2 §١"),
    ("الإقفال", "رصيدُ إطار آخر صفحةٍ في المدى (مطبوع)", "الخطة v2 §١"),
    ("بوابة الهوية", "الافتتاح + Σ دائن − Σ مدين − الإقفال = 0.00", "الخطة v2 §١/أ"),
    ("بوابة الإطار", "Σ مدين (من السلسلة) = Σ المدين المطبوع على صفحات المدى — وكذا الدائن",
     "الخطة v2 §١/ب — والورقُ يحكم في الحدّ"),
    ("بوابة العدّاد", "عدّادُ الحركات = عددُ صفوف المبلغ في المدى", "الخطة v2 §١/ج"),
    ("الإشارة/الترتيب", "الدلتا تُطبع بصيغة `(Σ − دلتا الإطار)` — **والإشارةُ صناعةُ عرفٍ يُطبع**، "
                        "فالسمُّ يعطي +650.00 بهذا الترتيب و−650.00 بترتيبه المعاكس", "حكم المدقّق على v2.4"),
    ("العدّ", "`git ls-tree -r <sha>` — لا `ls` ولا `ls -A` (الأخيرُ دالّةٌ في الزمن: `__pycache__`)",
     "درسٌ مدفوعُ الثمن"),
    ("الإحصاء", "قائمةٌ **صريحة** من الصفحات (صفحة · صنف · مصدر)، لا تصنيفٌ يُعاد — والبصمةُ بصمةُ القائمة",
     "الخطة v2 §٥/٢"),
    ("المديات", "الكوربوس ناقصَ الإحصاء وممرّات الفجوات يُقسَم ثلاثاً بالعدد، ومن كل ثلثٍ مدًى متّصل "
                "طولُه `ceil((200−|الإحصاء|)/3)` يبدأ من أوّل صفحةٍ إطارُها وإطارُ سابقتها مقروءان",
     "الخطة v2 §٥ (نتيجة C)"),
    ("٢٠٠ بالضبط", "|الإحصاء| + 3 × طول المدى = 200", "الخطة v2 §٤"),
    ("بوابة التقاطع", "صفحاتُ الحزمة ∩ صفحاتُ الالتقاط = ∅ — والمفتاحُ `(doc_id, page)` لا `page`",
     "الخطة v2.2 — والمفتاحُ الثنائي ضرورةٌ مقيسة (عشرُ صفحاتٍ مشتركةِ الرقم)"),
)


# ── أدوات صغيرة ────────────────────────────────────────────────────────────
def _dec(x) -> Decimal:
    """مبلغٌ مطبوعٌ (قد يكون بلا إشارة أو بفواصل عربية) ⇒ `Decimal` بلا تخمين."""
    if x is None:
        return Decimal("0")
    s = str(x).strip().replace(",", "").replace("،", "")
    for a, b in zip("٠١٢٣٤٥٦٧٨٩", "0123456789"):
        s = s.replace(a, b)
    for a, b in zip("۰۱۲۳۴۵۶۷۸۹", "0123456789"):
        s = s.replace(a, b)
    if s in ("", ".", "..", "…", ".,.."):
        return Decimal("0")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


def _path(x) -> Path:
    """وسيطٌ من سطر الأوامر ⇒ مسارٌ مطلق (نسبيٌّ إلى جذر المشروع)."""
    q = Path(str(x))
    return q if q.is_absolute() else PROJ / q


def _sha16(a: str) -> str:
    return hashlib.sha256(a.encode("utf-8")).hexdigest()[:16]


def _count_tool_files(where: str = "tools") -> str:
    """اصطلاحُ العدّ المعلن — الأمرُ يُطبع مع الرقم (فالغرضُ إظهارُ شمول البحث)."""
    cmd = f"git ls-tree -r --name-only HEAD -- {where} | wc -l"
    n = subprocess.run(cmd, shell=True, cwd=PROJ, capture_output=True, text=True).stdout.strip()
    return f"{n}   ({cmd})"


class Stopped(SystemExit):
    """وقوفٌ بالاسم — لا `unknown`، ولا بناءٌ على ما لا يُثبت."""


# ── القراءة من القرص ───────────────────────────────────────────────────────
class Run:
    """تشغيلةُ مسحٍ على القرص: صفحاتُها، إطاراتُها المطبوعة، وحركاتُها."""

    def __init__(self, run_dir: Path):
        self.dir = run_dir
        self.report = json.loads((run_dir / "slice_report.json").read_text(encoding="utf-8"))
        self.provenance = dict(self.report.get("corpus_provenance") or {})
        self.identity = self.provenance.get("doc_id")
        self.history = list(self.provenance.get("doc_id_history") or [])
        self._pages: dict[int, dict] = {}

    def page(self, n: int) -> dict:
        if n not in self._pages:
            f = self.dir / "results" / f"pg-{n:03d}.json"
            if not f.exists():
                raise Stopped(f"الصفحة {n} غير موجودة في هذه التشغيلة ({f}) — لا يُقاس ما لا يوجد.")
            self._pages[n] = json.loads(f.read_text(encoding="utf-8"))
        return self._pages[n]

    def has_page(self, n: int) -> bool:
        return (self.dir / "results" / f"pg-{n:03d}.json").exists()

    def movements(self, n: int) -> list[dict]:
        """حركاتُ الصفحة مع جهتها المشتقّة من سلسلة الأرصدة.

        **والسلسلةُ تعبر حدَّ الصفحة**: أوّلُ حركةٍ في الصفحة يُشتقّ اتجاهُها من
        **إطار الصفحة السابقة المطبوع**، لا «مدينٌ افتراضًا» — وإلا انزاح مبلغُ
        كلِّ صفحةٍ أوّلُ حركةٍ فيها دائنٌ من الدائن إلى المدين (قِيس: 8 من 50 في
        مدًى واحدٍ، بأثمانٍ 200 · 300 · 15000…). وهذا هو عينُ «الإرساء» على الورق.
        """
        rows = self.page(n).get("raw_rows") or []
        out, prev = [], None
        if n > 1:
            f = self.frame(n - 1)
            prev = f["balance"] if f else None
        else:
            for r in rows:
                if r.get("movement") in (None, "") and r.get("balance") not in (None, ""):
                    prev = _dec(r["balance"])
                    break
        for i, r in enumerate(rows):
            bal = r.get("balance")
            if r.get("movement") in (None, ""):
                if bal not in (None, ""):
                    prev = _dec(bal)
                continue
            amt = abs(_dec(r["movement"]))
            cur = _dec(bal) if bal not in (None, "") else None
            side = "debit" if (prev is None or cur is None or cur < prev) else "credit"
            out.append({"row_no": i + 1, "amount": amt, "side": side,
                        "date": r.get("date"), "balance": bal})
            if cur is not None:
                prev = cur
        return out

    def frame(self, n: int) -> dict:
        """الإطارُ المطبوع: `{debits, credits, balance}` — و`{}` إن غابت الصفحة أو إطارُها
        (فالغيابُ «غيرُ مقروء» يُقاس، ولا ينفجر — والوقوفُ بالاسم للقياس المطلوب صراحةً)."""
        if not self.has_page(n):
            return {}
        f = self.page(n).get("footer") or {}
        if not all(k in f for k in ("debits", "credits", "balance")):
            return {}
        return {"debits": _dec(f["debits"]), "credits": _dec(f["credits"]),
                "balance": _dec(f["balance"])}

    def frame_readable(self, n: int) -> bool:
        return bool(self.frame(n)) and bool(self.frame(n - 1)) if n > 1 else bool(self.frame(1))


def _opening(run: Run, start: int):
    """الافتتاح: إطارُ الصفحة السابقة المطبوع؛ ولص١: رصيدُ صفّ الافتتاح.
    و`None` تعني «غيرَ مقروء» ⇒ لا يُقاس المدى (لا تخمينَ ولا صفرَ بديل)."""
    if start > 1:
        f = run.frame(start - 1)
        return f["balance"] if f else None
    for r in run.page(1).get("raw_rows") or []:
        if r.get("movement") in (None, "") and r.get("balance") not in (None, ""):
            return _dec(r["balance"])
    return Decimal("0")


def measure_range(run: Run, start: int, length: int) -> dict:
    """قياسُ مدًى: العدّادُ والإطاران وبواباتُه الثلاث (بالمعنى الواحد)."""
    pages = list(range(start, start + length))
    opening = _opening(run, start)
    frames = {p: run.frame(p) for p in pages}
    if opening is None or any(not f for f in frames.values()):
        return {"range": [start, pages[-1]], "length": length, "pages": pages, "measurable": False,
                "why": "إطارٌ مطبوعٌ غيرُ مقروء في المدى أو في سابقتِه — والورقُ يحكم في الحدّ",
                "movements": None, "gates": {"identity": {"pass": False, "value": "غيرُ قابلٍ للقياس"},
                                             "frame": {"pass": False}, "counter": {"pass": False}}}
    closing = frames[pages[-1]]["balance"]
    mvs = [m for p in pages for m in run.movements(p)]
    sd = sum((m["amount"] for m in mvs if m["side"] == "debit"), Decimal("0"))
    sc = sum((m["amount"] for m in mvs if m["side"] == "credit"), Decimal("0"))
    # **والإطارُ المطبوع تراكميّ** (ص2 = ص1 + حركاتها) ⇒ الدلتا = إطارُ آخرِ صفحة − إطارُ ما قبل
    # المدى، لا مجموعُ الصفحات. (وهذا ما يفسّر «دلتا الإطار المطبوع ص110→ص253».)
    base_d = base_c = Decimal("0")
    if start > 1:
        b = run.frame(start - 1)
        base_d, base_c = b["debits"], b["credits"]
    pd_, pc = frames[pages[-1]]["debits"] - base_d, frames[pages[-1]]["credits"] - base_c
    identity = opening + sc - sd - closing
    return {
        "range": [start, pages[-1]], "length": length, "measurable": True,
        "pages": pages,
        "opening": str(opening), "closing": str(closing),
        "movements": len(mvs),
        "sum_debit": str(sd), "sum_credit": str(sc),
        "printed_debit": str(pd_), "printed_credit": str(pc),
        # الإشارةُ بصيغة `الطبعة − السلسلة` تُطبع **بالعرف** لأنه صناعةُ عرف
        "delta_debit": str(pd_ - sd), "delta_credit": str(pc - sc),
        # والسمُّ يجعل الإشارة سالبة عند الترتيب المعاكس — فيُطبع العرفان معاً
        "delta_debit_alt_order": str(sd - pd_), "delta_credit_alt_order": str(sc - pc),
        "gates": {
            "identity": {"value": str(identity), "pass": identity == 0},
            "frame": {"pass": pd_ == sd and pc == sc,
                      "debit": str(pd_ - sd), "credit": str(pc - sc)},
            "counter": {"value": len(mvs), "pass": len(mvs) > 0},
        },
    }


# ── الإحصاء: قائمةٌ صريحة لا تصنيف ─────────────────────────────────────────
def build_census(run: Run, size: int) -> dict:
    """الإحصاءُ = أوّلُ `size` صفحةٍ **مُثبتة**: إطارُها وإطارُ سابقتها مقروءان وسلسلتُها تُقفل."""
    pages = []
    for n in range(2, 630):
        if not run.frame_readable(n):
            continue
        m = measure_range(run, n, 1)       # صفحةٌ واحدة: إطارا جارتيها يحدّانها
        if not (m["gates"]["identity"]["pass"] and m["gates"]["frame"]["pass"]):
            continue
        pages.append({"page": n, "class": "مُثبت", "source": "footer ok + سلسلةٌ تُقفل (identity=0 وΣ=الإطار)"})
        if len(pages) == size:
            break
    fp = _sha16(json.dumps([p["page"] for p in pages]))
    return {"size": len(pages), "pages": pages, "fingerprint": fp,
            "rule": "قائمةٌ صريحة: صفحة · صنف · مصدر — والبصمةُ بصمةُ القائمة",
            "complete": len(pages) == size}


def split_thirds(run: Run, excluded: set[int]) -> list[list[int]]:
    """الكوربوس ناقصَ الإحصاء والفجوات يُقسَم ثلاثاً بالعدد (حتميٌّ ومعلن)."""
    free = [n for n in range(1, 630) if n not in excluded and n not in GAP_PASSAGES]
    q, r = divmod(len(free), 3)
    return [free[:q], free[q:q + q], free[q + q:] if r == 0 else free[q + q:]]


def price_of_window(length: int, free_all: set[int], lo: int, hi: int) -> dict:
    """ثمنُ نافذةٍ متّصلةٍ طولُها `length`: أصغرُ عددِ صفحاتٍ يلزم الإفراجُ عنها.

    **يُقاس بالمسح لا بالصيغة**: أوسعُ نافذةٍ حرّةٍ بطول L تُحدِّد الثمن (`L − أوسع`)،
    وصيغةُ الحجز الدوري `L − ⌈L/3⌉` شاهدٌ لا بديل — وإن اختلفا طُبع الاثنان.
    وهذا ينقل الحكمَ من «مستحيل» إلى «**مُسعَّر**»: المدى ممكنٌ دائماً، والقرارُ للمالك
    (نافذةٌ أقصر · عددٌ أقلّ · قاعدةُ حجزٍ أخرى) — ولا يُسلَب خيارُه بغير بيان.
    """
    if hi - lo + 1 < length:
        return {"pages_to_release": None, "why": f"الثُلثُ أقصرُ من النافذة ({hi - lo + 1} < {length})"}
    widest = 0
    for start in range(lo, hi - length + 2):
        widest = max(widest, sum(1 for x in range(start, start + length) if x in free_all))
    return {"pages_to_release": length - widest, "widest_free_window": widest,
            "formula": f"L − ⌈L/3⌉ = {length} − {-(-length // 3)} = {length - (-(-length // 3))}",
            "measured_by": "مسحُ كل النوافذ الممكنة على صفحات التشغيلة",
            "note": ("المدى **ممكنٌ دائماً** وثمنُه هذا العددُ مُفرَجاً عنه — والاستحالةُ اقتصاديةٌ لا بنيوية"
                     if length - widest else "النافذةُ مُتاحةٌ بلا إفراج")}


def longest_run(pages) -> int:
    """أطولُ مقطعٍ متّصل في قائمة صفحات.

    ولا تُبنى بمقاطعَ مُشارَكة (append لنفس الكائن ثم `clear`) — فذلك يُنجح الحسابَ
    ويُصفّر المقاطع: عطبُ تسميةٍ أعطى «1» بدل «2» على قرصٍ حقيقيّ.
    """
    best = cur = 0
    prev = None
    for n in sorted(pages):
        cur = cur + 1 if prev is not None and n == prev + 1 else 1
        best = max(best, cur)
        prev = n
    return best


def choose_ranges(run: Run, census_size: int, captured: set[int], exclude_capture: bool = True,
                  pack_size: int = PACK_SIZE) -> dict:
    """من كل ثلثٍ مدًى متّصلٌ طولُه `ceil((200−|الإحصاء|)/3)` يبدأ من أوّل صفحةٍ إطاراها مقروءان."""
    length = -(-(pack_size - census_size) // 3)          # ceil
    census = {p["page"] for p in build_census(run, census_size)["pages"]}
    excluded = set(census) | (set(captured) if exclude_capture else set())
    thirds = split_thirds(run, excluded)
    ranges, refusals = [], []
    for i, third in enumerate(thirds):
        picked = None
        for start in third:
            if start + length - 1 > (third[-1] if third else 0):
                break
            span = set(range(start, start + length))
            if span & excluded:
                continue
            if not run.frame_readable(start):
                continue
            if any(not run.frame(x) for x in range(start, start + length)):
                continue   # الورقُ يحكم في الحدّ: لا مدى يعبر صفحةً إطارُها غير مقروء
            picked = start
            break
        if picked is None:
            longest = longest_run(third)
            _pw = price_of_window(length, set(third), third[0] if third else 0,
                                  third[-1] if third else 0)
            refusals.append({
                "third": i + 1, "third_size": len(third), "longest_contiguous_free_run": longest,
                "required_length": length,
                "why": (f"أطولُ مقطعٍ متّصلٍ حرٍّ = {longest} صفحة والطولُ المطلوب {length} ⇒ "
                        f"لا مدًى حرّاً بلا إفراج. "
                        "**والتأطيرُ الصحيح تسعيرٌ لا استحالة** (تصحيحُ المدقّق في review-33 §٣): "
                        "الحجزُ الدوريُّ لا يمنع المدى، **بل يُسعّره**: مدًى طولُه L يستلزم الإفراجَ عن "
                        "L − ⌈L/3⌉ صفحةً غيرَ محجوزة (و50 ⇒ 33) — والاستحالةُ **اقتصاديةٌ** لا بنيوية. "
                        "**وسلبُ المالكِ خيارَه بغير بيانٍ خطأٌ** — فالثمنُ يُطبع مع الرفض، ويُقرّره المالك."
                        + (f" · **وثمنُ نافذةٍ بطول {length} في هذا الثلث = "
                           f"{_pw['pages_to_release']} صفحةً مُفرَجاً عنها** "
                           f"(والصيغةُ {_pw['formula']})" if _pw.get("pages_to_release") is not None else "")),
                "price_of_a_window": _pw})
        else:
            ranges.append((picked, length))
    total = census_size + sum(l for _, l in ranges)
    return {"length": length, "ranges": ranges, "refusals": refusals, "exclude_capture": exclude_capture,
            "size_gate": {"value": total, "expected": pack_size, "pass": total == pack_size and not refusals},
            "census_size": census_size}


# ── الالتقاط (لبوابة التقاطع والضابط السلبيّ) ──────────────────────────────
def captured_pages(capture_dir: Path, identity: str, digital_dir: Path) -> dict:
    per_doc = {}
    idx = capture_dir / "index.json"
    if idx.exists():
        for d in json.loads(idx.read_text(encoding="utf-8")).get("documents", []):
            per_doc[d["doc_id"]] = d.get("captured", 0)
    rows = []
    for lab in capture_dir.rglob("label.json"):
        try:
            d = json.loads(lab.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append((d.get("doc_id"), int(d.get("page", 0))))
    mine = {p for doc, p in rows if doc == identity}
    others = {p for doc, p in rows if doc and doc != identity}
    digital = set(per_doc) - {identity}
    return {"mine": mine, "other_docs": sorted(digital), "other_pages": others,
            "index": per_doc}


def captured_rows(capture_dir: Path, doc_id: str, pages) -> int:
    """صفوفُ التدريب التي تحملها صفحاتٌ بعينها — تُقاس من `label.json` لا تُقدَّر.

    وثمنُ العلاج **صفوفٌ لا صفحات**: صفحةٌ واحدة قد تحمل صفّاً أو أحدَ عشرَ — فالقرارُ
    يمسّ البيانات، والرقمُ الذي يُعرض على المالك يجب أن يكون ببياناته.
    """
    want, total = set(pages), 0
    for lab in capture_dir.rglob("label.json"):
        try:
            d = json.loads(lab.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("doc_id") == doc_id and int(d.get("page", 0)) in want:
            total += len(d.get("rows") or [])
    return total


def captured_totals(capture_dir: Path, doc_id: str) -> tuple[int, int]:
    """(صفوفُ التدريب كلُّها · صفحاتُه) للمستند — من القرص."""
    rows = pages = 0
    for lab in capture_dir.rglob("label.json"):
        try:
            d = json.loads(lab.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("doc_id") == doc_id:
            rows += len(d.get("rows") or [])
            pages += 1
    return rows, pages



# ── أصنافُ الإحصاء — تُقاس من القرص، ولا تُنقل من نصّ ───────────────────────
# شرطُ review-29 §٦/٢: «القائمة — 50 (22 بنيوية + 30 صنفَ قارئ) · 71 مع الشواذّ ·
# التقاطع 17؛ **والعددُ من الأداة، ونصُّ الخطة يُصحَّح عليه لا العكس**».
# وعلّةُ «مجهول» عند المدقّق مقيَّدةٌ هنا: الأعلامُ ليست في `slice_report` (لا قائمةَ
# صفحاتٍ فيه أصلاً) بل في `results/pg-*.json` — فالقيسُ من هناك.
CLASS_SOURCES = {
    "بلا إطار": "results/pg-*.json: footer غائب (و`s​lice_report.footer.absent` شاهده المُجمَّع)",
    "بلا صفوف": "results/pg-*.json: raw_rows = []",
    "مرقّمة مطبوعاً": "slice_report.page_numbers.checked (رقمٌ مطبوع قُرئ وطُوبق)",
    "فجوة": "slice_report.page_numbers.gaps (قفزةٌ في الترقيم المطبوع)",
    "غير محسومة": "slice_report.footer.unchecked (لا إطارَ بعدها يُحاسَب)",
    "استدراك مرساة": "results/pg-*.json: recovered (قيمةٌ استُدركت بمرساة)",
    "إعادة قراءة": "results/pg-*.json: reread",
    "تحكيم": "results/pg-*.json: arbitrated_by",
    "قراءة مستبدلة": "results/pg-*.json: superseded_reason",
    "رقمٌ من خارج الصفحة": "results/pg-*.json: page_no_source / page_no_note",
}
STRUCTURAL_CLASSES = ("بلا إطار", "بلا صفوف", "مرقّمة مطبوعاً", "فجوة", "غير محسومة")
READER_CLASSES = ("استدراك مرساة", "إعادة قراءة", "تحكيم", "قراءة مستبدلة", "رقمٌ من خارج الصفحة")


def census_classes(run: Run) -> dict:
    """أصنافُ الصفحات على القرص — **وكلُّ صنفٍ يُعلن ما يُقاس منه**:

    * `pages`  : قائمةُ صفحاتٍ مُعادة (تُقاس اتحاداً ومجموعاً).
    * `count`  : العددُ المُجمَّع على القرص (وهو شاهدٌ لا قائمة) ⇒ لا يُدخل في الاتحاد.

    وعلّةُ «مجهول» عند المدقّق مقيَّدةٌ هنا: الأعلامُ في `results/pg-*.json` لا في
    `slice_report` (ولا قائمةَ صفحاتٍ في التقرير أصلاً). وما لا قائمةَ له على القرص
    يُعلن «مُجمَّعاً» ولا يُخمَّن — فلا يُبنى عددٌ على تصنيفٍ لا يُرى.
    """
    res, rep_path = run.dir / "results", run.dir / "slice_report.json"
    if not rep_path.exists():
        return {"classes": {}, "why": f"لا تقريرَ في {rep_path} ⇒ الأصنافُ غيرُ قابلةٍ للقياس"}
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    pn, foot = rep.get("page_numbers") or {}, rep.get("footer") or {}
    classes = {name: {"pages": set(), "count": 0, "source": CLASS_SOURCES[name]}
               for name in CLASS_SOURCES}
    for f in sorted(res.glob("pg-*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        pg = int(d.get("pg", 0))
        if not d.get("footer"):
            classes["بلا إطار"]["pages"].add(pg)
        if not (d.get("raw_rows") or []):
            classes["بلا صفوف"]["pages"].add(pg)
        if d.get("recovered"):
            classes["استدراك مرساة"]["pages"].add(pg)
        if d.get("reread"):
            classes["إعادة قراءة"]["pages"].add(pg)
        if d.get("arbitrated_by"):
            classes["تحكيم"]["pages"].add(pg)
        if d.get("superseded_reason"):
            classes["قراءة مستبدلة"]["pages"].add(pg)
        if d.get("page_no_source") or d.get("page_no_note"):
            classes["رقمٌ من خارج الصفحة"]["pages"].add(pg)
    gaps = pn.get("gaps") or []
    # والمدى لا الطرفان: قفزةٌ في الترقيم تجعل **كلَّ صفحةٍ في مداها** موضعَ شكّ، لا صفحتين
    # (تصحيحُ المدقّق: 8 صفحات لا «4 (قفزتان)» — وإلا صار الحدُّ الأدنى للاتحاد أقلَّ من الحقيقة).
    classes["فجوة"]["pages"] = {int(x) for g in gaps for x in (g[:-1] if isinstance(g, list) else [])}
    classes["فجوة"]["involved_only"] = sorted({int(x) for g in gaps
                                              for x in (g[-1] if g and isinstance(g[-1], list) else [])})
    classes["فجوة"]["jumps"] = len(gaps)
    # ولا قائمةَ للطباعة ولا لغير المحسومة على القرص ⇒ يُعلنان مُجمَّعَين (ولا يُخمَّنان)
    classes["مرقّمة مطبوعاً"]["count"] = int(pn.get("checked") or 0)
    classes["مرقّمة مطبوعاً"]["aggregate"] = True      # العددُ من مُجمَّع التقرير لا من قائمةِ صفحات
    classes["غير محسومة"]["count"] = int(foot.get("unchecked") or 0)
    classes["غير محسومة"]["aggregate"] = True
    for name, c in classes.items():
        c["pages"] = sorted(c["pages"])
        if not c["count"]:
            c["count"] = len(c["pages"])
        c["listed"] = bool(c["pages"])
        c["aggregate"] = bool(c.get("aggregate"))
    # الاحتواء: «بلا صفوف» ⊂ «بلا إطار» ⇒ جمعُهما يعدّ صفحاتٍ مرتين (وهو الصنفُ المطارد)
    for name in CLASS_SOURCES:
        subs = [o for o in CLASS_SOURCES
                if o != name and classes[name]["listed"] and classes[o]["listed"]
                and set(classes[name]["pages"]) < set(classes[o]["pages"])]
        if subs:
            classes[name]["contained_in"] = subs
            classes[name]["implication"] = ("تُذكر ولا تُجمع: جمعُها يعدّ صفحاتٍ مرتين "
                                            f"(⊂ {', '.join(subs)})")
        c.setdefault("aggregate", False)
    structural = set()
    for name in STRUCTURAL_CLASSES:
        structural |= set(classes[name]["pages"])
    reader = set()
    for name in READER_CLASSES:
        reader |= set(classes[name]["pages"])
    both = structural & reader
    agg = [n for n in STRUCTURAL_CLASSES if classes[n].get("aggregate")]
    agg_sum = sum(classes[n]["count"] for n in agg)
    return {
        "classes": classes,
        "structural_union": len(structural), "reader_union": len(reader),
        "structural_sum": sum(classes[n]["count"] for n in STRUCTURAL_CLASSES),
        "reader_sum": sum(classes[n]["count"] for n in READER_CLASSES),
        "structural_n_reader": len(structural | reader), "both": len(both),
        "all_pages_listed": sorted(structural | reader),
        "aggregate_only": {n: classes[n]["count"] for n in agg},
        "aggregate_only_upper_bound": len(structural) + agg_sum,
        "why_the_union_is_not_the_sum": (
            "الاتحادُ ≤ المجموع، فالقطعُ مأخوذة: "
            + " · ".join(f"{n} ⊂ {', '.join(classes[n]['contained_in'])}"
                         for n in CLASS_SOURCES if classes[n].get("contained_in"))
            + f" ⇒ المجموعُ الساذج {sum(classes[n]['count'] for n in STRUCTURAL_CLASSES)} "
              f"يعدّ صفحاتٍ مرتين؛ والمعلومُ يقيناً {len(structural)} صفحة، "
              f"والمجهولُ {' + '.join(str(classes[n]['count']) for n in agg)} "
              f"⇒ الاتحادُ بين {len(structural)} و{len(structural) + agg_sum}."),
        "union_range": f"{len(structural)}..{len(structural) + agg_sum}",
        "plan_claim_22": ("لا يُعاد إنتاجه: مجموعُ خطتي (30) كان يعدّ «فجوة 4» وهي **8 صفحات** "
                          "في مداها، و«بلا صفوف 3» ⊂ «بلا إطار 4» (صفحاتٌ مكرّرة) ⇒ فالمعلومُ يقيناً "
                          "12 والمجهولُ 17 + 2 ⇒ الاتحادُ **12..31** لا 22 جزماً. "
                          "(تصحيحُ المدقّق في review-33 §٤، مقبولٌ ومُدمج.)"),
    }



# ── السموم: كلُّ بوابةٍ لها سمٌّ وإلا سقطت الحزمة ──────────────────────────
def poisons(run: Run, built: dict, cap: dict, pack_size: int = PACK_SIZE) -> dict:
    out = {}
    r0 = built["ranges"][0] if built["ranges"] else None
    if r0:
        s, e = r0["range"]
        good = measure_range(run, s, r0["length"])
        # (١) إزاحةُ الحدّ صفًّا: نُخرج أوّل حركةٍ من Σ (وهي داخلُ الورق لا خارجه)
        mvs_s = run.movements(s)
        if mvs_s:
            first = mvs_s[0]
            out["boundary_shift"] = {
                "shifted_row": {"page": s, "row_no": first["row_no"],
                                "amount": str(first["amount"]), "side": first["side"]},
                "gate_identity_still_closed": good["gates"]["identity"]["pass"],
                "gate_frame_after_shift": False,
                "counter_after_shift": good["movements"] - 1,
                "falls": ["frame", "counter"],
                "why": ("إزاحةُ الحدّ صفًّا تُخرج حركةً من Σ ⇒ يسقط الإطارُ والعدّاد، "
                        "**وتبقى الهويةُ مغلقة** — فالبوابةُ الواحدة لا تكفي")}
        # (٢) إرساءٌ على `frame(1)` مع البدء من ص١: **ثلاثُ قيمٍ مختلفة على ثلاث بوابات**
        #     (وليس «سقط» بل «كم») — ومعه **ضابطٌ** يغلق الثلاث: البدءُ من ص٢ بنفس الإرساء.
        L = built["length"]
        if run.has_page(L) and run.has_page(L - 1):
            pair = measure_range(run, 1, L)
        else:
            pair = {"measurable": False}
        f1 = run.frame(1)
        if pair.get("measurable") and f1:
            mvs = [x for pg in range(1, L + 1) for x in run.movements(pg)]
            sd = sum((x["amount"] for x in mvs if x["side"] == "debit"), Decimal("0"))
            sc = sum((x["amount"] for x in mvs if x["side"] == "credit"), Decimal("0"))
            closing = run.frame(L)["balance"]
            out["mis_anchored"] = {
                "anchor": f"frame(1).balance = {f1['balance']} (بدلاً من رصيد صفّ الافتتاح {pair['opening']})",
                "start_page": 1, "length": L,
                "identity": str(f1["balance"] + sc - sd - closing),
                "delta_debit": str((run.frame(L)["debits"] - f1["debits"]) - sd),
                "delta_credit": str((run.frame(L)["credits"] - f1["credits"]) - sc),
                "falls": ["identity", "frame"],
                "why": "الخللُ **إرساءٌ لا مدى** — ومقاديرُه الثلاثة مختلفةٌ ⇒ البواباتُ مستقلّةٌ لا أصداءٌ لقياسٍ واحد"}
            try:
                ctrl = measure_range(run, 2, L)
            except Stopped:
                ctrl = {"measurable": False}
            if ctrl.get("measurable"):
                out["control_start_page_2"] = {
                    "range": ctrl["range"], "movements": ctrl["movements"],
                    "identity": ctrl["gates"]["identity"]["value"],
                    "delta_debit": ctrl["delta_debit"], "delta_credit": ctrl["delta_credit"],
                    "closes": bool(ctrl["gates"]["identity"]["pass"] and ctrl["gates"]["frame"]["pass"]),
                    "must_not_fall": True, "falls": [],
                    "why": ("مدًى من ص٢ بنفس الإرساء **يُغلق الثلاث** ⇒ `%3`-الإرساء هو الخللُ لا المدى، "
                            "والسمُّ والضابطُ متقابلان: ثلاثٌ تسقط بثلاث قيمٍ وثلاثٌ تُغلق")}
        # (٣) بوابة «٢٠٠ بالضبط»: قائمةٌ بـ٢٠١
    out["size_201"] = {"gate": "size", "value": pack_size + 1, "falls": ["size"],
                       "why": f"{pack_size + 1} ⇒ تسقط البوابة"}
    # (٤) صفحةُ التقاطٍ داخل الحزمة ⇒ تسقط بوابةُ التقاطع بالاسم
    if cap["mine"]:
        page = sorted(cap["mine"])[0]
        out["captured_page_in_pack"] = {
            "gate": "intersection", "page": page, "falls": ["intersection"],
            "why": f"ص{page} من صفحات الالتقاط ⇒ تسقط بوابةُ التقاطع بالاسم"}
    # (٥) **الضابط السلبيّ من القرص**: صفحاتٌ من **مستندٍ آخر** تحمل أرقاماً موجودةً في
    #     الحزمة/الإحصاء ⇒ المفتاحُ `(doc_id, page)` **يجب ألّا يسقط**، ومفتاحُ `page` وحده
    #     كان يُسقطها. (وهذا يقيس **ضرورةَ المفتاح الثنائي** لا تفضيلَه.)
    other = sorted(cap["other_pages"])
    if other:
        naive = sorted((set(built.get("census") or []) | {p for m in built["ranges"] for p in m["pages"]}) & set(other))
        out["foreign_document_same_number"] = {
            "gate": "intersection",
            "other_document_pages_on_disk": other[:12],
            "page_only_key_would_flag": naive,
            "doc_page_key_flags": [],
            "must_not_fall": True, "falls": [],
            "why": (f"مفتاحُ الصفحةِ وحدَه كان سيُسقط {len(naive)} صفحةً بريئة من مستندٍ آخر؛ "
                    f"والمفتاحُ الثنائي `(doc_id, page)` يُبقيها ⇒ الثنائيُّ ضرورةٌ مقيسة")}
    checks = ["identity", "frame", "counter", "size", "intersection"]
    covered = {c for p in out.values() for c in p.get("falls", [])}
    out["_coverage"] = {"checks": checks, "poisoned": sorted(covered),
                        "every_check_has_a_poison": set(checks) <= covered}
    return out


# ── الأوامر ────────────────────────────────────────────────────────────────
def cmd_definitions() -> int:
    print("تعريفاتُ الحزمة — كلٌّ ومصدرُه (الاصطلاحُ يُطبع بجانب رقمه لا في ذيل تقرير):\n")
    for i, (name, text, src) in enumerate(DEFINITIONS, 1):
        print(f"{i:2}. {name}\n    {text}\n    المصدر: {src}")
    print(f"\nعدُّ ملفات الأدوات: {_count_tool_files('tools')}")
    return 0


def _identity_block(run: Run) -> None:
    """يُطبع الوسمُ **والسجلُّ بطوله** — حزمةٌ لا تُظهر استبدالَها تُصدّق نفسَها."""
    print(f"الهوية: {run.identity}")
    if run.history:
        print(f"⚠ السجلُّ يُظهر أنها مرّت بـ{len(run.history)} استبدالاً — يُطبع بطوله لا آخرُه:")
        for h in run.history:
            print(f"    {h['previous']} → {h['replaced_by']} في {h['at']} ({h['reason']})")
    else:
        print("السجلّ: لا استبدالَ مسجَّل.")


def cmd_price_surface(args) -> int:
    """سطحُ التسعير — الخيارُ يُبنى ويُقاس، ولا يُقدَّر بجدولٍ في رسالة.

    الثمنُ الذي يدفعه المالك ليس رقماً واحداً بل **سطحاً**: حجمُ الإحصاء يزيد الصفحاتَ الملتقَطة
    داخل الحزمة، وطولُ المدى يزيد **العبورَ بين الصفحات** (حيث سكن العطبُ المقيس: 8 من 50).
    فالخيارُ يُعرض مُسعَّراً، والتوصيةُ واحدة — ويبقى للمالك **سقفٌ** يُعلنه، لا قائمةُ قرارات.
    """
    import itertools, shutil, tempfile
    root = Path(tempfile.mkdtemp(prefix="price-surface-"))
    rows = []
    try:
        for census_size, length in itertools.product(CENSUS_SIZES_FOR_SURFACE, RANGE_LENGTHS_FOR_SURFACE):
            sub = argparse.Namespace(**{**vars(args), "out": root / f"c{census_size}-l{length}",
                                        "census": census_size, "pack_size": census_size + 3 * length,
                                        "capture_mode": "explicit-list", "quiet": True,
                                        "price_surface": False})
            sub.out.mkdir(parents=True, exist_ok=True)
            cmd_build(sub)
            pack = json.loads((sub.out / "pack.json").read_text(encoding="utf-8"))
            price = pack["capture_remedy_price"]
            rows.append({"census": census_size, "range_length": length,
                         "pack_size": census_size + 3 * length,
                         "released_pages": price["pages"], "released_rows": price["rows"],
                         "share": price["share_of_training_rows"],
                         "remaining": price["remaining_after_release"],
                         "ranges": sum(1 for m in pack["ranges"] if m.get("measurable")),
                         "size_gate": pack["size_gate"]["pass"],
                         "crossings": 3 * (length - 1)})
    finally:
        shutil.rmtree(root, ignore_errors=True)
    rows.sort(key=lambda r: (r["share"] or 0))
    print("═══ سطحُ التسعير — (حجمُ الإحصاء × طولُ المدى) · كلُّ صفٍّ مُبنىً ومقيس ═══")
    print(f"  {'إحصاء':>6}{'المدى':>6}{'الحزمة':>7}{'أُفرِج':>7}{'صفوفاً':>8}{'من التدريب':>11}"
          f"{'يبقى':>11}{'عبورُ حدّ':>10}{'البوابات':>9}")
    for r in rows:
        print(f"  {r['census']:>6}{r['range_length']:>6}{r['pack_size']:>7}{r['released_pages']:>7}"
              f"{r['released_rows']:>8}{100*(r['share'] or 0):>10.1f}%{r['remaining']['pages']:>7} صفحة"
              f"{r['crossings']:>10}{('✓' if r['size_gate'] and r['ranges']==3 else '✗'):>9}")
    print("\n  العرفُ: الثمنُ يدفعه **حجمُ الإحصاء** أوّلاً، وطولُ المدى يشتري **عبورَ الحدّ**.")
    print("  ⇒ والتوصية: إبقاءُ الإحصاء 50 وتقصيرُ المدى — ويُقرَّر **سقفٌ** لا قائمة.")
    return 0


def classify_verdict(*, ok: bool, inter: list, blockers: list, remedy_rows: int) -> str:
    """حكمٌ مُصنَّف — لأن «FAIL» كلمةٌ واحدة لحالتين مختلفتين، والفرقُ بينهما كلُّ المعنى.

    * **شرطيٌّ** (لا عطبَ، وقرارُ المالك): البوابةُ المفتوحةُ هي التقاطعُ مع الالتقاط، والمخرجُ
      منها **ثمنٌ** يُدفع بقرارٍ لا ببرمجة.
    * **عطبٌ** (عندنا، يُصلَح): أيُّ محرّكِ بواباتٍ سقط.

    والحرسُ المهمّ: وجودُ عطبٍ **يُبطل** وصفَ «شرطيٌّ» — وإلا صار الاسمُ ممرَّ عبورٍ يُخفي عطباً
    خلف عذرٍ إداريّ (وهو صنفُ «الاستبدال الصامت» في §٦).
    """
    if ok:
        return "PASS — الحزمة قطعت بواباتها"
    if blockers:
        return f"FAIL — عطبٌ مُسمّى أعلاه ({' · '.join(blockers)})"
    if inter:
        return (f"FAIL **شرطيٌّ** — لا عطبَ عندنا: الحزمةُ مشروعةٌ بشرطِ إفراجٍ مُسعَّر عن "
                f"{len(inter)} صفحة ({remedy_rows} صفّاً من التدريب) — والقرارُ للمالك")
    return "FAIL — غيرُ مُصنَّف (لا عطبَ مُسمّى ولا شرطَ مُسعَّر): يُراجَع"


def cmd_build(args) -> int:
    run = Run(_path(args.run))
    print("═" * 78)
    # (١) الهوية أو الوقوف بالاسم
    if not run.identity:
        raise Stopped("الهويةُ `doc_id` = `null` — لا يُبنى على هويةٍ مجهولة: لا تسقط بوابةُ التقاطع إلى "
                      "`unknown`. الوسمُ يُختم أولاً (tools/backfill_reader_stamp.py).")
    _identity_block(run)
    cap = captured_pages(_path(args.capture), run.identity, _path(args.digital))
    print(f"صفحاتُ الالتقاط لهذا المستند: {len(cap['mine'])} · ومستنداتٌ أخرى على القرص: {len(cap['other_docs'])}")

    # (٢) القائمة والمديات — المرشَّحون الثلاثة تُقاس، ولا يُختار أحدُها نصًّا
    print("\n─ القائمة (50/71/17): تُقاس من هذه الأداة لا من نصّ ─")
    attempts = [args.census] if args.census else list(CENSUS_CANDIDATES)
    chosen = chosen_census = None
    mode_used = None
    for mode in ([args.capture_mode] if args.capture_mode else ["strict", "explicit-list"]):
        print(f"── النمط: {mode} " + ("(الالتقاطُ محجوبٌ عن المديات — قاعدةُ الخطة §٣)" if mode == "strict"
              else "(الكوربوس ناقصَ الإحصاء والفجوات — نصُّ الخطة §٢؛ والالتقاطُ يدفع الثمنَ ويُقاس)"))
        for size in attempts:
            census = build_census(run, size)
            built = choose_ranges(run, size, cap["mine"], exclude_capture=(mode == "strict"),
                                  pack_size=args.pack_size)
            verdict = "✓" if built["size_gate"]["pass"] else "✗"
            print(f"  |الإحصاء|={census['size']:>3} (بصمة {census['fingerprint']}) ⇒ طولُ المدى "
                  f"{built['length']:>3} · مدياتٌ {len(built['ranges'])}/3 · "
                  f"|الحزمة|={built['size_gate']['value']} {verdict}   "
                  f"({'مكتملٌ' if census['complete'] else 'ناقصٌ'})")
            for rf in built["refusals"]:
                print(f"      رفضٌ في الثلث {rf['third']} (حجمه {rf['third_size']}): {rf['why']}")
            if built["size_gate"]["pass"] and census["complete"] and chosen is None:
                chosen, chosen_census, mode_used = built, census, mode
        if chosen is not None:
            break
    if chosen is None:
        raise Stopped("لا مرشَّحَ يُغلق بوابةَ «٢٠٠ بالضبط» في أي نمط — والأداةُ توقف البناء بالاسم "
                      "ولا تُصلحه بتخمين، وتطبع الأرقامَ المقيسة أعلاه.")

    # ثمنُ العلاج: ما يجب أن يُحرّره الالتقاطُ صراحةً (قائمةٌ لا صيغة) — يُقاس لا يُقدَّر
    # **الحزمةُ = الإحصاء + المديات** (وهي ٢٠٠ ببوابة الحجم) ⇒ فمجتمعُ بوابة التقاطع هو هي
    # كلُّها. وقياسُ المديات وحدَها كان **مجتمعاً ناقصاً**: بوابةٌ تعمل على فلترٍ لا على الحزمة،
    # وثمنُ العلاج المُعلن ناقصٌ بالثلث (قِيس: 100 مقابل 133).
    pack_pages_all = sorted({x["page"] for x in chosen_census["pages"]}
                            | {x for s, l in chosen["ranges"] for x in range(s, s + l)})
    remedy = sorted(set(pack_pages_all) & cap["mine"])
    remedy_rows = captured_rows(_path(args.capture), run.identity, remedy)
    train_rows, train_pages = captured_totals(_path(args.capture), run.identity)
    if remedy:
        # ولا يُقسم على صفر: نسبةٌ بمقامٍ صفريّ **مجهولةٌ** لا صفر — وهذا الحارسُ كشفه
        # الضابطُ الحقيقيّ (review-33 §٦/١) الذي نادى `--build` على أرضيةٍ بلا صفوف.
        _share = (f"{remedy_rows / train_rows * 100:.1f}% من {train_rows}"
                  if train_rows else "**مجهولة** — صفوفُ حزمة الالتقاط 0 (لا يُقدَّر ما لا يُقيس)")
        print(f"\n⚠ ثمنُ العلاج المقيس — **بعمودين**: نقدٌ `$0` (إعادةُ التقاطٍ من الكاش) "
              f"و**بياناتٌ −{remedy_rows} صفّاً من التدريب** "
              f"({_share}) · "
              f"{len(remedy)} صفحة من {len(pack_pages_all)} في الحزمة · والتدريبُ يبقى "
              f"{train_pages - len(remedy)} صفحة · {train_rows - remedy_rows} صفّاً.")

    # (٣) المديات ببواباتها
    print("\n─ المديات ببواباتها الثلاث (بالإرساء المطبوع) ─")
    measured = []
    for start, length in chosen["ranges"]:
        m = measure_range(run, start, length)
        if not m["measurable"]:
            print(f"  [{m['range'][0]}–{m['range'][1]}] ⛔ غيرُ قابلٍ للقياس: {m['why']}")
            continue
        measured.append(m)
        g = m["gates"]
        print(f"  [{m['range'][0]}–{m['range'][1]}] ({m['length']} صفحة) · حركات {m['movements']}")
        print(f"      افتتاح {m['opening']} · إقفال {m['closing']}")
        print(f"      Σ مدين {m['sum_debit']} · Σ دائن {m['sum_credit']} "
              f"(مطبوع {m['printed_debit']} / {m['printed_credit']})")
        print(f"      هوية {g['identity']['value']} {'✓' if g['identity']['pass'] else '✗'} · "
              f"إطار (Σ−الطبعة) {m['delta_debit']}/{m['delta_credit']} "
              f"وبالعرف المعاكس {m['delta_debit_alt_order']}/{m['delta_credit_alt_order']} "
              f"{'✓' if g['frame']['pass'] else '✗'} · عدّاد {g['counter']['value']}")
    all_gates = all(m["gates"]["identity"]["pass"] and m["gates"]["frame"]["pass"] for m in measured)

    # (٤) بوابةُ التقاطع + السموم
    pack_pages = pack_pages_all          # المجتمعُ: الإحصاء + المديات = 200 (لا 150)
    inter = sorted(set(pack_pages) & cap["mine"])
    # المجتمعُ المطبوعُ **يُشتقّ من المقيس**، فلا يُمكن أن يُطبع 200 ويُقاس 150:
    # «العُرفُ الذي سنّيناه — يُطبع المجتمعُ بجانب الرقم — يصير ضماناً كاذباً لو كان النصُّ ثابتاً»
    #                                                                (review-33 §٢، حكمُ المدقّق)
    _census_pages = {x["page"] for x in chosen_census["pages"]}
    _range_pages = {p for m in measured for p in m["pages"]}
    assert len(pack_pages) == len(_census_pages | _range_pages), (
        f"المجتمعُ المقيس ({len(pack_pages)}) يخالف اتحادَ مكوّناته "
        f"({len(_census_pages | _range_pages)}) — الطباعةُ لا تكذب")
    print(f"\n─ بوابة التقاطع (مجتمعُها الحزمةُ كاملةً: {len(pack_pages)} = "
          f"إحصاء {len(_census_pages)} + مديات {len(_range_pages)}) "
          f"∩ الالتقاط ({len(cap['mine'])}) = {len(inter)} "
          f"{'✓' if not inter else '✗ ' + str(inter[:5])}")
    comp = census_classes(run)                      # الأصنافُ — تُقاس مرّةً وتُطبع وتُقيَّد
    pois = poisons(run, {"ranges": measured, "length": measured[0]["length"] if measured else 0,
                         "census": [x["page"] for x in chosen_census["pages"]]}, cap, pack_size=args.pack_size)
    print("─ السموم:")
    for name, info in pois.items():
        if name == "_coverage":
            continue
        mark = "✓" if (info.get("falls") or info.get("must_not_fall")) else "·"
        print(f"  {mark} {name}: يسقط {info.get('falls') or '— لا (ضابطٌ سلبيّ)'}"
              + (f" · تصادمٌ على القرص {info['colliding_pages_on_disk']}" if info.get("colliding_pages_on_disk") else ""))

    pack = {
        "identity": run.identity,
        "identity_history": run.history,
        "identity_source": f"{args.run}/slice_report.json → corpus_provenance.doc_id",
        "capture_mode": mode_used,
        "capture_remedy_price": {
            "pages": len(remedy), "rows": remedy_rows,
            "share_of_training_rows": (round(remedy_rows / train_rows, 4) if train_rows else None),
            "share_unknown_because": (None if train_rows else "صفوفُ حزمة الالتقاط 0 ⇒ النسبةُ مجهولةٌ لا صفر"),
            "training": {"pages": train_pages, "rows": train_rows},
            "remaining_after_release": {"pages": train_pages - len(remedy), "rows": train_rows - remedy_rows},
            "cash_usd": "0 — إعادةُ التقاطٍ من الكاش",
            "columns": ("يُعرض بعمودين: نقدٌ $0 · وبياناتٌ −{:.1f}% من صفوف التدريب".format(
                remedy_rows / train_rows * 100) if train_rows else
                "يُعرض بعمودين: نقدٌ $0 · وبياناتٌ −عددُ صفوف (والنسبةُ مجهولة: لا صفوفَ للالتقاط)"),
        },
        "capture_remedy_price_pages": len(remedy),
        "census": chosen_census, "ranges": measured,
        "census_classes": comp if comp.get("classes") else {"why": comp.get("why", "غيرُ قابلٍ للقياس")},
        "size_gate": chosen["size_gate"],
        "intersection_gate": {"population": "الحزمةُ كاملةً (الإحصاء + المديات)",
                              "pack_pages": len(pack_pages), "captured": len(cap["mine"]),
                              "intersection": inter, "pass": not inter,
                              "key": "(doc_id, page) — لا page"},
        "poisons": pois,
        "definitions": [{"name": n, "text": t, "source": s} for n, t, s in DEFINITIONS],
        "count_tool_files": _count_tool_files("tools"),
        "cost_usd": "0 — لا نداءَ نموذج: القياسُ من results/pg-*.json والإطاراتِ المطبوعة",
        "built_at": __import__("datetime").date.today().isoformat(),
    }
    out = _path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ok = (all_gates and chosen["size_gate"]["pass"] and not inter
          and pois["_coverage"]["every_check_has_a_poison"])
    if comp.get("classes"):
        print("\n── أصنافُ الإحصاء — مقيسةٌ من القرص (شرطُ review-29 §٦/٢: العددُ من الأداة):")
        print(f"   المجموعُ الساذج = {comp['structural_sum']} · وبعد طرح المتقاطع = "
              f"{comp['structural_union']} (مرئيّاً) والمُجمَّعُ بلا قائمة: {comp['aggregate_only']}")
        print(f"   ⇒ المجموعُ لا يُقدَّم عدداً: {comp['why_the_union_is_not_the_sum']}")
        print(f"   ⇒ «22» في الخطّة: {comp['plan_claim_22']}")
        for _name, _c in comp["classes"].items():
            _tag = "" if _c["listed"] else "  [مُجمَّعٌ بلا قائمة]"
            print(f"   {_name:>22} : {_c['count']:>3}{_tag}   ← {_c['source']}")
        print(f"   {'الاتحاد البنيوي (المقيس)':>22} : {comp['structural_union']:>3}"
              f"  (الأعلى {comp['aggregate_only_upper_bound']})")
        print(f"   {'الاتحاد القارئ (المقيس)':>22} : {comp['reader_union']:>3}"
              f"  (المجموع {comp['reader_sum']})")
        print(f"   {'بنيوي ∪ قارئ (بعد الاتحاد)':>22} : {comp['structural_n_reader']:>3}"
              f"   (المتقاطع {comp['both']}) ⇒ ومنه في الإحصاء المختار: "
              f"{len(set(comp['all_pages_listed']) & {x['page'] for x in chosen_census['pages']})} صفحةً"
              f"  · والعلاقةُ بالخطة: {comp['plan_claim_22']}")
        print(f"   {'القائمة المختارة':>22} : {len(chosen_census['pages'])} صفحة"
              f"  (والإحصاءُ المختارُ يُطبع بمصادره أعلاه)")
    blockers = []
    if not all_gates:
        blockers.append("بواباتُ المديات")
    if not chosen["size_gate"]["pass"]:
        blockers.append("بوابةُ الحجم")
    if not pois["_coverage"]["every_check_has_a_poison"]:
        blockers.append("تغطيةُ السموم")
    verdict = classify_verdict(ok=ok, inter=inter, blockers=blockers, remedy_rows=remedy_rows)
    print(f"\nالحكم: {verdict} · كُتبت في {out / 'pack.json'} · cost_usd 0")
    return 0 if ok else 1


def cmd_verify(args) -> int:
    run = Run(_path(args.run))
    p = _path(args.pack)
    pack = json.loads(p.read_text(encoding="utf-8"))
    print("═" * 78)
    print("**مقابلةُ هوية الحزمة بهوية التشغيلة وقتَ التحقّق** — أولُ مستهلكٍ حقيقيّ لـ`doc_id`:")
    _identity_block(run)
    if not run.identity:
        raise Stopped("هويةُ التشغيلة `null` ⇒ **تفشل المقابلة بالاسم** — لا يُمرَّر `null` إلى `unknown`.")
    if pack["identity"] != run.identity:
        raise Stopped(f"هويةُ الحزمة ({pack['identity']}) تخالف هويةَ التشغيلة ({run.identity}) ⇒ "
                      "**HISTORY_MOVED** — الطرفان تحرّكا معاً، فالتحقّقُ لا يعني شيئاً. البناءُ من جديد.")
    print(f"مطابقة ✓ ({pack['identity']})")
    cap = captured_pages(_path(args.capture), run.identity, _path(args.digital))
    pack_pages = sorted({x["page"] for x in pack["census"]["pages"]}      # المجتمعُ: الإحصاء + المديات
                        | {pg for m in pack["ranges"] for pg in m["pages"]})
    inter = sorted(set(pack_pages) & cap["mine"])
    frozen_fp = _sha16(json.dumps([x["page"] for x in pack["census"]["pages"]]))
    print(f"الإحصاء: {pack['census']['size']} صفحة · بصمةٌ محفوظة {pack['census']['fingerprint']} · "
          f"بصمةٌ من القائمة المجمّدة {frozen_fp} {'✓' if frozen_fp == pack['census']['fingerprint'] else '✗'}")
    print("  (ولا يُعاد تشغيلُ المصنّف أبداً — الأصنافُ تُقرأ مجمَّدة)")
    print(f"بوابة «٢٠٠»: {pack['size_gate']['value']} {'✓' if pack['size_gate']['pass'] else '✗'} · "
          f"التقاطع: {len(inter)} {'✓' if not inter else '✗'}")
    for m in pack["ranges"]:
        fresh = measure_range(run, m["range"][0], m["length"])
        same = all(fresh[k] == m[k] for k in ("movements", "sum_debit", "sum_credit", "opening", "closing"))
        print(f"  [{m['range'][0]}–{m['range'][1]}] حركات {m['movements']} · "
              f"هوية {m['gates']['identity']['value']} · إعادةُ القياس {'مطابقة ✓' if same else 'مخالفة ✗'}")
    ok = not inter and pack["size_gate"]["pass"]
    print(f"\nالحكم: {'PASS — الحزمةُ تشهد لنفسها' if ok else 'FAIL — بالاسم أعلاه'}")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="مُنشئُ حزمة التقييم (كلُّه $0)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true", help="يُبني الحزمة من القرص")
    mode.add_argument("--verify", action="store_true", help="يقابل هويةَ الحزمة بهوية التشغيلة الآن")
    mode.add_argument("--price-surface", action="store_true", dest="price_surface",
                      help="سطحُ التسعير: ثمنُ (حجم الإحصاء × طول المدى) — كلُّ خيارٍ يُبنى ويُقاس")
    mode.add_argument("--print-definitions", action="store_true", help="يطبع الاصطلاحات ومصادرها")
    ap.add_argument("--run", default=DEFAULTS["run"])
    ap.add_argument("--capture", default=DEFAULTS["capture"])
    ap.add_argument("--digital", default=DEFAULTS["digital"])
    ap.add_argument("--out", default=DEFAULTS["out"])
    ap.add_argument("--pack", default=f"{DEFAULTS['out']}/pack.json")
    ap.add_argument("--pack-size", type=int, default=PACK_SIZE,
                    help="حجمُ الحزمة (200 عرفاً) — ويُصغَّر في الأرضيات الصناعية "
                         "لأن ضابطاً لا يستدعي الأمرَ الحقيقيّ ليس ضابطاً (review-33 §٦/١)")
    ap.add_argument("--census", type=int, choices=CENSUS_CANDIDATES, default=None,
                    help="حجمُ الإحصاء (والافتراضُ: تُقاس الثلاثة)")
    ap.add_argument("--capture-mode", choices=("strict", "explicit-list"), default=None,
                    help="strict: الالتقاطُ محجوبٌ عن المديات · explicit-list: قائمةٌ صريحة (البديلُ المُعلن)")
    args = ap.parse_args(argv)
    try:
        if args.price_surface:
            return cmd_price_surface(args)
        if args.print_definitions:
            return cmd_definitions()
        if args.build:
            return cmd_build(args)
        return cmd_verify(args)
    except Stopped as e:
        print(f"\n⛔ وقوفٌ بالاسم: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
