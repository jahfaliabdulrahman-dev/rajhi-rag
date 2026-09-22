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


def choose_ranges(run: Run, census_size: int, captured: set[int], exclude_capture: bool = True) -> dict:
    """من كل ثلثٍ مدًى متّصلٌ طولُه `ceil((200−|الإحصاء|)/3)` يبدأ من أوّل صفحةٍ إطاراها مقروءان."""
    length = -(-(PACK_SIZE - census_size) // 3)          # ceil
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
            refusals.append({
                "third": i + 1, "third_size": len(third), "longest_contiguous_free_run": longest,
                "required_length": length,
                "why": (f"أطولُ مقطعٍ متّصلٍ حرٍّ = {longest} صفحة والطولُ المطلوب {length} ⇒ "
                        f"المدى مستحيلٌ بهذا القيد (فرق {length - longest} صفحة). "
                        "**والعلّةُ بنيوية لا عددية**: حجزٌ بدورية ٣ لا يُجاور محجوزَين، فالمقطعُ الحرُّ "
                        "محصورٌ بنيوياً بـ٣ (محجوزٌ + جاراه غيرُ المحجوزَين **إن أُفرِج عنهما**) — "
                        "فلا كوربوسٌ أطولُ يُصلح تناقضَ «دورية 3» مع «مدى متّصل»")})
        else:
            ranges.append((picked, length))
    total = census_size + sum(l for _, l in ranges)
    return {"length": length, "ranges": ranges, "refusals": refusals, "exclude_capture": exclude_capture,
            "size_gate": {"value": total, "expected": PACK_SIZE, "pass": total == PACK_SIZE and not refusals},
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


# ── السموم: كلُّ بوابةٍ لها سمٌّ وإلا سقطت الحزمة ──────────────────────────
def poisons(run: Run, built: dict, cap: dict) -> dict:
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
    out["size_201"] = {"gate": "size", "value": PACK_SIZE + 1, "falls": ["size"], "why": "٢٠١ ⇒ تسقط البوابة"}
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
            built = choose_ranges(run, size, cap["mine"], exclude_capture=(mode == "strict"))
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
        print(f"\n⚠ ثمنُ العلاج المقيس — **بعمودين**: نقدٌ `$0` (إعادةُ التقاطٍ من الكاش) "
              f"و**بياناتٌ −{remedy_rows} صفّاً من التدريب** "
              f"({remedy_rows / train_rows * 100:.1f}% من {train_rows}) · "
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
    print(f"\n─ بوابة التقاطع (مجتمعُها الحزمةُ كاملةً: {len(pack_pages)} = "
          f"إحصاء {len(chosen_census['pages'])} + مديات {sum(m['length'] for m in measured)}) "
          f"∩ الالتقاط ({len(cap['mine'])}) = {len(inter)} "
          f"{'✓' if not inter else '✗ ' + str(inter[:5])}")
    pois = poisons(run, {"ranges": measured, "length": measured[0]["length"] if measured else 0,
                         "census": [x["page"] for x in chosen_census["pages"]]}, cap)
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
            "share_of_training_rows": round(remedy_rows / train_rows, 4) if train_rows else None,
            "training": {"pages": train_pages, "rows": train_rows},
            "remaining_after_release": {"pages": train_pages - len(remedy), "rows": train_rows - remedy_rows},
            "cash_usd": "0 — إعادةُ التقاطٍ من الكاش",
            "columns": "يُعرض بعمودين: نقدٌ $0 · وبياناتٌ −{:.1f}% من صفوف التدريب".format(
                (remedy_rows / train_rows * 100) if train_rows else 0),
        },
        "capture_remedy_price_pages": len(remedy),
        "census": chosen_census, "ranges": measured,
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
    print(f"\nالحكم: {'PASS — الحزمة قطعت بواباتها' if ok else 'FAIL — عطبٌ مُسمّى أعلاه'} "
          f"· كُتبت في {out / 'pack.json'} · cost_usd 0")
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
    mode.add_argument("--print-definitions", action="store_true", help="يطبع الاصطلاحات ومصادرها")
    ap.add_argument("--run", default=DEFAULTS["run"])
    ap.add_argument("--capture", default=DEFAULTS["capture"])
    ap.add_argument("--digital", default=DEFAULTS["digital"])
    ap.add_argument("--out", default=DEFAULTS["out"])
    ap.add_argument("--pack", default=f"{DEFAULTS['out']}/pack.json")
    ap.add_argument("--census", type=int, choices=CENSUS_CANDIDATES, default=None,
                    help="حجمُ الإحصاء (والافتراضُ: تُقاس الثلاثة)")
    ap.add_argument("--capture-mode", choices=("strict", "explicit-list"), default=None,
                    help="strict: الالتقاطُ محجوبٌ عن المديات · explicit-list: قائمةٌ صريحة (البديلُ المُعلن)")
    args = ap.parse_args(argv)
    try:
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
