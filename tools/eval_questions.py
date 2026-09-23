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
            pos, neg = any(w in ans for w in _POS), _is_neg(ans)
            if t.get("equal"):
                near = any(abs(v - 0.0) < 0.05 for v in nums)
                return (pos and not neg and near), f"متساويان: إيجابٌ {'✓' if pos else '✗'} · فرقٌ صفريٌّ {'✓' if near else '✗'}"
            near = any(abs(v - float(t.get("diff") or -1)) < 0.05 for v in nums)
            return (neg and not pos and near), \
                f"غيرُ متساويين: نفيٌ {'صريح' if neg else 'غائب/مضادّ'} · الفرقُ {'مذكور' if near else 'غيرُ مذكور'}"
        if q["expect"] == "boolean":
            pos, neg = any(w in ans for w in _POS), _is_neg(ans)
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
        if isinstance(truth_val, dict):                      # تعادلٌ ⇒ لا يجوز الجزم
            return False, "الصفحةُ صحيحةٌ لكن الحقيقةَ تعادلٌ لا جزم"
        want = None
        for n in used:
            if 1 <= n <= len(rows) and rows[n - 1]["page"] == need:
                want = n
                break
        if want is None:
            return False, f"استشهد بالصفحة {need} بلا صفٍّ منها"
        cands = [rows[n - 1]["movement"] for n in used
                 if 1 <= n <= len(rows) and rows[n - 1]["page"] == need and rows[n - 1]["movement"] is not None]
        ok = any(abs(float(mv) - float(truth_val)) < 0.05 for mv in cands)   # أيُّ صفٍّ مُستشهَدٍ يطابق القمة
        return ok, f"{'أشار إلى' if ok else 'لم يُشر إلى'} صفِّ القمة في الصفحة {need} ({len(cands)} صفًّا مُستشهَداً)"

    if m == "abstain":
        if q["expect"] == "ambiguous":
            ok = any(w in ans for w in _AMBIG)
            return ok, ("أعلن التعادل ✓" if ok else "لم يُعلن التعادل (جزمَ بلا سند)")
        invented = [v for v in nums if abs(v) > 0.005]
        gated = getattr(res, "scope", "in_scope") != "in_scope" or bool(getattr(res, "refused", False))
        why = ("بوّابةُ النطاق منعته قبل النموذج ✓" if gated
               else "امتناعٌ نصّيّ بلا مبلغٍ مُخترع ✓" if (not invented and any(w in ans for w in _ABSENCE))
               else f"أجاب بـ{len(invented)} رقماً لا سند لها ✗")
        return (gated or (not invented and any(w in ans for w in _ABSENCE))), why
    return False, f"مقياسٌ مجهول: {m}"


class _Trace:
    """أثرُ جوابٍ محفوظ — يُعيد بناءَ ما يحتاجه الحُكم بلا نداءِ نموذجٍ ثانٍ."""

    def __init__(self, rec: dict):
        self.used_row_nos = list(rec.get("used_row_nos") or [])
        self.scope = rec.get("scope") or "in_scope"
        self.refused = bool(rec.get("refused"))


def rescore(a, qs: list[dict], c: Corpus, pack: dict, spec: dict, rows: list[dict]) -> int:
    """**إعادةُ الحكم على أجوبةٍ محفوظة — بلا نداءِ نموذجٍ ولا دفع** (والأثرُ محفوظٌ مع كلّ جواب).

    هذا ما يجعل قواعدَ الحُكم قابلةً للتصحيح بعد التشغيل بلا إعادة صرف، وهو شرطُ عدلٍ: لا يُعاقَب
    النظامُ مرّتين على قاعدةِ حُكمٍ كانت خاطئة.
    """
    out = a.out or (pack_io.data_root() / "data/eval_pack/answers.json")
    data = json.loads(out.read_text())
    by_id = {q["id"]: q for q in qs}
    results = []
    for rec in data.get("results", []):
        q = by_id.get(rec["id"])
        if q is not None:
            truth_val, _ = truth(q, c, pack)
            ok, why = score_answer(q, truth_val, rec.get("answer", ""), _Trace(rec), rows)
            rec = {**rec, "ok": ok, "why": why}
        results.append(rec)
        print(f"{rec['id']:9s} {'✅' if rec.get('ok') else '❌'} {rec.get('why', '')}")
    data["results"] = results
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
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
    done = {k: v for k, v in prev_all.items()
            if not str(v.get("answer") or "").startswith("<")}   # **النائبُ ليس جواباً** ⇒ يُعاد سؤالُه
    todo = [q for q in qs if q["id"] not in done]
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
                         "refused": bool(getattr(res, "refused", False)) if res else None}
        merged = {**prev_all, **done}      # النائبُ يبقى ما لم يُجَب عنه فعلاً
        out.write_text(json.dumps({"model": a.model or "افتراضيّ",
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
    invented = sum(1 for r in results if r.get("metric") == "abstain" and not r.get("ok"))
    print(f"\n⛔ الامتناعاتُ الساقطة (خطرُ الاختراع): {invented}/8")
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
        for p in (v for k_, v in q["derive"].items() if k_ in ("page", "a", "b")):
            if not c.covers(p):
                bad.append(f"{qid}: الصفحة {p} خارج الحزمة — مرسًى لا يُقاس")
    if bad:
        print("\n".join(x for x in bad if x), file=sys.stderr)

    if a.rescore:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
        from tools.refusal_test import build_rows                     # noqa: PLC0415
        rows, _ = build_rows(a.run)
        return rescore(a, qs, c, pack, spec, rows)

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
