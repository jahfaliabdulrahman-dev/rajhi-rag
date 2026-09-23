#!/usr/bin/env python3
"""**مُشتقُّ إجاباتِ الـ٥٠ سؤالاً** — الحقيقةُ الأرضيةُ تُشتقّ بالأمر، ولا تُكتب في أيّ ملفٍّ مُلتزم.

## القاعدةُ الحاكمة (القاعدة ١٣ · لا رقمَ بيد)

ملفُّ الأسئلة `docs/eval_pack/questions.json` يحمل **نصَّ السؤال ومرساه وقاعدةَ اشتقاقه** — ولا يحمل
مبلغاً ولا اسماً ولا نصَّ كشف. الأرقامُ تُشتقّ هنا عند الطلب من نفس المصدر الذي تشهد له الحزمة
(`page_seal` / `footer` / `results`)، وتُطبع على الشاشة فقط.

## الأوضاع

    python3 tools/eval_questions.py --validate      # المراسي: هل كلُّ صفحةٍ موجودة وكلُّ نمطٍ يقع؟
    python3 tools/eval_questions.py --safe          # ملخّصٌ بلا مبالغ (عدّاتٌ وفهارسُ وأحكام)
    python3 tools/eval_questions.py --truth         # الإجاباتُ كاملةً (مبالغُ المالك، على الشاشة وحدها)

## الاستعمالُ عند التقييم

`--safe` هو ما يُلصق في تقريرٍ أو يُدفع إلى git؛ و`--truth` لا يُحفظ في ملفٍّ متعقَّب **أبداً**.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from tools import pack_io  # noqa: E402

ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩"
PERSIAN = "۰۱۲۳۴۵۶۷۸۹"
LATIN = "0123456789"
_TRANS = str.maketrans(ARABIC_INDIC + PERSIAN, LATIN + LATIN)
_QUESTIONS = pathlib.Path(__file__).resolve().parent.parent / "docs" / "eval_pack" / "questions.json"


def norm_digits(s: str) -> str:
    """توحيدُ الأرقام (عربيةٌ-هندية وفارسية ⇒ لاتينية) — علّةُ القياس لا علاجُ السؤال."""
    return str(s or "").translate(_TRANS)


def num(s) -> float | None:
    """يقرأ مبلغاً مطبوعاً بأيّ صيغةٍ يكتبها الكشف — بلا تخمين.

    الصيغُ المُقاسةُ في الكوربوس ثلاثة، وقراءتُها جميعاً شرطُ صدقٍ (والأمثلةُ أدناه **مواضعٌ لا قيم**):
    فاصلةُ آلافٍ ثمّ نقطةٌ عشريّة · فاصلةٌ **عشريّة** (والمعنى مئة) بأرقامٍ فارسية ·
    فاصلةٌ عشريّةٌ عربية (`٫`). وقاعدةُ الحسم: **آخرُ فاصلٍ من نوعيه هو العشريّ**، وما عداه آلاف.
    """
    t = norm_digits(s).replace("٬", "").replace("٫", ".").strip()   # ٬ آلاف · ٫ عشريّة
    m = re.search(r"-?[\d.,]+", t)
    if not m:
        return None
    tok = m.group(0).rstrip(".,")
    last_dot, last_com = tok.rfind("."), tok.rfind(",")
    if last_dot >= 0 and last_com >= 0:                     # النوعان معاً ⇒ الأخيرُ عشريّ
        dec, thou = (".", ",") if last_dot > last_com else (",", ".")
        tok = tok.replace(thou, "").replace(dec, ".")
    elif last_com >= 0:                                     # فاصلةٌ وحدها
        frac = tok[last_com + 1:]
        tok = tok.replace(",", ".") if len(frac) == 2 else tok.replace(",", "")
    elif last_dot >= 0:
        frac = tok[last_dot + 1:]
        if len(frac) == 3 and tok.count(".") == 1:          # 1.234 ⇒ آلافٌ لا عشريّات
            tok = tok.replace(".", "")
    try:
        return float(tok)
    except ValueError:
        return None


class Corpus:
    """قارئٌ واحدٌ لصفحات التشغيلة — بلا منطقٍ ثانٍ يخالف قارئ الحزمة."""

    def __init__(self, run_dir: pathlib.Path, pages: list[int]):
        self.dir = run_dir
        self.pages = list(pages)
        self._cache: dict[int, dict | None] = {}

    def page(self, p: int) -> dict | None:
        if p not in self._cache:
            f = self.dir / "results" / f"pg-{p:03d}.json"
            self._cache[p] = json.loads(f.read_text()) if f.exists() else None
        return self._cache[p]

    def rows(self, p: int) -> list[dict]:
        d = self.page(p) or {}
        return list(d.get("raw_rows") or [])

    def footer(self, p: int) -> dict:
        return dict((self.page(p) or {}).get("footer") or {})

    def covers(self, p: int) -> bool:
        return p in self.pages and self.page(p) is not None

    def corpus_pages(self) -> int:
        return len(list((self.dir / "results").glob("pg-*.json")))


def truth(q: dict, c: Corpus, pack: dict) -> tuple[object, dict]:
    """يُشتقّ الجوابُ من القرص. يُعيد (الجواب, ملخّصٌ آمنٌ بلا مبالغ)."""
    d = q["derive"]
    k = d["kind"]
    if k == "footer":
        v = num(c.footer(d["page"]).get(d["field"]))
        return v, {"kind": k, "page": d["page"], "field": d["field"], "found": v is not None}
    if k == "count_rows":
        n = len(c.rows(d["page"]))
        return n, {"kind": k, "page": d["page"], "rows": n}
    if k == "last_row_balance":
        rs = c.rows(d["page"])
        return (num(rs[-1].get("balance")) if rs else None), {"kind": k, "page": d["page"], "rows": len(rs)}
    if k == "argmax_row":
        vals = [(i, num(r.get("movement"))) for i, r in enumerate(c.rows(d["page"]))]
        vals = [(i, v) for i, v in vals if v is not None]
        if not vals:
            return None, {"kind": k, "page": d["page"], "rows": 0}
        m = max(v for _, v in vals)
        tops = [i for i, v in vals if v == m]
        return (tops[0] if len(tops) == 1 else {"tie": tops}), {"kind": k, "page": d["page"], "tops": tops}
    if k == "rows_matching":
        hits = [(p, i) for p in c.pages for i, r in enumerate(c.rows(p))
                if d["pattern"] in str(r.get("desc") or "")]
        return hits, {"kind": k, "hits": len(hits), "pages": sorted({p for p, _ in hits})}
    if k == "chain":
        a, b = c.footer(d["a"]), c.footer(d["b"])
        ba, bb = num(a.get("balance")), num(b.get("balance"))
        if ba is None or bb is None:
            return None, {"kind": k, "a": d["a"], "b": d["b"], "found": False}
        net = (num(b.get("credits")) or 0.0) - (num(b.get("debits")) or 0.0)
        ok = abs((bb - ba) - net) < 0.005
        return ok, {"kind": k, "a": d["a"], "b": d["b"], "closes": ok}
    if k == "date_encoding":
        ind = sum(1 for p in c.pages for r in c.rows(p)
                  if re.search(f"[{ARABIC_INDIC}{PERSIAN}]", str(r.get("date") or "")))
        lat = sum(1 for p in c.pages for r in c.rows(p)
                  if re.search(r"\d", str(r.get("date") or ""))
                  and not re.search(f"[{ARABIC_INDIC}{PERSIAN}]", str(r.get("date") or "")))
        return (ind if d["encoding"] == "arabic_ind" else lat), {"kind": k, "encoding": d["encoding"]}
    if k == "pack_meta":
        f = d["field"]
        v = {"pages": len(c.pages), "pack_pages": (pack.get("size_gate") or {}).get("value"),
             "identity": pack.get("identity"), "class_count": len(pack.get("census_classes") or [])}.get(f)
        return v, {"kind": k, "field": f}
    if k == "absent":
        return None, {"kind": k, "reason": d["reason"]}
    return None, {"kind": k, "unknown": True}


def check_abstention(q: dict, c: Corpus, pack: dict) -> tuple[bool, str]:
    """**ادّعاءُ الامتناع يُقاس أيضاً** — لا «لا يوجد» بلا قياس: الصفحةُ خارج الحزمة فعلاً؟ السنةُ غائبةٌ فعلاً؟

    هذا هو الفرقُ بين سؤالٍ عادلٍ وسؤالٍ ظالمه: لو كانت الصفحةُ ٣٠٠ موجودةً لكان جوابُ «لا يوجد» خطأً.
    """
    d = q["derive"]
    r = d["reason"]
    if r == "page_outside_pack":
        return (d["page"] not in c.pages), f"الصفحة {d['page']} {'داخل' if d['page'] in c.pages else 'خارج'} الحزمة"
    if r == "year_absent":
        yrs = set()
        for p in c.pages:
            for row in c.rows(p):
                m = re.findall(r"(?:19|20)\d{2}", norm_digits(row.get("date") or ""))
                yrs.update(m)
        return (str(d["year"]) not in yrs), f"{d['year']} {'موجودة' if str(d['year']) in yrs else 'غائبة'}"
    if r == "field_not_printed":
        hits = 0
        for p in c.pages:
            blob = json.dumps(c.page(p), ensure_ascii=False)
            hits += blob.count(f'"{d["field"]}"')
        return (hits == 0), f"الحقل {d['field']} يظهر {hits} مرّةً"
    if r == "boundary":
        return ((d["page"] + 1) not in c.pages), f"الصفحة {d['page'] + 1} {'داخل' if (d['page'] + 1) in c.pages else 'خارج'} الحزمة"
    return False, f"سببٌ مجهول: {r}"


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="أسئلةُ التقييم: مراسي وإجابات (والحقيقةُ تُشتقّ لا تُكتب)")
    ap.add_argument("--questions", type=pathlib.Path, default=_QUESTIONS)
    ap.add_argument("--validate", action="store_true", help="المراسي فقط: هل كلُّ صفحةٍ موجودة؟")
    ap.add_argument("--safe", action="store_true", help="ملخّصٌ بلا مبالغ")
    ap.add_argument("--truth", action="store_true", help="الإجاباتُ كاملةً (لا تُحفظ)")
    ap.add_argument("--page", type=int, help="سؤالٌ واحدٌ بالرقم التسلسلي (1..50)")
    ap.add_argument("--run", type=pathlib.Path,
                    default=pack_io.data_root() / "data/local_sample/slice_629p",
                    help="مجلّدُ التشغيلة المقروءة (نفسُ مصدر الحزمة)")
    a = ap.parse_args(argv)

    spec = json.loads(a.questions.read_text())
    qs = spec["questions"]
    pack = json.loads(pack_io.pack_path().read_text())
    pages = sorted(int(p) for p in (pack.get("page_seal") or {}).get("pages") or {})
    c = Corpus(a.run, pages)

    print(f"الأسئلة: {len(qs)} · صفحاتُ الحزمة: {len(pages)} · "
          f"صفوفُ الكوربوس المقروءة: {c.corpus_pages()} صفحة")
    bad: list[str] = []
    seen_ids: set[str] = set()
    for q in qs:
        qid = q["id"]
        if qid in seen_ids:
            bad.append(f"{qid}: معرّفٌ مكرّر")
        seen_ids.add(qid)
        for f in ("cat", "metric", "q", "derive", "expect"):
            if f not in q:
                bad.append(f"{qid}: حقلٌ ناقص ({f})")
        if q["derive"].get("kind") == "absent":
            ok_abs, why = check_abstention(q, c, pack)
            if not ok_abs:
                bad.append(f"{qid}: ادّعاءُ امتناعٍ لا يقيسه القرص ({why})")
            continue
        for p in (v for k_, v in q["derive"].items() if k_ in ("page", "a", "b")):
            if not c.covers(p):
                bad.append(f"{qid}: الصفحة {p} خارج الحزمة — مرسًى لا يُقاس")
    if bad:
        print("\n".join(x for x in bad if x), file=sys.stderr)

    if a.validate:
        broken = [x for x in bad if x]
        print("المراسي: %s" % ("كلُّها تقع ✓" if not broken else f"{len(broken)} مرسًى مكسور ✗"))
        return 1 if broken else 0

    rows = []
    for i, q in enumerate(qs, 1):
        if a.page and i != a.page:
            continue
        val, safe = truth(q, c, pack)
        shown = json.dumps(val, ensure_ascii=False) if a.truth else ""
        rows.append((i, q["id"], q["cat"], q["metric"], q["expect"], safe.get("kind"), shown))
    for i, qid, cat, metric, exp, kind, shown in rows:
        print(f"{i:02d} {qid:9s} {cat:8s} {metric:14s} {exp:9s} {kind:14s} {shown}")
    if not a.truth:
        print("\n(بلا مبالغ — والتفصيلُ الكاملُ بـ`--truth` على الشاشة وحدها)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
