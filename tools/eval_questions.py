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

from tools import eval_stamp, pack_io  # noqa: E402

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
        # **قارئٌ واحد**: المحصَّنُ في `pack_io.run_page` — لا منطقٌ ثانٍ يخالف قارئ الحزمة (مراجعة المقاعد).
        # وملفٌّ تالفٌ يُسمّى «غائباً» بدل أن يُفجّر Traceback بلا حكم (وR47 كان في المدى نفسِه).
        if p not in self._cache:
            self._cache[p] = pack_io.run_page(self.dir, p)
        return self._cache[p]

    def rows(self, p: int) -> list[dict]:
        d = self.page(p) or {}
        return list(d.get("raw_rows") or [])

    def footer(self, p: int) -> dict:
        return dict((self.page(p) or {}).get("footer") or {})

    def covers(self, p: int) -> bool:
        return p in self.pages and self.page(p) is not None

    def raw_rows(self, page: int) -> list[dict]:
        """**الصفوفُ المطبوعةُ الخامّة** — لا تُسقِط صفًّا بلا رصيد (وإسقاطُها كان يُخفي صفحةَ ٦٢٩ كلَّها).
        وتقرأ من القارئ الواحد/الكاش نفسه ⇒ لا قراءتان لملفٍّ واحد في تشغيلةٍ واحدة."""
        return list((self.page(page) or {}).get("raw_rows") or [])

    def corpus_pages(self) -> int:
        return len(list((self.dir / "results").glob("pg-*.json")))

    def corpus_page_list(self) -> list[int]:
        """**نطاقُ النظام الحقيقيّ**: كلُّ صفحةٍ في الكشف — لا صفحات الحزمة وحدها.

        وهذا فرقٌ قاتلٌ في التقييم: النظامُ يفهرس الكشفَ كلَّه، فسؤالٌ يقول «في الحزمة» يسأله عمّا لا يعرفه.
        """
        return sorted(int(f.stem.split("-")[1]) for f in (self.dir / "results").glob("pg-*.json"))


def truth(q: dict, c: Corpus, pack: dict) -> tuple[object, dict]:
    """يُشتقّ الجوابُ من القرص. يُعيد (الجواب, ملخّصٌ آمنٌ بلا مبالغ)."""
    d = q["derive"]
    k = d["kind"]
    if k == "footer":
        v = num(c.footer(d["page"]).get(d["field"]))
        return v, {"kind": k, "page": d["page"], "field": d["field"], "found": v is not None}
    if k == "page_sum_all":
        vals = [num(r.get("movement")) for r in c.rows(d["page"])]
        vals = [v for v in vals if v is not None]
        return (sum(vals) if vals else None), {"kind": k, "page": d["page"], "rows": len(vals)}
    if k == "count_rows":
        n = len(c.raw_rows(d["page"]))        # **المطبوعُ الخامّ** (لا المشتقُّ الذي يُسقِط صفوفاً)
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
        # **الحقيقةُ صفٌّ ومبلغٌ وتعادلٌ — لا فهرسٌ يُقارَن بمبلغ** (كان المصحِّحُ معكوساً: صحّحتُ ٢٠٢٦-٠٩-٢٤)
        return ({"amount": m, "tops": tops, "tie": len(tops) > 1},
                {"kind": k, "page": d["page"], "tops": tops})
    if k == "row_chain":
        ra, rb = c.rows(d["a"]), c.rows(d["b"])
        la = num(ra[-1].get("balance")) if ra else None
        fb = num(rb[0].get("balance")) if rb else None
        if la is None or fb is None:
            return None, {"kind": k, "a": d["a"], "b": d["b"], "found": False}
        return ({"equal": abs(la - fb) < 0.005, "diff": round(abs(fb - la), 2)},
                {"kind": k, "a": d["a"], "b": d["b"], "equal": abs(la - fb) < 0.005})
    if k == "rows_matching":
        hits = [(p, i) for p in c.corpus_page_list() for i, r in enumerate(c.rows(p))
                if d["pattern"] in str(r.get("desc") or "")]
        return hits, {"kind": k, "hits": len(hits), "pages": sorted({p for p, _ in hits})}
    if k == "date_encoding":
        ind = sum(1 for p in c.corpus_page_list() for r in c.rows(p)
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
    present = set(c.corpus_page_list())     # **نطاقُ النظام**: الكشفُ كلُّه (٦٢٩) لا حزمةُ تقييمي (٢٠٠)
    if r == "page_outside_pack":
        return (d["page"] not in present), \
            f"الصفحة {d['page']} {'داخل' if d['page'] in present else 'خارج'} نطاقِ النظام ({len(present)} صفحة)"
    if r == "year_absent":
        yrs = set()
        for p in present:
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


def _key_usage() -> dict | None:
    """**الكلفةُ الفعليّة من المزوّد** (لا عدّادُنا): رصيدُ المفتاح قبل وبعد — والفرقُ هو الكلفة.

    المفتاحُ يُقرأ داخل العملية ولا يُطبع أبداً؛ ويُطبع الرقمُ وحده.
    """
    import urllib.request
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
        from statement_qa.api_key import get_api_key
        req = urllib.request.Request("https://openrouter.ai/api/v1/key",
                                     headers={"Authorization": f"Bearer {get_api_key()}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode())["data"]
        return {"usage": d.get("usage"), "limit": d.get("limit"), "limit_remaining": d.get("limit_remaining")}
    except Exception as e:                                   # noqa: BLE001 — قياسٌ لا يُسقط التشغيل
        print(f"  (تعذّر قياسُ الرصيد: {type(e).__name__})", file=sys.stderr)
        return None


_NUMTOK = re.compile(r"[\d٠-٩۰-۹][\d٠-٩۰-۹,٬،٫.]*")
_ABSENCE = ("غير موجود", "لا يوجد", "غير متوف", "لا تتوفر", "لا يمكن", "غير مطبوع", "لا أعلم",
            "لا تتضمّن", "لا تتضمن", "لا بيانات", "خارج", "لا سند")
_AMBIG = ("تعادل", "متساو", "مبلغان", "مبلغين", "أكثر من مبلغ", "لا يمكن الجزم", "لا يمكن تحديد")
_POS = ("يتّصل", "يتصل", "متّصل", "متصل", "يتماشى", "يساوي")
_NEG = ("لا يتّصل", "لا يتصل", "غير متّصل", "غير متصل", "لا يتماشى", "لا يساوي", "ينقطع", "لا يوجد اتصال")


def extract_numbers(text: str) -> list[float]:
    """كلُّ الأرقام في جوابٍ — بأيّ صيغةٍ كتبها النموذج (وهذا ما يُقابَل بالحقيقة)."""
    return [v for v in (num(m.group(0)) for m in _NUMTOK.finditer(text or "")) if v is not None]


_NEG_RE = re.compile(r"(لا\s*(?:يتساو|يتطابق|يتصل|يوجد|يمكن|أستطيع|تُوجد)|غير\s*(?:موجود|متساو|متطابق|متصل)|ليس|مختلف)")


def _is_neg(ans: str) -> bool:
    """**النفيُ بالمعنى لا بالكلمة**: «لا يتساويان» نفيٌ صريح — وقد أسقطها حُكمي مرّةً بسذاجة قائمتي."""
    return bool(_NEG_RE.search(ans)) or any(w in ans for w in _NEG)


def _polarity(ans: str) -> tuple[bool, bool]:
    """(إيجاب، نفي) — **يُزال النفيُ أوّلاً ثم يُبحث عن الإيجاب**: «لا يساوي» **تحتوي** «يساوي»، فأشعلت
    العلمَين معاً فيسقط الشرط `neg and not pos` على جوابٍ صحيح (قِيس بالتنفيذ في مراجعة المقاعد)."""
    t = ans or ""
    stripped = t
    for w in _NEG:
        stripped = stripped.replace(w, " ")
    stripped = _NEG_RE.sub(" ", stripped)
    return any(w in stripped for w in _POS), _is_neg(t)


_AMOUNT_TOK = re.compile(r"\d[\d,٬]*(?:[.٫]\d{1,2})\b")   # مبلغٌ لا رقمُ صفحة: الفاصلةُ العشريّةُ شرط
_ROW_IDX_RE = re.compile(r"(?:الصف|صف|سطر|السطر)[\u064b-\u0652]*\s*(?:رقم[\u064b-\u0652]*\s*)?([0-9٠-٩۰-۹]+)")


def _claimed_row_index(ans: str) -> int | None:
    """رقمُ الصفّ الذي **يسمّيه** الجواب — «مبلغٌ» ليس فهرساً (قِيس أنّ الحُكم كان يمرّر فهرساً خاطئاً)."""
    m = _ROW_IDX_RE.search(ans or "")
    v = num(m.group(1)) if m else None
    return int(v) if v is not None else None


def _claimed_amounts(ans: str) -> list[float]:
    """المبالغُ المُدّعاةُ في الجواب (لا كلُّ رقم) — رقمُ الصفحةِ والعدّ ليسا مبلغاً."""
    out = []
    for tok in _AMOUNT_TOK.findall(ans or ""):
        try:
            out.append(float(tok.replace(",", "").replace("٬", "").replace("٫", ".")))
        except ValueError:
            continue
    return out


def _trace_amounts(res, rows: list[dict]) -> list[float]:
    """**السندُ = الأثر**: مبالغُ الصفوف التي استُشهد بها فعلاً (movement/balance)."""
    out = []
    for n in (getattr(res, "used_row_nos", None) or []):
        if 1 <= n <= len(rows):
            for v in (rows[n - 1].get("movement"), rows[n - 1].get("balance")):
                if v is not None:
                    out.append(float(v))
    return out


_TIE_RE = re.compile(r"(مرّ?تين|مرتين|يتكرّر|يتكرر|مكرّر|مكرر|تعادل|متساو|نفس المبلغ|الصفَّ?ين|كليهما)")


def _declares_tie(ans: str) -> bool:
    """التعادلُ يُعلَن بألفاظٍ لا بقائمةٍ فقيرة: «ويظهر مرتين» إعلانٌ صريح (قِيس: رسب ظلماً)."""
    return bool(_TIE_RE.search(ans))


def score_answer(q: dict, truth_val, ans: str, res, rows: list[dict]) -> tuple[bool, str]:
    """حكمٌ **ميكانيكيّ** لكلّ سؤال — بلا حَكَمٍ ذوقيّ (والحدُّ معلَنٌ في التقرير).

    الأرقامُ تُقابَل بتسامح ٠٫٠٥ (كسرُ هللة)، والامتناعُ يُشترَط فيه **ألّا يخترع مبلغاً**،
    والاستشهادُ يُقابَل بصفحات الصفوف التي استدعتها الأدوات فعلاً (`used_row_nos`).
    """
    nums = extract_numbers(ans)
    m = q["metric"]
    used = list(getattr(res, "used_row_nos", None) or [])
    cited_pages = sorted({rows[n - 1]["page"] for n in used if 1 <= n <= len(rows)})

    if m == "number":
        if q["expect"] == "chain":
            t = truth_val if isinstance(truth_val, dict) else {}
            if not t:
                # **عطبُ مرسًى لا يُقرأ حُكماً على النظام** (قياسُ غيابٍ لا يساوي فشلَ النظام).
                return False, "عطبُ مرسًى: لا سلسلةَ مُشتقّة (لا يُحكم على النظام)"
            pos, neg = _polarity(ans)
            if t.get("equal"):
                near = any(abs(v - 0.0) < 0.05 for v in nums)
                return (pos and not neg and near), f"متساويان: إيجابٌ {'✓' if pos else '✗'} · فرقٌ صفريٌّ {'✓' if near else '✗'}"
            near = any(abs(v - float(t.get("diff"))) < 0.05 for v in nums)
            return (neg and not pos and near), \
                f"غيرُ متساويين: نفيٌ {'صريح' if neg else 'غائب/مضادّ'} · الفرقُ {'مذكور' if near else 'غيرُ مذكور'}"
        if q["expect"] == "boolean":
            pos, neg = _polarity(ans)
            if truth_val is True:
                return (pos and not neg), f"إيجابٌ {'موجود' if pos else 'غائب'}{' ونفيٌ مضادّ' if neg else ''}"
            # السلسلةُ لا تتّصل: الجوابُ الصحيحُ نفيٌ صريح
            return ((neg or (not pos and any(w in ans for w in _ABSENCE)))
                    and len(cited_pages) >= 2), f"نفيٌ {'صريح' if neg else 'غير صريح'} · صفحاتٌ مُستشهدة {len(cited_pages)}"
        if truth_val is None:
            return False, "لا قيمةَ مُشتقّة (عطبُ مرسًى)"
        if isinstance(truth_val, str):
            return (truth_val in ans), f"النصُّ المتوقَّع {'ظهر' if truth_val in ans else 'لم يظهر'}"
        hit = [v for v in nums if abs(v - float(truth_val)) < 0.05]
        return bool(hit), f"المتوقَّع {'وُجد' if hit else 'لم يوجد'} في {len(nums)} رقماً"

    if m == "citation":
        need = q["derive"].get("page")
        if q["derive"]["kind"] == "rows_matching":
            hit_pages = sorted({p for p, _ in truth_val})
            hit = set(cited_pages) & set(hit_pages)
            prec = (len(hit) / len(cited_pages)) if cited_pages else 0.0
            return (bool(hit) and prec >= 0.3), \
                f"أصابت {len(hit)}/{len(hit_pages)} صفحةً صحيحة · دقّةُ الاستشهاد {prec:.0%} ({len(cited_pages)} صفحةً مُستشهدة)"
        if need not in cited_pages:
            return False, f"لم يستشهد بالصفحة {need} (المستشهَد {cited_pages})"
        want = None
        for n in used:
            if 1 <= n <= len(rows) and rows[n - 1]["page"] == need:
                want = n
                break
        if want is None:
            return False, f"استشهد بالصفحة {need} بلا صفٍّ منها"
        t = truth_val if isinstance(truth_val, dict) else {}
        cands = [rows[n - 1]["movement"] for n in used
                 if 1 <= n <= len(rows) and rows[n - 1]["page"] == need and rows[n - 1]["movement"] is not None]
        if not cands:
            return False, f"استشهد بالصفحة {need} بلا صفٍّ منها"
        amt = t.get("amount")
        if amt is None:
            return False, f"لا قمةَ مُشتقّةً للصفحة {need} (صفحةٌ بلا مبالغ)"
        floor = float(amt)
        names = any(abs(float(mv) - floor) < 0.05 for mv in cands)  # **مبلغٌ بمبلغ لا فهرسٌ بمبلغ**
        # **والفهرسُ يُقابَل بالفهرس**: `expect: row_index` يطلب صفّاً بعينه، وقياسُ الأثر وحده لا يقيسه.
        # ويُقبَل الصيغتان — فهرسٌ عامٌّ في `tops` أو ترتيبُ الصفّ داخل صفحته — لأنّ نصَّ السؤال يحتملهما.
        claimed_idx = _claimed_row_index(ans)
        tops_g = {int(x) for x in (t.get("tops") or [])}
        local_top = None
        if 1 <= want <= len(rows):
            page_rows = [r for r in rows if r["page"] == need]
            local_top = next((i for i, r in enumerate(page_rows, 1)
                              if r.get("movement") is not None and abs(float(r["movement"]) - floor) < 0.05), None)
        idx_ok = claimed_idx is not None and (claimed_idx in tops_g or claimed_idx == local_top)
        tie_ok = (not t.get("tie")) or _declares_tie(ans)
        ok = bool(names and tie_ok and idx_ok)
        why = (f"{'ذكر' if names else 'لم يذكر'} قمةَ الصفحة {need} ({len(cands)} صفًّا مُستشهَداً)"
               + ("" if tie_ok else " · **ولم يُعلن التعادل** وهو متعادل")
               + (f" · الفهرسُ {claimed_idx} ✓" if idx_ok
                  else f" · الفهرسُ {'غيرُ مذكور' if claimed_idx is None else f'{claimed_idx} خطأ'} ✗"))
        return ok, why

    if m == "abstain":
        if q["expect"] == "ambiguous":
            ok = any(w in ans for w in _AMBIG)
            return ok, ("أعلن التعادل ✓" if ok else "لم يُعلن التعادل (جزمَ بلا سند)")
        # **الاختراعُ = ادّعاءُ مبلغٍ لا سندَ له في الأثر** — لا كلُّ رقمٍ في الجواب (رقمُ الصفحة ليس مبلغاً).
        # قِيس: العدّادُ القديم حسب ٩ اختراعات، منها جوابٌ ردّ فيه رقمَ الصفحة المسؤول عنها ⇒ تعليمٌ كاذب.
        sup = _trace_amounts(res, rows)
        claimed = [v for v in _claimed_amounts(ans) if abs(v) > 0.005]
        unsupported = [v for v in claimed if not any(abs(v - s) < 0.005 for s in sup)]
        gated = getattr(res, "scope", "in_scope") != "in_scope" or bool(getattr(res, "refused", False))
        declared = any(w in ans for w in _ABSENCE)
        # **عدّادان لا عدّادٌ واحد**: «ادّعى مبلغاً بلا سند» ≠ «لم يُعلن امتناعاً» — وخلطُهما رفع الرقمَ
        # المنشور بواحد (قِيس: ثلاثُ اختراعاتٍ فعليّة + سقوطٌ واحدٌ سببُه عدمُ إعلان التعادل).
        why = ("بوّابةُ النطاق منعته قبل النموذج ✓" if gated
               else f"امتناعٌ نصّيّ بلا مبلغٍ مُخترع ✓ ({len(claimed)} مبلغاً مُدّعى، كلُّه مسنود)"
               if (not unsupported and declared)
               else f"**اختراع**: ادّعى {len(unsupported)} مبلغاً بلا سند في الأثر ✗" if unsupported
               else "**لم يُعلن امتناعاً** نصّيّاً ✗ (ولا ادّعى مبلغاً)")
        return (gated or (not unsupported and declared)), why
    return False, f"مقياسٌ مجهول: {m}"


class _Trace:
    """أثرُ جوابٍ محفوظ — يُعيد بناءَ ما يحتاجه الحُكم بلا نداءِ نموذجٍ ثانٍ."""

    def __init__(self, rec: dict):
        self.used_row_nos = list(rec.get("used_row_nos") or [])
        self.scope = rec.get("scope") or "in_scope"
        self.refused = bool(rec.get("refused"))


def _spec_sha() -> str:
    """بصمةُ ملفّ الأسئلة — تُحفظ مع كلّ جواب ليكون **الربطُ بين النصّ والجواب قابلاً للتدقيق**."""
    import hashlib
    p = pathlib.Path(__file__).resolve().parent.parent / "docs/eval_pack/questions.json"
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    except OSError:
        return "?"


def rescore(a, qs: list[dict], c: Corpus, pack: dict, spec: dict, rows: list[dict]) -> int:
    """**إعادةُ الحكم على أجوبةٍ محفوظة — بلا نداءِ نموذجٍ ولا دفع** (والأثرُ محفوظٌ مع كلّ جواب).

    هذا ما يجعل قواعدَ الحُكم قابلةً للتصحيح بعد التشغيل بلا إعادة صرف، وهو شرطُ عدلٍ: لا يُعاقَب
    النظامُ مرّتين على قاعدةِ حُكمٍ كانت خاطئة.
    """
    out = a.out or (pack_io.data_root() / "data/eval_pack/answers.json")
    data = json.loads(out.read_text())
    by_id = {q["id"]: q for q in qs}
    cur_sha = _spec_sha()
    stale = 0
    results = []
    for rec in data.get("results", []):
        q = by_id.get(rec["id"])
        if q is not None:
            truth_val, _ = truth(q, c, pack)
            ok, why = score_answer(q, truth_val, rec.get("answer", ""), _Trace(rec), rows)
            # **لا يُكتب فوق نصّ السؤال المحفوظ**: الملفُّ شاهدٌ على ما طُلب فعلاً (كان يُستبدل فيُفقد الشاهد)
            rec = {**rec, "ok": ok, "why": why, "metric": q["metric"], "expect": q["expect"],
                   "cat": q["cat"], "kind": q["derive"]["kind"]}
            if not eval_stamp.is_publishable(rec, cur_sha):
                stale += 1
        results.append(rec)
        print(f"{rec['id']:9s} {'✅' if rec.get('ok') else '❌'} {rec.get('why', '')}")
    data["results"] = results
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    if stale:
        print(f"\n⚠️ {stale} سجلاً كُتب **قبل** بصمةِ الأسئلة الحاليّة ({cur_sha}) ⇒ نصُّ السؤال في السجل قد يخالف "
              f"ما طُلب فعلاً. الأصلُ: إعادةُ الطرح. **ولا يُنشر رقمٌ من سجلاتٍ غيرِ مطابقةِ البصمة.**")
    good, why = eval_stamp.publishable_or_why(results, cur_sha)
    if not good and not getattr(a, "allow_stale", False):
        print(f"\n{why}\n   ⇒ **لا تُطبع مقاييسُ من سجلٍّ لا شاهدَ له على السؤال المطروح** — "
              f"للتشخيص وحده: `--allow-stale`.")
        return 3
    if not good:
        print(f"\n{why}\n   ⇒ تُطبع الآن **تشخيصيّاً** ويُمنع نشرُها.")
    _print_metrics(results)
    return 0


def run_questions(a, qs: list[dict], c: Corpus, pack: dict, spec: dict) -> int:
    """تشغيلُ الأسئلة على سلسلة السؤال الحقيقيّة — **مدفوع**، ويُقاس بأمرٍ صريح."""
    src = pathlib.Path(__file__).resolve().parent.parent / "src"
    sys.path.insert(0, str(src))
    from tools.refusal_test import build_rows                     # noqa: PLC0415
    from statement_qa.chunking import chunk_rows                  # noqa: PLC0415
    from statement_qa.qa import answer_question, build_llm        # noqa: PLC0415
    from statement_qa.retriever import build_index                # noqa: PLC0415

    before = _key_usage()
    print(f"[1/4] بناءُ الجدول من {a.run} …", flush=True)
    rows, n_pages = build_rows(a.run)
    print(f"      {n_pages} صفحة | {len(rows)} صفًّا", flush=True)
    print("[2/4] بناءُ الفهرس الدلاليّ (محلّيّ) …", flush=True)
    chunks = chunk_rows([{**r, "row_no": i + 1} for i, r in enumerate(rows)])
    store = build_index(chunks)
    print(f"      {len(chunks)} قطعة", flush=True)
    # ٤) الطرح: كلُّ سؤالٍ في خيطٍ بمهلة — انظر `_ask` (عميلُ النموذج واحدٌ يُبنى هنا)
    llm = build_llm(a.model)
    out = a.out or (pack_io.data_root() / "data/eval_pack/answers.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    prev_all: dict[str, dict] = {}         # كلُّ ما سبق (وإن كان نائباً) — لا يُسقطه الحفظُ التدريجيّ
    if out.exists():                       # **استئنافٌ**: جوابٌ محفوظٌ لا يُعاد سؤالُه (ولا يُدفع ثمنُه مرّتين)
        try:
            prev_all = {r["id"]: r for r in json.loads(out.read_text()).get("results", [])}
        except (OSError, json.JSONDecodeError, KeyError):
            prev_all = {}
    curent = _spec_sha()
    done = {k: v for k, v in prev_all.items()
            # **النائبُ ليس جواباً** ⇒ يُعاد سؤالُه · **وجوابُ نصٍّ آخر ليس جواباً لهذا السؤال** (قِيس:
            # أربعُ إعاداتِ صياغةٍ في مدىً واحد ⇒ كان يُعاد استخدامُ جوابِ النصّ القديم صامتاً).
            if not str(v.get("answer") or "").startswith("<") and eval_stamp.is_publishable(v, curent)}
    todo = [q for q in qs if q["id"] not in done]
    if a.budget:                       # **سقفٌ يُعلن ويُقاس**: بمعدّلٍ مُقنَّعٍ من نقطتين مقيسَتين (٠٫٠٠٦–٠٫٠١٠ للسؤال)
        cap = max(0, int(float(a.budget) / 0.01))
        if len(todo) > cap:
            print(f"⛔ السقفُ أوقف الجدولة: {len(todo)} سؤالاً > {cap} (بمعدّل $0.01/سؤال المُقنَّع) ⇒ "
                  f"التغطيةُ المُعلَنة: {cap} من {len(qs)}", flush=True)
            todo = todo[:cap]
    if getattr(a, "only", None):           # إعادةُ أسئلةٍ بعينها (بعد تصحيح نطاقِها أو صياغتِها)
        want = {x.strip() for x in a.only.split(",") if x.strip()}
        todo = [q for q in qs if q["id"] in want]
        done = {k: v for k, v in done.items() if k not in want}
    print(f"[3/4] طرحُ الأسئلة ({len(todo)} من {len(qs)} · ومحفوظٌ سابقاً {len(done)}) "
          f"على {a.model or 'الافتراضيّ'} …\n", flush=True)

    order = [q["id"] for q in qs]
    import threading

    def _ask(qtext: str, out_box: dict) -> None:
        """سؤالٌ واحدٌ في خيط: تعليقُه لا يُسقط الجولةَ (ولا يُقتل الخيط — يُترك معلّقاً ويُسجَّل فشلُه)."""
        try:
            r = answer_question(store, qtext, rows=rows, chunks=chunks, llm=llm)
            out_box.update({"answer": r.answer or "", "used": list(getattr(r, "used_row_nos", None) or []),
                            "scope": getattr(r, "scope", None), "refused": bool(getattr(r, "refused", False))})
        except Exception as e:                                   # noqa: BLE001 — عطبٌ يُسمّى لا يُسقط الجولة
            out_box["error"] = f"{type(e).__name__}: {e}"

    for i, q in enumerate(todo, 1):
        import time
        t0 = time.monotonic()
        truth_val, _ = truth(q, c, pack)
        box: dict = {}
        t = threading.Thread(target=_ask, args=(q["q"], box), daemon=True)
        t.start()
        t.join(int(getattr(a, "timeout", 0) or 150))
        msg = {"error": "انتهت المهلة"} if t.is_alive() else (box or {"error": "لا جواب"})
        res = _Trace({"used_row_nos": msg.get("used"), "scope": msg.get("scope"),
                      "refused": msg.get("refused")}) if "answer" in msg else None
        ans = msg["answer"].strip() if res else f"<{msg.get('error')}>"
        ok, why = (score_answer(q, truth_val, ans, res, rows) if res
                   else (False, f"عطبٌ/مهلة: {msg.get('error')}"))
        done[q["id"]] = {"id": q["id"], "cat": q["cat"], "metric": q["metric"], "expect": q["expect"],
                         "kind": q["derive"]["kind"],
                         "q": q["q"], "answer": ans, "ok": ok, "why": why,
                         "cited_pages": sorted({rows[n - 1]["page"] for n in (getattr(res, "used_row_nos", None) or [])
                                                if 1 <= n <= len(rows)}) if res else [],
                         "used_row_nos": (list(getattr(res, "used_row_nos", None) or [])[:40] if res else []),
                         "scope": getattr(res, "scope", None) if res else None,
                         "refused": bool(getattr(res, "refused", False)) if res else None,
                         "spec_sha": _spec_sha(),   # **شاهدُ الربط**: أيُّ نصِّ سؤالٍ أُجيب عنه
                         "secs": round(time.monotonic() - t0, 1)}   # **المتزنُ في الدليل**: كم أخذ السؤال
        merged = {**prev_all, **done}      # النائبُ يبقى ما لم يُجَب عنه فعلاً
        out.write_text(json.dumps({"model": a.model or "افتراضيّ", "spec_sha": _spec_sha(),
                                   "budget_usd": a.budget,     # **العقدةُ في الدليل**: ميزانيةُ الجولة مُعلنةٌ في ملفّها
                                   "results": [merged[k] for k in order if k in merged]},
                                  ensure_ascii=False, indent=1))   # **حفظٌ تدريجيّ: قتلُ العملية لا يُهدر جواباً**
        print(f"{i:02d} {q['id']:9s} {'✅' if ok else '❌'} {why}", flush=True)

    after = _key_usage()
    results = [done[k] for k in order if k in done]
    print(f"\n[4/4] الأجوبةُ كاملةً في {out} (خارج git: `data/` · حفظٌ تدريجيّ بعد كلّ سؤال)")

    print("\n" + "=" * 62)
    _print_metrics(results)
    if before and after and before.get("usage") is not None:
        d = float(after["usage"]) - float(before["usage"])
        print(f"💰 الكلفةُ الفعليّةُ من المزوّد: ${d:.4f} (رصيدُ المفتاح {before.get('usage')} ⇒ {after.get('usage')})")
    else:
        print("💰 تعذّر قياسُ الكلفة من المزوّد — لا يُدَّعى رقمٌ بلا مصدر.")
    return 0 if all(r["ok"] for r in results) else 1


def _print_metrics(results: list[dict]) -> None:
    """المقاييسُ الثلاثة + تفصيلٌ بالقاعدة (يُظهر **أين** العطب لا كمّه فقط)."""
    for m, label in (("number", "دقّة الرقم"), ("citation", "صدق الاستشهاد من الأثر"), ("abstain", "صحّة الامتناع")):
        sel = [r for r in results if r.get("metric") == m]
        n_ok = sum(1 for r in sel if r.get("ok"))
        print(f"{label:26s} {n_ok:2d}/{len(sel):2d}  {'█' * n_ok}{'·' * (len(sel) - n_ok)}")
    print(f"{'المجموع':26s} {sum(1 for r in results if r.get('ok')):2d}/{len(results):2d}")
    n_abs = sum(1 for r in results if r.get("metric") == "abstain")
    fell = [r for r in results if r.get("metric") == "abstain" and not r.get("ok")]
    invented = sum(1 for r in fell if "**اختراع**" in (r.get("why") or ""))
    silent = sum(1 for r in fell if "لم يُعلن" in (r.get("why") or ""))
    # المقامُ يُشتقّ لا يُكتب بيد — **والصنفان يُفصَلان** (وإلّا قرأ القارئُ صنفاً وقيس غيرُه)
    print(f"\n⛔ الامتناعاتُ الساقطة: {len(fell)}/{n_abs} — منها **اختراعُ مبلغٍ بلا سند {invented}** "
          f"· **عدمُ إعلان الامتناع {silent}**")
    by_kind: dict[str, list[bool]] = {}
    for r in results:
        by_kind.setdefault(r.get("kind") or "?", []).append(bool(r.get("ok")))
    print("\nتفصيلٌ بالقاعدة:")
    for k, oks in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        print(f"  {k:16s} {sum(oks):2d}/{len(oks):2d}")


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="أسئلةُ التقييم: مراسي وإجابات (والحقيقةُ تُشتقّ لا تُكتب)")
    ap.add_argument("--questions", type=pathlib.Path, default=_QUESTIONS)
    ap.add_argument("--validate", action="store_true", help="المراسي فقط: هل كلُّ صفحةٍ موجودة؟")
    ap.add_argument("--safe", action="store_true", help="ملخّصٌ بلا مبالغ")
    ap.add_argument("--truth", action="store_true", help="الإجاباتُ كاملةً (لا تُحفظ)")
    ap.add_argument("--page", type=int, help="سؤالٌ واحدٌ بالرقم التسلسلي (1..50)")
    ap.add_argument("--execute", action="store_true",
                    help="**تشغيلُ الأسئلة على سلسلة السؤال (مدفوع)** — يطرحها ويطبع المقاييس الثلاثة")
    ap.add_argument("--limit", type=int, help="أوّلُ N سؤالاً (للقياس قبل الصرف)")
    ap.add_argument("--model", help="اسمُ النموذج على OpenRouter (وإلّا فالافتراضيّ في `build_llm`)")
    ap.add_argument("--out", type=pathlib.Path, help="ملفُّ الأجوبة (افتراضيّه `data/eval_pack/answers.json`)")
    ap.add_argument("--budget", type=float, help="سقفُ الصرف بالدولار — يُوقف الجدولةَ ويُعلن التغطية")
    ap.add_argument("--force", action="store_true", help="تجاوزُ حاجبِ المراسي (يُعلن في الخرج أنّه تجاوز)")
    ap.add_argument("--allow-stale", action="store_true",
                    help="طبعُ مقاييسَ من سجلاتٍ لا تطابق بصمةَ الأسئلة — **تشخيصٌ فقط، لا للنشر**")
    ap.add_argument("--only", help="إعادةُ سؤالِ معرّفاتٍ بعينها (مفصولةً بفاصلة) رغم الحفظ التدريجيّ")
    ap.add_argument("--timeout", type=int, default=150,
                    help="مهلةُ كلّ سؤالٍ بالثواني (بلا مهلةٍ يعلَق التشغيلُ أبدًا — قِيس)")
    ap.add_argument("--rescore", action="store_true",
                    help="**إعادةُ الحكم على أجوبةٍ محفوظة** بالقواعد الحاليّة — بلا نداءِ نموذجٍ ولا دفع")
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
        present = set(c.corpus_page_list())   # **نطاقُ النظام**: الكشفُ كلُّه (٦٢٩) — المرسى يُقاس عليه لا على حزمة تقييمي
        for p in (v for k_, v in q["derive"].items() if k_ in ("page", "a", "b")):
            if p not in present:
                bad.append(f"{qid}: الصفحة {p} خارج نطاقِ النظام ({len(present)} صفحة) — مرسًى لا يُقاس")
    if bad:
        print("\n".join(x for x in bad if x), file=sys.stderr)

    if a.rescore:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
        from tools.refusal_test import build_rows                     # noqa: PLC0415
        rows, _ = build_rows(a.run)
        return rescore(a, qs, c, pack, spec, rows)

    if bad and (a.execute or a.rescore) and not a.force:
        # **حاجبٌ في المسار المدفوع لا في المجّانيّ وحده**: جولةٌ تُصرف فوق مراسٍ لا تُقاس هي بالضبط ما
        # أنتج الأرقامَ المسحوبة (صفحتان «غائبتان» وهما موجودتان · «سنةٌ غائبة» فيها ٨٦٢ صفًّا).
        print(f"⛔ {len(bad)} عطباً في المراسي ⇒ لا طرحَ مدفوعاً ولا إعادةَ حكمٍ فوق ما لا يُقاس "
              f"(تجاوزٌ صريح: --force). القائمةُ مطبوعةٌ أعلاه.", file=sys.stderr)
        return 2
    if a.execute:
        sel = qs[: a.limit] if a.limit else qs
        return run_questions(a, sel, c, pack, spec)

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
