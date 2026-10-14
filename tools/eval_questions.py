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
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from tools import eval_stamp, pack_io  # noqa: E402
from tools.spend import at_or_over, would_exceed  # noqa: E402

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
        #: **تخزينٌ داخلَ التشغيلة — ومُبطِلُه مُعلَن (§٣٠ «لا حالةَ مخزَّنةً صامتة»):**
        #: العمرُ = عمرُ هذه النسخة؛ وملفّاتُ التشغيلة **لا تتغيّر داخلها** (الكاشُ يُكتب قبل القياس)؛
        #: ومن أراد إعادةَ القراءة يبني `Corpus` جديدةً — ولا يُستعمل هذا المخزّنُ **بين تشغيلتين أبدًا**
        #: (لا يُحفظ على القرص ولا ثابتٌ عالميّ). أُعلن هذا استجابةً لمقعد البنية (مراجعة إغلاق ٦٤):
        #: قاعدةُ §٣٠ كانت أوسعَ من مُحصِّها، فالمخزَّنُ الآخرُ القائمُ يُصرّح بنطاقه ومُبطِلِه هنا.
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


def _page_row_ids(rows: list[dict], page: int) -> list[int]:
    """صفوفُ الصفحة **بترقيم النظام** (`i+1`) — موضعُ الإثبات لكلّ ما يُشتقّ من صفوف الصفحة."""
    return [i + 1 for i, r in enumerate(rows) if r.get("page") == page]


def _match_row_ids(rows: list[dict], hits, c: "Corpus", pattern: str) -> tuple[list[int], list[dict]]:
    """معرّفاتُ **الصفوف المطابِقة** بترقيم النظام + **المطابقاتُ غيرُ القابلة للتموضع مُعلَنة**.

    التحويلُ من الفهرس المحلّيّ داخل الصفحة إلى موضعِه في السلسلة لا يُترجَم بالتخمين: كلُّ معرّفٍ
    يُشترط أن يكون موضعَه المحلّيّ قائمًا في صفوف السلسلة لنفس الصفحة.

    **ولا يضيع ضمُّ صفٍّ صامتًا** (قِيس: `cit-01` أربعُ مطابقات إحداها على الصفحة ٦٢٩ — صفُّ مجموعٍ بلا
    رصيدٍ مطبوع ⇒ يسقطه `build_rows` ⇒ لا موضعَ له في عالم الصفوف الذي يستشهد به النموذج): كلُّ مطابقةٍ
    لا مقابلَ لها تخرج في `unmapped` ببابها وسببها، وضابطٌ يقيس أنّ (المُوضَّع + المُعلَن) = المطابقات.
    """
    want: dict[int, list[int]] = {}
    for p, i in hits:
        want.setdefault(p, []).append(i)
    ids: list[int] = []
    unmapped: list[dict] = []
    for p, idxs in sorted(want.items()):
        chain = _page_row_ids(rows, p)             # صفوفُ الصفحة بترقيم النظام، بترتيب السلسلة
        src = c.raw_rows(p)                        # الصفوفُ المطبوعة كما قُرئت (نفسُ ما طُوبق عليه)
        for i in sorted(set(idxs)):
            if i < len(chain):
                # **تحقّقُ هويّةٍ لا موضع**: الصفُّ المُعيَّن يجب أن يحمل النصَّ الذي طُوبق عليه الأصل.
                # (شرطُ المدى وحده كان يفترض أنّ الترتيبَ لم يتحرّك؛ وإسقاطُ صفٍّ من وسط الصفحة
                #  يُزيح ما بعده ⇒ استشهادٌ بصفٍّ آخر يبدو كاملًا — مراجعة ٥٢ · مقعدا المعايير والبنية.)
                got = str((rows[chain[i] - 1] or {}).get("desc") or "")
                if pattern and pattern not in got:
                    unmapped.append({"page": p, "index": i,
                                     "why": "إزاحةٌ موضعيّة: صفُّ السلسلة عند هذا الموضع لا يحمل النصّ المطابِق"})
                    continue
                ids.append(chain[i])
                continue
            why = ("الصفُّ المطابِق بلا رصيدٍ مطبوع ⇒ يخرج من السلسلة (build_rows يُسقط رصيدَه None)"
                   if i < len(src) and num(src[i].get("balance")) is None
                   else "المطابقةُ عند فهرسٍ لا صفَّ له في السلسلة (فهرسُ الصفحة أطولُ من صفوفها في السلسلة)")
            unmapped.append({"page": p, "index": i, "why": why})
    return sorted(set(ids)), unmapped


def _absent_pages(c: Corpus, d: dict) -> list[int]:
    """موضعُ إثبات الامتناع = **مجموعةُ الفحص نفسها** لا رمزٌ عنها.

    كان يعيد `[page, page + 1]` لصفحةٍ مطلوبةٍ خارج الكشف (٧٠٠ ⇒ `[700, 701]`) — صفحتان **لا وجودَ
    لهما** ⇒ موضعٌ لا يُكذَّب ولا يُصدَّق، ويمرّ لأنّ `check_proof` لا يشترط إلا «غيرَ فارغ».
    الآن: الحدُّ **الموجودُ** في الكشف للسؤال عن صفحةٍ خارجه، والصفحاتُ الممسوحةُ فعلًا لِما يُقاس على المسح.
    """
    r = d.get("reason")
    scope = c.corpus_page_list()
    if r == "boundary":
        # **الشاهدُ يُطابق الدعوى**: `check_abstention` يقيس `page + 1` ⇒ الموضعُ يشير إلى الصفحة نفسها
        # التي تُقاس (كان يشير إلى `page` ⇒ موضعٌ بجوار الدعوى لا عليها — مقعدُ البنية).
        nxt = int(d.get("page") or 0) + 1
        return [nxt] if nxt in set(scope) else ([max(scope)] if scope else [])
    if r == "page_outside_pack":
        return [max(scope)] if scope else []      # آخرُ صفحةٍ موجودة = الحدُّ الذي يُقاس به الغياب
    if r in ("year_absent", "field_not_printed"):
        return scope                              # الشاهدُ = ما مُسح، لا حزمةُ تقييمي (٢٠٠)
    return []


PROOF_RULE = {                    # **موضعُ الإثبات المُلزِم لكلّ نوع** — «سؤالٌ بلا صفوفٍ ⇒ يسقط»
    "footer": "pages", "page_sum_all": "rows", "count_rows": "rows", "last_row_balance": "rows",
    "argmax_row": "rows", "row_chain": "rows", "rows_matching": "rows", "date_encoding": "pages",
    "absent": "pages", "pack_meta": "source",
}


PROOF_EXCEPTIONS = {
    # **استثناءٌ مُعلَنٌ ومؤرَّخ — لا صمت**: صفوفُ الصفحة ٦٢٩ يسقطها `build_rows` (لا رصيدَ مطبوعاً فيها)،
    # وحقيقةُ `abs-02` تُشتقّ من `raw_rows` ⇒ لا موضعَ إثباتٍ لها في عالم الصفوف الذي يقرؤه النموذج.
    # وإعادةُ صياغتها **تُغيّر بصمةَ الحزمة** ⇒ تُسقط شهادةَ الـ٢٠٠ سجل ⇒ **قرارُ المالك** (أُعلن ٢٠٢٦-٠٩-٢٤).
    "abs-02": "الصفحة ٦٢٩: صفوفٌ بلا رصيد ⇒ لا موضعَ إثباتٍ في عالم الصفوف؛ وإعادةُ الصياغة تُسقط بصمةَ الـ٢٠٠",
}


def proof_exception(qid: str) -> str | None:
    """استثناءٌ مُعلَنٌ **بمعناه** لا كتمًا. ويُمنع استثناءٌ متقادمٌ بضابط (انظر `classify_proof`)."""
    return PROOF_EXCEPTIONS.get(qid)


def classify_proof(q: dict, safe: dict, c: "Corpus", rows: list[dict]) -> tuple[str, str]:
    """منطقٌ **واحد** يستهلكه `--validate` و`--truth` والضوابط: `ok` | `exception` | `missing`.

    و**الاستثناءُ المتقادم يُكشف**: سؤالٌ صار له إثباتٌ وهو في قائمة الاستثناءات ⇒ يُعلَن ليُزال
    (وإلا صارت القائمةُ غطاءً دائمًا — وهي علّةٌ من صنف «ضابطٌ لا يميّز الفرضيّتين»).
    """
    why = check_proof(q, safe, c=c, rows=rows)
    exc = proof_exception((q or {}).get("id"))
    if not why:
        return ("ok", f"⚠ استثناءٌ متقادم: {q.get('id')} صار له موضعُ إثبات ⇒ يُزال من القائمة") if exc else ("ok", "")
    return ("missing", why) if not exc else ("exception", exc)


def check_proof(q: dict, safe: dict, c: "Corpus", rows: list[dict]) -> str | None:
    """**لا سؤالَ بلا موضعِ إثبات** (الخارطة · أ-١). يُعيد سببَ السقوط أو None.

    ليس تزيينًا للتقرير: سؤالٌ تُشتقّ إجابتُه بلا موضعٍ يُشار إليه لا يمكن تكذيبُه ولا تصديقُه ⇒ يُسقط
    قبل أن يُطرح. والموضعُ يُشتقّ **داخل `truth` من القيم نفسها** (لا من مصدرٍ ثانٍ) فلا تنقسم قاعدة.

    **ومراجعة ٥٢ · R52-2:** «غيرُ فارغ» ليست دليلًا — موضعٌ يُشير إلى الصفحة ٧٠٠ (والكشفُ ٦٢٩) مرّ
    لأنّ القائمةَ غيرُ فارغة. **ويُشترط أن تقع الصفحاتُ في نطاق الفحص، وأن تقع الصفوفُ في السلسلة**
    — وإلا سقط بالاسم.

    **ومقعدُ المعايير (مراجعة ٥٢):** كانا معاملَين **اختياريّين** ⇒ استدعاءٌ بلا قرص يمرّ بحكمٍ أضعفَ
    **صامتًا**، وهذا إعفاءٌ بالمسار لا حكم. فصارا **مطلوبَين**: موضعُ إثباتٍ لا يُقابَل بعالَمٍ (كشفٍ
    وسلسلةٍ) دعوى بلا مرجع. وضوابطُ لا‑قرصٍ تُمرّر بديلًا مُصغَّرًا صريحًا (`_Scan` في الاختبارات).
    """
    kind = (q.get("derive") or {}).get("kind")
    rule = PROOF_RULE.get(kind)
    if rule is None:
        return f"نوعٌ بلا قاعدةِ إثبات: {kind}"
    pr = (safe or {}).get("proof") or {}
    if rule == "rows" and not pr.get("rows"):
        return f"بلا صفوفِ إثبات (النوع {kind})"
    if rule == "pages" and not pr.get("pages"):
        return f"بلا صفحاتِ إثبات (النوع {kind})"
    if rule == "source" and not pr.get("source"):
        return f"بلا مصدرِ إثبات (النوع {kind})"
    if kind == "rows_matching" and safe.get("hits") is not None:
        # **لا تضيع مطابقةٌ صامتة** (مراجعة ٥٢ · وأمسكها قياسي): كلُّ مطابقةٍ إمّا لها معرّفُ صفٍّ،
        # وإمّا تُعلَن في `unmapped` ببابها وسببها. والمجموعُ يساوي عددَ المطابقات بالضبط.
        covered = len(pr.get("rows") or []) + len(pr.get("unmapped") or [])
        if covered != safe["hits"]:
            return (f"موضعُ المطابقة لا يغطّي المطابقات: {covered} من {safe['hits']} "
                    f"(والصامتُ ممنوع: كلُّ مطابقةٍ بلا مقابلٍ تُعلَن في `unmapped`)")
        if any(not (u or {}).get("why") for u in (pr.get("unmapped") or [])):
            return "مطابقةٌ غيرُ قابلةٍ للتموضع بلا سببٍ مُعلَن"
    scope = set(c.corpus_page_list())
    stray = sorted({p for p in (pr.get("pages") or []) if p not in scope})
    if stray:
        return f"موضعُ إثباتٍ خارج نطاق الفحص: {stray[:5]} من {len(scope)} صفحة"
    # **وحدُّ الصفوف يُقاس بـ`rows` وحدها** (كان مشروطًا بـ`c` أيضًا ⇒ اتّصالٌ يُمرّر صفوفًا بلا كوربوس
    # لا يُقاس ⇒ حارسٌ لا يستطيع السقوط — مقعدُ البنية).
    n = len(rows)
    bad_rows = sorted({r for r in (pr.get("rows") or []) if not 1 <= r <= n})
    if bad_rows:
        return f"صفوفُ إثباتٍ خارج السلسلة (1..{n}): {bad_rows[:5]}"
    return None


def truth(q: dict, c: Corpus, pack: dict, rows: list[dict]) -> tuple[object, dict]:
    """يُشتقّ الجوابُ من القرص. يُعيد (الجواب, ملخّصٌ آمنٌ بلا مبالغ).

    **`rows` إلزاميٌّ وهو عالمُ الصفوف الواحد**: صفوفُ السلسلة كما يراها النموذج
    (`tools.refusal_test.build_rows` ثم `qa_tools._number_rows`) — صفُّ الفهرس `i` رقمُه `i+1`.
    ولا يُشتقّ شيءٌ من صفوف الصفحة وحدها: ذاك ترقيمٌ ثانٍ كان يُنتج حكماً على جوابٍ صحيحٍ بالرفض
    (REVIEW-48 · P-1: «أكثرُ من نصف المنظومة لا تجيب» كانت **غلطةَ الحاكم**).
    """
    d = q["derive"]
    k = d["kind"]
    if k == "footer":
        v = num(c.footer(d["page"]).get(d["field"]))
        return v, {"kind": k, "page": d["page"], "field": d["field"], "found": v is not None,
                   "proof": {"rows": [], "pages": [d["page"]]}}
    if k == "page_sum_all":
        vals = [num(r.get("movement")) for r in c.rows(d["page"])]
        vals = [v for v in vals if v is not None]
        return ((sum(vals) if vals else None),
                {"kind": k, "page": d["page"], "rows": len(vals),
                 "proof": {"rows": _page_row_ids(rows, d["page"]), "pages": [d["page"]]}})
    if k == "count_rows":
        n = len(c.raw_rows(d["page"]))        # **المطبوعُ الخامّ** (لا المشتقُّ الذي يُسقِط صفوفاً)
        return n, {"kind": k, "page": d["page"], "rows": n,
                   "proof": {"rows": _page_row_ids(rows, d["page"]), "pages": [d["page"]]}}
    if k == "last_row_balance":
        rs = c.rows(d["page"])
        return ((num(rs[-1].get("balance")) if rs else None),
                {"kind": k, "page": d["page"], "rows": len(rs),
                 "proof": {"rows": _page_row_ids(rows, d["page"])[-1:], "pages": [d["page"]]}})
    if k == "argmax_row":
        # **هويّةُ الصفّ بترقيم النظام لا بترقيم الصفحة** (REVIEW-48 · P-1): الصفُّ `i` في `rows` رقمُه `i+1`
        # — وهو بعينه ما يقرؤه النموذج في `(صفحة N، صف row_no)`. وكان يُشتقّ من صفوف الصفحة وحدها،
        # فيُرفض جوابُ الأدوات الصحيح (قِيس: ٨/٨ في العائلة — والضابطُ في `tests/test_eval_row_numbering.py`).
        vals = [(i + 1, num(r.get("movement"))) for i, r in enumerate(rows) if r.get("page") == d["page"]]
        vals = [(i, v) for i, v in vals if v is not None]
        if not vals:
            return None, {"kind": k, "page": d["page"], "rows": 0}
        m = max(v for _, v in vals)
        tops = [i for i, v in vals if v == m]
        # **الحقيقةُ صفٌّ ومبلغٌ وتعادلٌ — لا فهرسٌ يُقارَن بمبلغ** (كان المصحِّحُ معكوساً: صحّحتُ ٢٠٢٦-٠٩-٢٤)
        return ({"amount": m, "tops": tops, "tie": len(tops) > 1},
                {"kind": k, "page": d["page"], "tops": tops,
                 "proof": {"rows": tops, "pages": [d["page"]]}})
    if k == "row_chain":
        ra, rb = c.rows(d["a"]), c.rows(d["b"])
        la = num(ra[-1].get("balance")) if ra else None
        fb = num(rb[0].get("balance")) if rb else None
        if la is None or fb is None:
            return None, {"kind": k, "a": d["a"], "b": d["b"], "found": False}
        return ({"equal": abs(la - fb) < 0.005, "diff": round(abs(fb - la), 2)},
                {"kind": k, "a": d["a"], "b": d["b"], "equal": abs(la - fb) < 0.005,
                 "proof": {"rows": (_page_row_ids(rows, d["a"])[-1:] + _page_row_ids(rows, d["b"])[:1]),
                           "pages": [d["a"], d["b"]]}})
    if k == "rows_matching":
        hits = [(p, i) for p in c.corpus_page_list() for i, r in enumerate(c.rows(p))
                if d["pattern"] in str(r.get("desc") or "")]
        pages_hit = sorted({p for p, _ in hits})
        # **الموضعُ = الصفوفُ المطابِقة** لا كلُّ صفوفِ الصفحات المطابِقة (كان ٢٥ صفًّا لأربع مطابقات،
        # و٨٥٩ لـ١٦٠ ⇒ فائضٌ لا يُعيِّن شيئًا — مراجعة ٥٢ · R52-2). والتحويلُ من الفهرس المحلّيّ إلى
        # ترقيم النظام **يُتحقَّق منه لكلّ معرّف**، وغيرُ القابل للتموضع **يُعلَن** لا يُسقط.
        ids, unmapped = _match_row_ids(rows, hits, c, d["pattern"])
        return hits, {"kind": k, "hits": len(hits), "pages": pages_hit,
                      "proof": {"rows": ids, "pages": pages_hit, "unmapped": unmapped}}
    if k == "date_encoding":
        ind, lat, ind_pages, lat_pages = 0, 0, set(), set()     # مرورٌ واحدٌ لكلّ فحص (كان مرّتين)
        for p in c.corpus_page_list():
            for r in c.rows(p):
                if re.search(f"[{ARABIC_INDIC}{PERSIAN}]", str(r.get("date") or "")):
                    ind += 1
                    ind_pages.add(p)
        for p in c.corpus_page_list():     # **نفسُ نطاق الفحص** (كان حزمةَ التقييم ⇒ عدّان على مقامين)
            for r in c.rows(p):
                dt = str(r.get("date") or "")
                if re.search(r"\d", dt) and not re.search(f"[{ARABIC_INDIC}{PERSIAN}]", dt):
                    lat += 1
                    lat_pages.add(p)
        which = "arabic_ind" == d["encoding"]
        return (ind if which else lat), \
               {"kind": k, "encoding": d["encoding"],
                "proof": {"rows": [], "pages": sorted(ind_pages if which else lat_pages)}}
    if k == "pack_meta":
        f = d["field"]
        v = {"pages": len(c.pages), "pack_pages": (pack.get("size_gate") or {}).get("value"),
             "identity": pack.get("identity"), "class_count": len(pack.get("census_classes") or [])}.get(f)
        return v, {"kind": k, "field": f, "proof": {"rows": [], "pages": [], "source": "pack_meta"}}
    if k == "absent":
        scope = c.corpus_page_list()
        return None, {"kind": k, "reason": d["reason"],
                      # **المطلوبُ إلى جانبِ نطاق الفحص**: «٧٠٠» غائبةٌ تُقرأ مع «١..٦٢٩» — وإلا فالغيابُ دعوى
                      "requested": d.get("page", d.get("year")),
                      "scan": {"first": min(scope) if scope else None,
                               "last": max(scope) if scope else None, "pages": len(scope)},
                      "proof": {"rows": [], "pages": _absent_pages(c, d)}}
    return None, {"kind": k, "unknown": True}


def check_abstention(q: dict, c: Corpus, pack: dict) -> tuple[bool, str]:
    """**ادّعاءُ الامتناع يُقاس أيضاً** — لا «لا يوجد» بلا قياس: الصفحةُ خارج الحزمة فعلاً؟ السنةُ غائبةٌ فعلاً؟

    هذا هو الفرقُ بين سؤالٍ عادلٍ وسؤالٍ ظالمه: لو كانت الصفحةُ ٣٠٠ موجودةً لكان جوابُ «لا يوجد» خطأً.
    """
    d = q["derive"]
    r = d["reason"]
    present = set(c.corpus_page_list())          # **نطاقُ النظام**: الكشفُ كلُّه (٦٢٩) لا حزمةُ تقييمي (٢٠٠)
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
        for p in c.corpus_page_list():           # نفسُ مجموعة الموضع بالضبط (كان حزمةَ التقييم وحدها)
            blob = json.dumps(c.page(p), ensure_ascii=False)
            hits += blob.count(f'"{d["field"]}"')
        return (hits == 0), f"الحقل {d['field']} يظهر {hits} مرّةً"
    if r == "boundary":
        # **نفسُ القاعدة**: الحدُّ يُقاس على نطاق الفحص لا على حزمة التقييم (نوعٌ بلا سؤالٍ اليوم،
        # ويُصلَح حتى لا يُنسخ الفرقُ إلى سؤالٍ يُكتب غدًا)
        nxt = d["page"] + 1
        return (nxt not in present), f"الصفحة {nxt} {'داخل' if nxt in present else 'خارج'} نطاقِ النظام ({len(present)} صفحة)"
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


def _spent_since(before: dict | None, cur: dict | None) -> float | None:
    """المصروفُ بين قراءتين لعدّاد المزوّد — **مصدرٌ واحدٌ للصيغة** يستهلكه السقفُ وسطرُ الكلفة معًا.

    العدّادُ **تراكميٌّ صاعد** (يُثبته أنّ الكلفةَ تُحسب `after − before`)، فالصيغةُ الصحيحة `cur − before`.
    وطرحُها معكوسًا يعني سقفًا **لا يبلغ الميزانيةَ أبدًا** — وهي العلّةُ التي أمسكتها مراجعة ٥٠ بعد أن
    أعلنتُ S-2 مُغلقًا (والبندُ كان بلا ضابطٍ يمسك العكس). `None` تعني «لا قياس» لا «صفرَ مصروف»."""
    if not before or not cur:
        return None
    b, c = before.get("usage"), cur.get("usage")
    if b is None or c is None:
        return None
    return float(c) - float(b)


def _price_source(a) -> str:
    """مصدرُ السعر — **يُكتب في ملفّ الجولة** (شرطُ مراجعة ١١٢: السعرُ جزءٌ من الدليل)."""
    return "cli" if getattr(a, "price_in_per_m", None) is not None else "models-list"


def _resolve_price(a) -> tuple[float, float] | None:
    """(سعرُ مليونِ رمزٍ مدخلًا, مخرجًا) — من سطر الأمر، وإلّا من قائمة النماذج العامّة."""
    if (getattr(a, "price_in_per_m", None) is not None
            and getattr(a, "price_out_per_m", None) is not None):
        return float(a.price_in_per_m), float(a.price_out_per_m)
    from statement_qa.qa import effective_model                       # noqa: PLC0415

    return fetch_model_price(effective_model(getattr(a, "model", None)))


def usage_snapshot(handler) -> dict:
    """لقطةٌ من عدّاد الرموز اللحظيّ — تُقابَل بلقطةٍ بعد السؤال فيُعرف نصيبُه وحدَه."""
    return dict(getattr(handler, "usage_metadata", None) or {})


# ───────── سعرُ النداء — **مُشاهَدٌ من الرموز، لا مُستنتَجٌ من رصيدِ حساب** (R112-1) ─────────
# **العطبُ المقيس (مراجعة ١١٢):** كان «سعرُ النداء» يُبنى من **رصيد حساب المزوّد** المقروء بعد كلّ
# سؤال، والرصيدُ يتحرّك **متأخّرًا وعلى دفعات**: ١٢ نافذةً من ١٣ رأت **صفرًا**، ثمّ كتلةٌ واحدة
# ($0.006732) نُسبت إلى سؤالٍ **بأداةٍ واحدة** ⇒ `0.006732 ÷ 2 × 36 × 1.5 = $0.18176` — **أكبرُ من
# السقف كلِّه** ⇒ توقّفٌ عند ١٣ من ٥٠ وصرفُ ١٧.٧٪. **و٦٠٪ من الصرف وقع خارج نوافذ الأسئلة.**
#
# **والقاعدة الآن:** العددُ من **البنية** (`question_ceiling`) · **والسعرُ مُشاهَد**: رموزُ كلّ ردٍّ
# (`usage_metadata` — يجمعها `UsageMetadataCallbackHandler` من `langchain-core`، فلا يُبنى بديلٌ يدويّ)
# مضروبةً في **سعرِ الرمز المنشور** (قائمةُ النماذج العامّة، بلا مفتاح) ⇒ **معروفٌ لحظةَ القرار من
# أوّل نداء، ومنسوبٌ إلى النداءات التي أنتجته** (فرقُ نافذة السؤال، لا رصيدٌ تراكميّ).
#
# **وحدُّه المُعلَن صريحًا:** سعرُ النداء **لا يمكن أن يكون حدًّا بنيويًّا**: بحدّ المخرجات
# (`MAX_ANSWER_TOKENS = 3000`) وسعرِ المخرج المنشور ($0.90 للمليون) يكلّف أسوأُ نداءٍ ≈ $0.0027
# ⇒ أسوأُ سؤالٍ بسيط (٣٦ نداءً) ≈ **$0.097** = السقفُ كلُّه. فالسعرُ مشاهدةٌ تُضرب في حدِّ النداءات.
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def price_from_models(payload: dict, model_id: str) -> tuple[float, float] | None:
    """(سعرُ مليونِ رمزٍ **مدخلًا**, ومخرجًا) بالدولار من قائمة النماذج العامّة — بلا مفتاح.

    تُقرأ **مرّةً** في الجولة وتُسجَّل في ملفّها (شرطُ مراجعة ١١٢) ⇒ فالسعرُ جزءٌ من الدليل لا من الذاكرة.
    و`None` تعني «لا سعرَ معلوم» — **لا صفرًا** (فالصفرُ سعرٌ يُقبل ويُعمي الحاجز).
    """
    for m in (payload or {}).get("data") or []:
        if m.get("id") != model_id:
            continue
        pr = m.get("pricing") or {}
        try:
            return float(pr["prompt"]) * 1e6, float(pr["completion"]) * 1e6
        except (KeyError, TypeError, ValueError):
            return None
    return None


def fetch_model_price(model_id: str) -> tuple[float, float] | None:
    """يقرأ أسعارَ النموذج من الشبكة (نقطةُ نهايةٍ عامّة، بلا مفتاح) — و`None` عند أيّ تعذّر."""
    import urllib.request

    try:
        req = urllib.request.Request(OPENROUTER_MODELS_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return price_from_models(json.loads(r.read().decode()), model_id)
    except Exception as e:                                   # noqa: BLE001 — قياسٌ لا يُسقط التشغيل
        print(f"  (تعذّر قراءةُ سعر النموذج: {type(e).__name__})", file=sys.stderr)
        return None


def usage_delta(before: dict | None, after: dict | None) -> dict:
    """فرقُ الرموز بين قراءتين لعدّاد الرموز — **نافذةُ سؤالٍ واحدة** (وليس تراكمًا).

    والعدّادُ هنا (`usage_metadata`) **لحظيّ** — لا يتأخّر كما يتأخّر رصيدُ الحساب ⇒ فالنافذةُ تصف
    نداءاتِها هي لا نداءاتَ غيرها (وهو عينُ عطب «٦٠٪ خارج النوافذ»).
    """
    out: dict = {}
    for model, cur in (after or {}).items():
        prev = (before or {}).get(model) or {}
        tin = int(cur.get("input_tokens") or 0) - int(prev.get("input_tokens") or 0)
        tout = int(cur.get("output_tokens") or 0) - int(prev.get("output_tokens") or 0)
        if tin or tout:
            out[model] = {"input_tokens": max(0, tin), "output_tokens": max(0, tout)}
    return out


def tokens_cost(usage: dict | None, price_in_per_m: float, price_out_per_m: float) -> tuple[float, int, int]:
    """(الكلفةُ بالدولار, رموزُ المدخل, رموزُ المخرج) من رموزٍ مشهودة × سعرِ الرمز المنشور.

    **وتقريبُه في الاتجاه الآمن:** رموزُ المدخل قد تحمل رموزًا مُخزَّنةً (cached) يُسعّرها المزوّد
    أرخصَ ⇒ فالمحسوبُ **حدٌّ أعلى** للكلفة، وهو الاتجاه الصحيح لسقفٍ لا يُخترق.
    """
    if not usage:
        return 0.0, 0, 0
    tin = sum(int(u.get("input_tokens") or 0) for u in usage.values())
    tout = sum(int(u.get("output_tokens") or 0) for u in usage.values())
    return (tin * price_in_per_m + tout * price_out_per_m) / 1e6, tin, tout


def observation(before: dict | None, after: dict | None, tools_used: list | None,
                price_in_per_m: float, price_out_per_m: float) -> tuple[float, int] | None:
    """مشاهدةُ نافذةٍ واحدة: **(كلفةُ رموزها, عددُ نداءات أثرها)** — أو `None` إن لم تُبلّغ رموزًا.

    **والأثرُ (`tools_used`) أدنى حدٍّ لنداءات النموذج** (كلُّ نداءِ أداةٍ سبقه نداءُ نموذج، وفوقها
    نداءُ الجواب) ⇒ فالقسمةُ على `النداءات + ١` **تعلو الكلفةَ الحقيقيّةَ للنداء** فلا تُصغّر الحدّ.
    **ونافذةٌ بلا رموزٍ لا تُنتج صفرًا** — الصفرُ سعرٌ يُقبل ويُعمي الحاجز (وقد فعله ١٢ مرّة).
    """
    cost, _tin, _tout = tokens_cost(usage_delta(before, after), price_in_per_m, price_out_per_m)
    if cost <= 0:
        return None
    return cost, len(tools_used or [])


def finish_reasons_from(response) -> list[str]:
    """أسبابُ انتهاء النداءات من **بيانات الردّ نفسها** (مراجعة ١١٢) — ولا يُخترع سببٌ حين لا يُبلَّغ.

    **ولا مكوّنَ للمكتبة لهذا** (بخلاف عدّاد الرموز) ⇒ يُقرأ من `generation_info` ثمّ `llm_output`،
    وردٌّ لا يحمل شيئًا يعود **قائمةً فارغة** (تُقرأ «لم يُبلَّغ» ولا تُلبَس معنى «سليم»).
    """
    out: list[str] = []
    for gen_list in getattr(response, "generations", None) or []:
        for g in gen_list or []:
            info = getattr(g, "generation_info", None) or {}
            if isinstance(info, dict) and info.get("finish_reason"):
                out.append(str(info["finish_reason"]))
    llm_out = getattr(response, "llm_output", None) or {}
    if isinstance(llm_out, dict) and llm_out.get("finish_reason"):
        out.append(str(llm_out["finish_reason"]))
    return out


def finish_log():
    """مُرصِدٌ لأسباب انتهاء النداءات — **يُبنى عند الطلب** (استيرادُ المكتبة داخل الدالّة).

    يقرأ كلَّ ردٍّ عند وصوله ويراكم أوصافَه (`stop` · `length` · …) ⇒ فيُقرأ القطعُ من الدليل
    **بدل أن يُفترض** (طلبُ مراجعة ١١٢). وتسجيلُه **لا يغيّر سلوكَ التطبيق** (مراقبٌ صامت).
    """
    from langchain_core.callbacks import BaseCallbackHandler

    class _FinishLog(BaseCallbackHandler):
        def __init__(self) -> None:
            super().__init__()
            self.reasons: list[str] = []

        def on_llm_end(self, response, **kwargs) -> None:          # noqa: ANN001 · D102
            self.reasons.extend(finish_reasons_from(response))

    return _FinishLog()


def cap_evidence(*, spent_before: float, cost_here: float, bound: float, price: float, source: str,
                 meter_delta: float | None, tokens: int, tools: int, calls: int) -> dict:
    """ما حُوكم به لكلّ سؤال — **بلا تكرار**: حقلٌ واحد لكلّ معنى (R112-4).

    `cap_price_usd` سعرُ النداء المستعمل · `cap_price_source` مصدرُه · `spent_before_usd` المُنفَق
    قبل القرار (**من الرموز، لحظيّ**) · `cap_bound_usd` السقفُ الذي قُورن به · و`meter_delta_usd`
    شاهدُ رصيد الحساب لنفس النافذة (يُنشر ولا يحكم) ⇒ فالقانونُ يُعاد تشغيلُه من الملفّ
    (شرطُ البند ٣ في مراجعة ١١٢).
    """
    return {
        "cost_by_tokens_usd": round(cost_here, 6),
        "spent_before_usd": round(spent_before, 6),
        "cap_price_usd": round(price, 6),
        "cap_price_source": source,
        "cap_bound_usd": round(bound, 6),
        "tokens_observed": int(tokens),
        "tools_in_trace": int(tools),
        "calls_floor": int(calls),
        "meter_delta_usd": None if meter_delta is None else round(meter_delta, 6),
    }


# ───────── كلفةُ السؤال الواحد — **بحدٍّ حقيقيٍّ لا بمهلةٍ تُقدَّر** (R109-1 · فوق R108-6) ─────────
# **العطبُ المقيس:** السقفُ المأذون 0.10، والصرفُ بلغ **0.3482** (٣٫٥×)، والتوقّفُ وقع **بعد** الضرر.
# و**R108-6 قدّر الجذرَ بمهلةٍ × معدّلٍ لكلّ ثانية** — ومراجعةُ ١٠٩ أسقطت التقديرَ بالقياس:
# **الإنفاقُ لا يقف عند المهلة** (خيطُ القياس ينتظر 150 ث وينتهي، والسؤالُ يبقى يطلب وينفق — قِيس أنّ
# العمليّةَ بقيت حيّةً أربعَ دقائق بعد نتيجتها)، فالتقديرُ كان يفترض ما لا يقع.
#
# **والجذرُ الآن مكوّنُ المكتبة** (`statement_qa.qa`): `ModelCallLimitMiddleware` + `recursion_limit`
# + مهلةُ طلبٍ حقيقيّة ⇒ **لا يبلغ سؤالٌ واحدٌ أكثرَ من حدِّ نداءاتٍ معروف**، فصار أسوأُ كلفةٍ للسؤال
# **قابلًا للحساب قبل الطرح** لا للتقدير.
def per_call_cost(pairs: list[tuple[float, int]]) -> float:
    """أعلى كلفةِ **نداءِ نموذجٍ** مُشاهَدة = كلفةُ السؤال ÷ (نداءاتُ أثرِه + ١).

    **والمدخَلُ الآن رموزٌ مشهودة** (`observation`: رموزُ نافذة السؤال × سعرِ الرمز المنشور) — لا
    دلتا رصيدٍ متأخّرة (R112-1). والأثرُ (`tools_used`) **أدنى حدٍّ** لنداءات النموذج (كلُّ نداءِ
    أداةٍ سبقه نداءُ نموذج، وفوقها نداءُ الجواب) ⇒ فالقسمةُ على `النداءات + ١` **تعلو الكلفةَ
    الحقيقيّةَ للنداء** فلا تُصغّر الحدّ. وبلا عيّنة ⇒ **صفر** (لا يُخترع عدد).
    """
    vals = [c / (n + 1) for c, n in pairs if c is not None and c > 0]
    return max(vals) if vals else 0.0


#: **هامشٌ مُعلَن على كلفة النداء الأعلى (R110-1 · وسَببُه تغيّر في R112-1):**
#: كان سببُه **تأخّرَ عدّاد الحساب ≈١٢٠ ث** (فسؤالٌ يُقاس في ذيله قد لا يحمل كلفتَه كاملةً) — **وقد
#: سقط هذا السبب**: الرموزُ تُقرأ **لحظيًّا** لكلّ ردّ. **والباقي مُقاس:** سعرُ النداء **يتشتّت داخل
#: السلسلة** (النداءاتُ اللاحقة تحمل سياقًا أطول)، والقانون يضرب **أعلى** سعرٍ رُئي × هذا الهامش ⇒
#: فالهامشُ غطاءُ نموٍّ لا تعويضَ تأخّر، **ويُنشر مع كلّ جولة تشتُّتٌ المقيس** (`price_per_call_usd`
#: لكلّ نافذة في ملفّ الأجوبة ⇒ p50/p95/الأعلى قابلةٌ لإعادة الحساب من الدليل).
PER_CALL_MARGIN = 1.5


def next_question_ceiling(question: str, pairs: list[tuple[float, int]],
                          margin: float = PER_CALL_MARGIN) -> float:
    """سقفُ السؤال التالي: **حدُّ نداءاته × أعلى كلفةِ نداءٍ مُشاهَدة × الهامش** — حدٌّ أعلى لا وسط.

    **والحدُّ مشتقٌّ من بنية المسار** (`statement_qa.qa.question_ceiling`: طرحان لكلّ جزء + الاحتياط)
    لا من رقمٍ يكتبه أحدٌ بيده في أداة القياس. وبلا عيّنةٍ ⇒ **صفر**: لا سندَ يُضرب، **والثقبُ مُعلَن**
    (والحدُّ الحقيقيّ في التطبيق يبقى قائمًا).
    """
    from statement_qa.qa import question_ceiling

    return per_call_cost(pairs) * question_ceiling(question) * margin


def cap_verdict(spent: float | None, cap: float, bound: float) -> str:
    """قرارُ الصرف **قبل** طرح السؤال: `"go"` أو `"at-cap"` أو `"anticipatory"` أو `"unknown"`.

    دالّةٌ خالصةٌ تحمل القاعدةَ كلَّها (`tools/spend` بالسنّات) ⇒ تُقاس بسمٍّ بلا إنفاق:
    بلوغُ السقف، أو تقديرٌ يُوصِل الصرفَ بعد السؤال فوقه.
    """
    if spent is None:
        return "unknown"                     # لا قياسَ ⇒ لا حكم (ويُعلن الفرع التقديريّ المُعلَن)
    if at_or_over(spent, cap):
        return "at-cap"
    if bound and would_exceed(spent + bound, cap):
        return "anticipatory"
    return "go"


# ───────── السقف بالسنتات لا بالعائم (مراجعة ٥٢ · R52-4 · ومقعدُ البنية F7) ─────────
# **الوحدةُ صارت مشتركةً**: `tools/spend.py` — لأنّ الموضعَ المحلّيّ كان يُغلق الصنفَ في أداةٍ واحدة
# وأربعةُ أشقّاءَ يُقارنون السقفَ بعائمٍ خامّ (`compare_prompts` · `page_numbers` · `pos_witness` · `scale_slice`).
# والقاعدةُ (والتسامحُ المُعلَن ≤ ٠٫٥ سنت) في رأس تلك الوحدة، ويقيسها `tests/test_spend_unit.py`.


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
        # **والفهرسُ يُقابَل بالفهرس — بترقيمٍ واحد**: `tops` بترقيم النظام (`(صفحة N، صف row_no)`)،
        # ولا يُقبَل ترقيمُ الصفحة المحلّيّ. (REVIEW-48 · P-1: قبولُ الترقيمين معاً كان يُسقط ٨/٨ من عائلة
        # `argmax_row`، وضابطُه القديم لم يكشفه لأنّ صفحتَه الأولى في بياناتها فالتطابقُ فيها حتميّ.)
        claimed_idx = _claimed_row_index(ans)
        tops_g = {int(x) for x in (t.get("tops") or [])}
        idx_ok = claimed_idx is not None and claimed_idx in tops_g
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
        # **أسماءُ الأدوات (R104-1 · البند ③):** `trace_len` يعدّ **الصفوف** لا النداءات ⇒ فسؤالٌ
        # استدعى أداةً بلا صفوف (`page_footer`) أو لم يستدعِ شيئًا يبدوان «صفرَ أثر» سواءً.
        self.tools_used = list(rec.get("tools_used") or [])
        self.scope = rec.get("scope") or "in_scope"
        self.refused = bool(rec.get("refused"))


def _spec_sha(path: pathlib.Path | None = None) -> str:
    """بصمةُ **ملفّ الأسئلة المستعملِ فعلًا** — تُحفظ مع كلّ جواب ليكون الربطُ قابلاً للتدقيق.

    الجولة ٤٩ · S-4: كان المسارُ **مكتوبًا في الكود** (`docs/eval_pack/questions.json`) ⇒ تشغيلٌ بملفّ
    أسئلةٍ آخر يُختم ببصمة ملفٍّ لم يُقرأ ⇒ الشاهدُ يشهد على غير ما وقع. الآن يُمرَّر الملفُّ المستعمل.
    """
    import hashlib
    p = pathlib.Path(path) if path else (pathlib.Path(__file__).resolve().parent.parent / "docs/eval_pack/questions.json")
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
    cur_sha = _spec_sha(a.questions)
    stale = 0
    results = []
    for rec in data.get("results", []):
        q = by_id.get(rec["id"])
        # **النائبُ ليس جواباً** (الجولة ٤٩ · P-3/S-3): `<انتهت المهلة>` كان يُحكم عليه فشلاً فيدخل المقامَ
        # ويُخفي أنّ الجولةَ لم تُجب. الآن يُعلَن نائبًا ولا يدخل الحكمَ ولا المقاييس.
        if eval_stamp.is_substitute(rec):
            results.append({**rec, "ok": None, "substitute": True,
                            "why": f"نائبٌ (لا جواب): {str(rec.get('answer'))[:48]}"})
            print(f"{rec['id']:9s} ➖ نائبٌ (لا جواب) ⇒ لا يُحكم عليه ولا يدخل المقام")
            continue
        if q is not None:
            truth_val, _ = truth(q, c, pack, rows)
            ok, why = score_answer(q, truth_val, rec.get("answer", ""), _Trace(rec), rows)
            # **لا يُكتب فوق نصّ السؤال المحفوظ**: الملفُّ شاهدٌ على ما طُلب فعلاً (كان يُستبدل فيُفقد الشاهد)
            rec = {**rec, "ok": ok, "why": why, "metric": q["metric"], "expect": q["expect"],
                   "cat": q["cat"], "kind": q["derive"]["kind"]}
            # **أثرٌ قديمٌ مقصوص** (REVIEW-48 · P-2 · والجولة ٤٩): القاعدةُ في `eval_stamp.is_trace_suspect`
            # موضعًا واحدًا ⇒ فلا تنقسم بين `--rescore` وأداة المقارنة.
            if eval_stamp.is_trace_suspect(rec):
                rec["trace_suspect"] = True
            if not eval_stamp.is_publishable(rec, cur_sha):
                stale += 1
        results.append(rec)
        print(f"{rec['id']:9s} {'✅' if rec.get('ok') else '❌'} {rec.get('why', '')}")
    # **الحكمُ قبل الكتابة** (الجولة ٤٩ · S-3): كان الملفُّ يُكتب ثم يُرفض النشر ⇒ يُمحى شاهدٌ بلا مقابل.
    judged = [r for r in results if not r.get("substitute")]
    good, why = (eval_stamp.publishable_or_why(judged, cur_sha) if judged
                 else ([], "لا سجلَّ محكومًا: كُلُّ صفوفِ الملفّ نوائبُ (مهلةٌ/عطبٌ) — لا يُحكم على نائب"))
    if judged and not good and not getattr(a, "allow_stale", False):
        print(f"\n{why}\n   ⇒ **لا تُطبع مقاييسُ من سجلٍّ لا شاهدَ له على السؤال المطروح** — "
              f"للتشخيص وحده: `--allow-stale`.")
        print(f"   ⇒ **ولا يُكتب الملفّ** ({out}): الشاهدُ لا يُمحى بحكمٍ لا يُنشر.")
        return 3
    data["results"] = results
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    if stale:
        print(f"\n⚠️ {stale} سجلاً كُتب **قبل** بصمةِ الأسئلة الحاليّة ({cur_sha}) ⇒ نصُّ السؤال في السجل قد يخالف "
              f"ما طُلب فعلاً. الأصلُ: إعادةُ الطرح. **ولا يُنشر رقمٌ من سجلاتٍ غيرِ مطابقةِ البصمة.**")
    if not good:
        print(f"\n{why}\n   ⇒ تُطبع الآن **تشخيصيّاً** ويُمنع نشرُها.")
    _print_metrics(results)
    return 0


def run_questions(a, qs: list[dict], c: Corpus, pack: dict, spec: dict) -> int:
    """تشغيلُ الأسئلة على سلسلة السؤال الحقيقيّة — **مدفوع**، ويُقاس بأمرٍ صريح."""
    src = pathlib.Path(__file__).resolve().parent.parent / "src"
    sys.path.insert(0, str(src))
    from tools.refusal_test import build_footers, build_rows      # noqa: PLC0415
    from statement_qa.chunking import chunk_rows                  # noqa: PLC0415
    from statement_qa.qa import answer_question, build_llm, effective_model   # noqa: PLC0415
    from statement_qa.retriever import build_index                # noqa: PLC0415

    before = _key_usage()
    print(f"[1/4] بناءُ الجدول من {a.run} …", flush=True)
    rows, n_pages = build_rows(a.run)
    print(f"      {n_pages} صفحة | {len(rows)} صفًّا", flush=True)
    # **التذييلاتُ المطبوعة (R77):** يُبنى بالدالّة نفسِها التي يبنيها التطبيق (`app.py`)، ويُمرَّر
    # إلى الأدوات — وبدونه أجابت أداةُ `page_footer` «لا يوجد» لكلّ صفحة: **قاس المقياسُ نفسَه**
    # لا المنتجَ (قِيس: صنفُ footer 0/8، ولكلّ صفحةٍ منها تذييلٌ مطبوعٌ في البيانات).
    try:
        footers = build_footers(a.run)
    except Exception as e:                       # noqa: BLE001 — تشغيلٌ بلا مجلّد `results/`
        # **لا يُسقط التشغيلَ ولا يمرّ صامتًا:** يُعلن الحدَّ ويقول ما يترتّب عليه بالضبط
        # (أداةُ `page_footer` تُجيب «لا يوجد» لكلّ صفحة ⇒ صنفُ footer بلا معنى في هذه الجولة).
        footers = {}
        print(f"      ⚠️ لا تذييلاتٌ مطبوعة ({type(e).__name__}) ⇒ صنفُ التذييل لا يُقاس هذه الجولة",
              flush=True)
    print(f"      تذييلاتٌ مطبوعة: {len(footers)} صفحة", flush=True)
    print("[2/4] بناءُ الفهرس الدلاليّ (محلّيّ) …", flush=True)
    chunks = chunk_rows([{**r, "row_no": i + 1} for i, r in enumerate(rows)])
    store = build_index(chunks)
    print(f"      {len(chunks)} قطعة", flush=True)
    # ٤) الطرح: كلُّ سؤالٍ في خيطٍ بمهلة — انظر `_ask` (عميلُ النموذج واحدٌ يُبنى هنا)
    # **وعدّادُ الرموز اللحظيّ (R112-1):** مكوّنُ المكتبة يجمع `usage_metadata` لكلّ ردٍّ لحظةَ وصوله
    # ⇒ فسعرُ النداء يُشاهَد ولا يُستنتَج من رصيدٍ متأخّر. **ولا يُلمَس `invoke`** (الوسائطُ تُمرَّر
    # إلى العميل نفسه)، فيبقى ضابطُ «النداءُ بلا حالةِ رسم» صادقًا.
    from langchain_core.callbacks import UsageMetadataCallbackHandler   # noqa: PLC0415

    usage = UsageMetadataCallbackHandler()
    finishes = finish_log()
    llm = build_llm(a.model, callbacks=[usage, finishes])
    model_id = effective_model(a.model)     # **المعرّفُ الفعليّ** — به يُقرأ سعرُه ويُكتب في الدليل
    out = a.out or (pack_io.data_root() / "data/eval_pack/answers.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    prev_all: dict[str, dict] = {}         # كلُّ ما سبق (وإن كان نائباً) — لا يُسقطه الحفظُ التدريجيّ
    if out.exists():                       # **استئنافٌ**: جوابٌ محفوظٌ لا يُعاد سؤالُه (ولا يُدفع ثمنُه مرّتين)
        try:
            prev_all = {r["id"]: r for r in json.loads(out.read_text()).get("results", [])}
        except (OSError, json.JSONDecodeError, KeyError):
            prev_all = {}
    curent = _spec_sha(a.questions)
    done = {k: v for k, v in prev_all.items()
            # **النائبُ ليس جواباً** ⇒ يُعاد سؤالُه · **وجوابُ نصٍّ آخر ليس جواباً لهذا السؤال** (قِيس:
            # أربعُ إعاداتِ صياغةٍ في مدىً واحد ⇒ كان يُعاد استخدامُ جوابِ النصّ القديم صامتاً).
            if not eval_stamp.is_substitute(v) and eval_stamp.is_publishable(v, curent)}
    todo = [q for q in qs if q["id"] not in done]
    # **والسعرُ يُقرأ عند الطلب فقط:** بلا سقفٍ لا حاجةَ لسعر (ولا نداءَ شبكةٍ بلا سبب) ⇒ فلا يُقاس
    # سعرٌ لا يستهلكه قانون. **وقانونُ السقف يستهلكه** ⇒ فيسقط الفشلُ مُغلَقًا إن لم يُقرأ.
    price_pair = _resolve_price(a) if a.budget else None
    if a.budget:                       # **سقفٌ يُقاس بالحدّ لا بالتقدير** (S-2 · R110-1 · ثمّ R112-1)
        # كان `cap = budget / 0.01` ⇒ ٦٠ لخمسين سؤالًا ⇒ **لا يُلجِم أبدًا** ويُوكَل إلى تقديرٍ مُقنَّع.
        # **وبوّابتان قبل أوّل نداء (fail-closed):** شرطُ القرار «يُقرأ العدّادُ قبل وبعد» لا يتحقّق
        # بلا رصيدٍ يُقرأ، **والسقفُ لا يُحسب بحدٍّ** بلا سعرِ رمزٍ مشهود ⇒ فلا نداءَ مدفوعًا في الحالين.
        if before is None:
            print("⛔ رصيدُ المفتاح لا يُقرأ قبل الجولة ⇒ لا مجموعَ يشهد لها (شرطُ القرار: يُقرأ العدّادُ "
                  "قبل وبعد، والبعديّةُ بعد الخروج بثلاث دقائق) ⇒ **لا نداءَ مدفوعًا** · رمزُ الخروج 5.",
                  flush=True)
            return 5
        if not price_pair:
            print("⛔ سعرُ رمز النموذج لم يُقرأ (قائمةُ النماذج العامّة) ولا سعرَ صريحًا من سطر الأمر ⇒ "
                  "**سقفُ السؤال لا يُحسب بحدٍّ مشهود** — وهو عينُ عطب REQ-108-02 (سعرٌ من رصيدِ حسابٍ "
                  "متأخّر) ⇒ **لا نداءَ مدفوعًا** · رمزُ الخروج 5.", flush=True)
            return 5
        print(f"      سعرُ الرمز: ${price_pair[0]:.4f}/M مدخلًا · ${price_pair[1]:.4f}/M مخرجًا "
              f"({_price_source(a)})", flush=True)
    if getattr(a, "only", None):           # إعادةُ أسئلةٍ بعينها (بعد تصحيح نطاقِها أو صياغتِها)
        want = {x.strip() for x in a.only.split(",") if x.strip()}
        todo = [q for q in qs if q["id"] in want]
        done = {k: v for k, v in done.items() if k not in want}
    print(f"[3/4] طرحُ الأسئلة ({len(todo)} من {len(qs)} · ومحفوظٌ سابقاً {len(done)}) "
          f"على {a.model or 'الافتراضيّ'} …\n", flush=True)

    order = [q["id"] for q in qs]
    import threading

    def _ask(qtext: str, out_box: dict) -> None:
        """سؤالٌ واحدٌ في خيط: تعليقُه لا يُسقط الجولةَ (ولا يقتل الخيط — يُترك معلّقاً ويُسجَّل فشلُه)."""
        try:
            # **النطاقُ يُمرَّر كما يُمرّره التطبيق (R93-10):** كان النداءُ بلا `scope` ⇒ القالبُ يقول
            # «غيرُ مُعلَن» بينما المستخدمُ يرى نصًّا كاملًا («<الاسم> · ٦٢٩ صفحة · <N> حركة مُنظَّمة»)
            # ⇒ **الرقمُ المنشور يصف تلقينًا لا يُرسله التطبيق.** والصيغةُ تُنادَى من موضعها الواحد
            # (`statement_qa.qa.scope_text`)، والاسمُ اسمُ مجلّد التشغيلة (والتطبيقُ يضع اسمَ الملفّ
            # المرفوع — المصدرُ مختلفٌ ومُعلَن، والصيغةُ واحدة).
            # **والسجلُّ فارغٌ بالبناء:** الحزمةُ تطرح كلَّ سؤالٍ في دورةٍ مستقلّة ⇒ فالرقمُ يصف
            # **الدورةَ الأولى** في جلسةٍ جديدة، ولا يُدَّعى أنّه يصف سؤالًا تابعًا.
            r = answer_question(store, qtext, rows=rows, chunks=chunks, llm=llm,
                                footers=footers, scope=_pack_scope(rows, a.run, n_pages))
            out_box.update({"answer": r.answer or "", "used": list(getattr(r, "used_row_nos", None) or []),
                            "tools_used": list(getattr(r, "tools_used", None) or []),
                            "scope": getattr(r, "scope", None), "refused": bool(getattr(r, "refused", False))})
        except Exception as e:                                   # noqa: BLE001 — عطبٌ يُسمّى لا يُسقط الجولة
            out_box["error"] = f"{type(e).__name__}: {e}"

    halt = 0                       # **رمزُ التوقّف المُسمّى** (مراجعة ٥١ · البند ٥): 0 = لا توقّفَ بالسقف،
    # 3 = بلوغُ السقف، 4 = عدّادٌ تراجعيّ. كان `break` يُكمل إلى `return 0/1` ⇒ أتمتةٌ تقرأ توقّفًا
    # مُعلَنًا «نجاحًا». والتوقّفُ ليس حكمًا على الأجوبة ⇒ لا يجوز أن يُصبح رمزَ نجاح.
    observations: list[tuple[float, int]] = []     # (كلفةُ رموزِ نافذة, أدواتُ أثرها) — **مشاهدةٌ لحظيّة**
    bound = 0.0                                    # سقفُ السؤال القادم — وهو الذي يقارَن بالسقف الماليّ
    spent_tokens = 0.0                             # المُنفَقُ من الرموز × السعر — **لحظيّ، وهو ما يحكم**
    price_in, price_out = price_pair or (0.0, 0.0)
    meter_here: float | None = None
    for i, q in enumerate(todo, 1):
        # **قرارُ الشراء بحدِّ السؤال القادم (R110-1) × سعرِ نداءٍ مشهود (R112-1):** كان السعرُ
        # يُستنتَج من **رصيد حسابٍ متأخّر** ⇒ ١٢ نافذةً صفرًا ثمّ كتلةٌ واحدة نُسبت إلى سؤالٍ بأداةٍ
        # واحدة ⇒ سقفٌ **$0.18176** أكبرُ من السقف كلِّه ⇒ توقّفٌ عند ١٣ من ٥٠. والآن السعرُ من
        # **رموز الردود نفسِها** ⇒ موجبٌ من السؤال الثاني على الأكثر، ومنسوبٌ إلى نداءاته.
        bound = next_question_ceiling(q["q"], observations)
        price = per_call_cost(observations)
        source = "observed-tokens" if observations else "none-observation"
        meter_before_i: float | None = None
        if a.budget:                   # **المقياسُ قبل الطلب** (S-2) · والرصيدُ **شاهدٌ على المجموع**
            cur_u = _key_usage()
            meter_before_i = _spent_since(before, cur_u)
            if meter_before_i is not None and meter_before_i < 0:
                # **توقّفٌ مُسمّى عند عدّادٍ تراجعيّ** (مراجعة ٥٠ · مقعد Spec · P1): عدّادٌ ينقص يعني أنّ ما
                # يُقاس ليس ما يزيد بالصرف ⇒ لا سقفَ يُوثق به؛ والصمتُ هنا سقفٌ معطَّلٌ يُنشر كأنّه يعمل.
                print(f"\n⛔ **العدّادُ تراجع** ({before.get('usage') if before else '؟'} ⇒ "
                      f"{cur_u.get('usage') if cur_u else '؟'}): الفرقُ سالبٌ ⇒ لا سقفَ يُقاس بهذا المقياس "
                      f"⇒ توقّفٌ مُسمّى قبل السؤال {i} (fail-closed) · رمزُ الخروج 4.", flush=True)
                halt = 4
                break
            # **والبابُ البعديّ: رصيدُ الحساب** — لا يُغني عن الرموز ولا يُسقطها، **ولا يسمح بمرور**
            # صرفٍ تجاوز السقف (فلو أخطأ سعرُ الرمز في الاتجاه الأخفّ لعضّ هذا الباب).
            if meter_before_i is not None and at_or_over(meter_before_i, float(a.budget)):
                print(f"\n⛔ **رصيدُ الحساب** بلغ السقفَ ({meter_before_i:.4f} من {float(a.budget):.4f}) "
                      f"⇒ التوقّف قبل السؤال {i} (والمحسوبُ من الرموز {spent_tokens:.4f}). "
                      f"**التغطيةُ المُعلَنة: {i - 1} من {len(todo)}** · رمزُ الخروج 3.", flush=True)
                halt = 3
                break
            # **قرارُ الصرف في موضعٍ واحد** (`cap_verdict` دالّةٌ خالصةٌ تُقاس بسمّ بلا إنفاق):
            # البابُ البعديّ (بلغ الصرفُ السقف) والبابُ الاستباقيّ (سقفُ السؤال القادم يُوصِل فوقه).
            verdict = cap_verdict(spent_tokens, float(a.budget), bound)
            if verdict == "at-cap":
                print(f"\n⛔ السقفُ **المقيس** بلغ {spent_tokens:.4f} من {float(a.budget):.4f} "
                      f"(من الرموز × سعرِ الرمز) ⇒ التوقّف قبل السؤال {i}. "
                      f"**التغطيةُ المُعلَنة: {i - 1} من {len(todo)}** · رمزُ الخروج 3.", flush=True)
                halt = 3
                break
            # **توقّفٌ استباقيّ بسقف السؤال القادم** (مراجعة ٥١ · البند ٤ · **وجذرُه أُصلح في R109-1
            # ثمّ صار سعرُه مشهودًا في R112-1**): الحدُّ الحقيقيّ في التطبيق (حدُّ نداءاتٍ في الوكيل)،
            # وسعرُ النداء يُقرأ من الرموز ⇒ فالرقمُ المعلَن أدناه قابلٌ لإعادة الحساب من الدليل.
            if verdict == "anticipatory":
                meter_txt = "—" if meter_before_i is None else f"${meter_before_i:.4f}"
                print(f"\n⛔ **توقّفٌ استباقيّ**: المُنفَق {spent_tokens:.4f} + **سقفُ السؤال القادم** "
                      f"{bound:.4f} يتجاوز السقف {float(a.budget):.4f} ⇒ لا يُطرح السؤال {i}. "
                      f"(← سقفُ السؤال = `question_ceiling` من بنية المسار × ${price:.6f} **لسعر نداءٍ "
                      f"مشهود من الرموز** × هامش {PER_CALL_MARGIN} · ومصدرُه {source} · ورصيدُ الحساب "
                      f"للعلم: {meter_txt}) · **التغطيةُ المُعلَنة: {i - 1} من {len(todo)}** · "
                      f"رمزُ الخروج 3.", flush=True)
                halt = 3
                break
        u_before = usage_snapshot(usage)
        r_before = len(finishes.reasons)
        t0 = time.monotonic()
        truth_val, _ = truth(q, c, pack, rows)
        box: dict = {}
        t = threading.Thread(target=_ask, args=(q["q"], box), daemon=True)
        t.start()
        t.join(int(getattr(a, "timeout", 0) or 150))
        msg = {"error": "انتهت المهلة"} if t.is_alive() else (box or {"error": "لا جواب"})
        res = _Trace({"used_row_nos": msg.get("used"), "tools_used": msg.get("tools_used"),
                      "scope": msg.get("scope"),
                      "refused": msg.get("refused")}) if "answer" in msg else None
        ans = msg["answer"].strip() if res else f"<{msg.get('error')}>"
        ok, why = (score_answer(q, truth_val, ans, res, rows) if res
                   else (False, f"عطبٌ/مهلة: {msg.get('error')}"))
        # **مصدرٌ واحدٌ للحقول الثلاثة** (مراجعة ٥٢ · R52-3): كان `used_row_nos` و`trace_len` و
        # `cited_pages` تُشتقّ كلٌّ على حِدة من `res` ⇒ قصٌّ يُطبَّق على إحداها يجعل **السجلَّ يشهد
        # بغير ما حُكم به**، و`trace_len` يبقى كاملًا فلا يوسم السجلُّ مشكوكًا. الآن: قائمةٌ واحدة.
        trace = list(getattr(res, "used_row_nos", None) or []) if res else []
        secs = round(time.monotonic() - t0, 1)   # **يُقرأ مرّةً واحدة**: يستهلكه السجلُّ والقياس معًا
        done[q["id"]] = {"id": q["id"], "cat": q["cat"], "metric": q["metric"], "expect": q["expect"],
                         "kind": q["derive"]["kind"],
                         "q": q["q"], "answer": ans, "ok": ok, "why": why,
                         "cited_pages": sorted({rows[n - 1]["page"] for n in trace if 1 <= n <= len(rows)}),
                         "used_row_nos": trace,
                         "tools_used": list(getattr(res, "tools_used", None) or []) if res else [],
                         "trace_len": len(trace),      # **هويّةٌ محروسة**: trace_len == len(used_row_nos)
                         "scope": getattr(res, "scope", None) if res else None,
                         "refused": bool(getattr(res, "refused", False)) if res else None,
                         "spec_sha": _spec_sha(a.questions),   # **شاهدُ الربط**: أيُّ نصِّ سؤالٍ أُجيب عنه
                         "secs": secs}     # **المتزنُ في الدليل**: كم أخذ السؤال (يُقرأ قبل حساب الكلفة)
        # **ونافذةُ السؤال تُقاس رموزًا وتُسجَّل** (R108-6 · **وأُصلح إشارتُها في R112-1**): كان
        # يُسجَّل فرقُ **رصيد حسابٍ متأخّر** ⇒ ١٢ صفرًا وكتلةٌ واحدة (و٦٠٪ من الصرف خارج النوافذ).
        # والآن: فرقُ **رموز** النافذة نفسِها × سعرِ الرمز ⇒ منسوبٌ إلى نداءاتها، **وحقوقُ
        # `cost_by_tokens_usd`/`spent_before_usd`/`cap_price_usd`/`meter_delta_usd` تُكتب معه**
        # (شرطُ مراجعة ١١٢: القانونُ يُعاد تشغيلُه من الملفّ).
        u_after = usage_snapshot(usage)
        delta = usage_delta(u_before, u_after)
        cost_here, tok_in, tok_out = tokens_cost(delta, price_in, price_out)
        tools_now = list(getattr(res, "tools_used", None) or []) if res else []
        observed = observation(u_before, u_after, tools_now, price_in, price_out)
        reasons = finishes.reasons[r_before:]
        if a.budget:
            if meter_before_i is not None:
                meter_after_i = _spent_since(before, _key_usage())
                meter_here = (None if meter_after_i is None
                              else round(max(0.0, meter_after_i - meter_before_i), 6))
            done[q["id"]].update(cap_evidence(spent_before=spent_tokens, cost_here=cost_here,
                                              bound=bound, price=price, source=source,
                                              meter_delta=meter_here, tokens=tok_in + tok_out,
                                              tools=len(tools_now), calls=len(tools_now) + 1))
            done[q["id"]]["finish_reasons"] = reasons
            if observed is not None:
                observations.append(observed)
            spent_tokens += cost_here
        merged = {**prev_all, **done}      # النائبُ يبقى ما لم يُجَب عنه فعلاً
        out.write_text(json.dumps({"model": a.model or "افتراضيّ", "model_id": model_id,
                                   "spec_sha": _spec_sha(a.questions),
                                   "budget_usd": a.budget,     # **العقدةُ في الدليل**: ميزانيةُ الجولة مُعلنةٌ في ملفّها
                                   # **والسعرُ في الدليل** (شرطُ مراجعة ١١٢): يُقرأ مرّةً ويُكتب مع الجولة
                                   "price_in_per_m": None if not price_pair else price_pair[0],
                                   "price_out_per_m": None if not price_pair else price_pair[1],
                                   "price_source": _price_source(a),
                                   "results": [merged[k] for k in order if k in merged]},
                                  ensure_ascii=False, indent=1))   # **حفظٌ تدريجيّ: قتلُ العملية لا يُهدر جواباً**
        tools = ",".join(tools_now) or "—"
        print(f"{i:02d} {q['id']:9s} {'✅' if ok else '❌'} {why}  · أدوات: {tools}", flush=True)

    after = _key_usage()
    results = [done[k] for k in order if k in done]
    print(f"\n[4/4] الأجوبةُ كاملةً في {out} (خارج git: `data/` · حفظٌ تدريجيّ بعد كلّ سؤال)")

    print("\n" + "=" * 62)
    _print_metrics(results)
    d = _spent_since(before, after)          # **نفسُ صيغةِ السقف** (مصدرٌ واحدٌ يمنع تباعدَ الفرضيّتين)
    if d is not None:
        print(f"💰 الكلفةُ الفعليّةُ من المزوّد: ${d:.4f} (رصيدُ المفتاح {before.get('usage')} ⇒ {after.get('usage')})")
    else:
        print("💰 تعذّر قياسُ الكلفة من المزوّد — لا يُدَّعى رقمٌ بلا مصدر.")
    if halt:                       # التوقّفُ المُسمّى يسبق الحكم (٣ سقف · ٤ عدّادٌ تراجعيّ) — مراجعة ٥١
        return halt
    return 0 if all(r["ok"] for r in results) else 1


def _print_metrics(results: list[dict]) -> None:
    """المقاييسُ الثلاثة + تفصيلٌ بالقاعدة (يُظهر **أين** العطب لا كمّه فقط).

    **والعنوانُ على قاعدة المالك (قراره 20261007-184500 البند ١: «المهلةُ سؤالٌ بلا جواب، لا سؤالٌ خارج
    العدّ»):** فالنائبُ (`ok is None` — انتهت مهلةٌ أو عطبٌ) **داخلَ مقام العنوان** (`X/50`)، والمقامُ
    النظيفُ (بلا نائبٍ ولا مشكوكِ قصّ) **سطرٌ ثانٍ مُسمًّى** — فلا يقرأ قارئُ العنوانِ رقمًا يخالف القاعدة.

    **(R106-2 · مراجعة ١٠٦):** كان العنوانُ على المقام المُستبعَد (تصميمُ الجولة ٤٩) ⇒ فطبع «٤٥/٤٩» ونقله
    كاتبُ التقرير عنوانًا، وهو **R94-1 بعينه** (الخطأُ نفسه وقع في 10-07 وصُحّح). فنُقل العنوانُ إلى القاعدة،
    **وبقي إعلانُ المستبعَد كما هو** (استبعادٌ صامتٌ يقرأ تغطيةً كاذبة). **والملفُّ لم يتغيّر:** `num-04`
    محفوظٌ فيه `ok: false` — العرضُ وحدَه كان يُخرجه من المقام.
    """
    subs = [r for r in results if eval_stamp.is_substitute(r)]
    susp = [r for r in results if eval_stamp.is_trace_suspect(r)]
    judged = [r for r in results if eval_stamp.is_judged(r)]
    #: **حدُّ العنوان (R107-3 · مراجعة ١٠٧):** العنوانُ = **المحكوم + النوائب** (وكلُّهم بلا مشكوكِ
    #: القصّ)، والمشكوكُ **مستبعَدٌ ومُسمًّى كما كان** لا مُدخَلٌ صامتًا. **والعلّةُ التي أُغلقت:** كان
    #: العنوانُ يعدّ سجلًا مشكوكًا صحيحًا **والسطرُ النظيفُ يقسمه على مقامٍ لا يحمله** ⇒ طُبع
    #: «المجموع 49/50» و«وبلا المستبعَد 49/48» — **حسابٌ يتجاوز مقامَه**، وهو تغييرُ معنًى غيرُ مُعلَن
    #: عن الأداة القديمة (كانت تطبع 48/48). **والصنفُ كامنٌ اليوم** (صفرُ مشكوكٍ في كلّ ملفّات الأجوبة
    #: الحديثة) — ويُقاس بضابطه فلا يعود كامنًا.
    scored = [r for r in results if not eval_stamp.is_trace_suspect(r)]
    for m, label in (("number", "دقّة الرقم"), ("citation", "صدق الاستشهاد من الأثر"), ("abstain", "صحّة الامتناع")):
        sel = [r for r in scored if r.get("metric") == m]     # المقامُ على القاعدة: كلُّ أسئلة الصنف
        n_ok = sum(1 for r in sel if r.get("ok"))
        print(f"{label:26s} {n_ok:2d}/{len(sel):2d}  {'█' * n_ok}{'·' * (len(sel) - n_ok)}")
    n_ok_all = sum(1 for r in scored if r.get("ok"))
    print(f"{'المجموع':26s} {n_ok_all:2d}/{len(scored):2d}")
    if len(judged) != len(scored):        # السطرُ النظيفُ يُسمّى ولا يُخفى (قاعدةٌ قديمةٌ باقية)
        n_ok_judged = sum(1 for r in judged if r.get("ok"))
        print(f"{'  وبلا المستبعَد':26s} {n_ok_judged:2d}/{len(judged):2d}"
              f"   (بلا {len(subs)} نائبًا · وبلا {len(susp)} أثرًا مشكوكَ القصّ)")
    if subs or susp:
        print(f"➖ مُستبعَدٌ من المقام: **{len(subs)} نائبًا** (مهلةٌ/عطبٌ — لم يُجب) "
              f"· **{len(susp)} أثرًا مشكوكَ القصّ** ⇒ المقامُ = {len(judged)} من {len(results)}")
    n_abs = sum(1 for r in judged if r.get("metric") == "abstain")
    fell = [r for r in judged if r.get("metric") == "abstain" and not r.get("ok")]
    invented = sum(1 for r in fell if "**اختراع**" in (r.get("why") or ""))
    silent = sum(1 for r in fell if "لم يُعلن" in (r.get("why") or ""))
    # المقامُ يُشتقّ لا يُكتب بيد — **والصنفان يُفصَلان** (وإلّا قرأ القارئُ صنفاً وقيس غيرُه)
    print(f"\n⛔ الامتناعاتُ الساقطة: {len(fell)}/{n_abs} — منها **اختراعُ مبلغٍ بلا سند {invented}** "
          f"· **عدمُ إعلان الامتناع {silent}**")
    by_kind: dict[str, list[bool]] = {}
    for r in results:
        by_kind.setdefault(r.get("kind") or "?", []).append(bool(r.get("ok")))
    if subs or susp:
        print(f"\n➖ **المُستبعَدُ من المقام (مُعلَن لا مخفيّ):** نوائبُ (مهلةٌ/عطبٌ) **{len(subs)}** · "
              f"أثرٌ مشكوكُ القصّ **{len(susp)}** ⇒ الحكمُ على **{len(judged)}** سجلاً فقط.")
    print("\nتفصيلٌ بالقاعدة:")
    for k, oks in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        print(f"  {k:16s} {sum(oks):2d}/{len(oks):2d}")


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def _pack_scope(rows: list[dict], run_dir, n_pages: int = 0) -> str:
    """نطاقُ الكشف كما يبنيه التطبيق — **بالصيغة نفسِها وبالرقم نفسِه** (R93-10 · R94-4).

    الصيغةُ تُنادَى من موضعها الواحد (`statement_qa.qa.scope_text`).
    **وعددُ الصفحات كان يُعدّ هنا بعدّادٍ ثانٍ** (`ledger.pages_of` = الصفحاتُ التي فيها صفوف ⇒ ٦٢٦)،
    والتطبيقُ يعدّ **الصفحات المقروءة** (٦٢٩) ⇒ فالنطاقُ كان يخالف نطاقَ التطبيق في الرقم وإن اتّفق في
    الصيغة. والعددُ الآن يأتي من **`build_rows`** الذي يُرجعه في السطر نفسِه (وكان مهمَلًا) ⇒ مصدرٌ واحد.
    والاسمُ يبقى اسمَ مجلّد التشغيلة (والتطبيقُ يضع اسمَ الملفّ المرفوع) — **مصدرٌ مختلفٌ مُعلَن.**
    """
    from statement_qa.qa import scope_text                          # noqa: PLC0415
    if not n_pages:
        n_pages = len({r.get("page") for r in rows if r.get("page") is not None})
    return scope_text(name=getattr(run_dir, "name", "") or "",
                      n_pages=n_pages, n_rows=len(rows), kind="")


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
    ap.add_argument("--price-in-per-m", type=float,
                    help="سعرُ مليونِ رمزٍ مدخلًا (يسبق قراءةَ قائمة النماذج — للسقف بلا شبكة)")
    ap.add_argument("--price-out-per-m", type=float,
                    help="سعرُ مليونِ رمزٍ مخرجًا (يُعلَن مصدرُه في ملفّ الجولة)")
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

    if bad and (a.execute or a.rescore) and not a.force:
        # **حاجبٌ في المسار المدفوع لا في المجّانيّ وحده**: جولةٌ تُصرف فوق مراسٍ لا تُقاس هي بالضبط ما
        # أنتج الأرقامَ المسحوبة (صفحتان «غائبتان» وهما موجودتان · «سنةٌ غائبة» فيها ٨٦٢ صفًّا).
        print(f"⛔ {len(bad)} عطباً في المراسي ⇒ لا طرحَ مدفوعاً ولا إعادةَ حكمٍ فوق ما لا يُقاس "
              f"(تجاوزٌ صريح: --force). القائمةُ مطبوعةٌ أعلاه.", file=sys.stderr)
        return 2
    if a.rescore:
        # **البوّابةُ قبل الفرعَين** (الجولة ٤٩ · S-3): كان الفرعُ يعود **قبل** فحص المراسي ⇒ جولةُ إعادةِ
        # حكمٍ فوق سؤالٍ يشير إلى صفحةٍ غيرِ موجودةٍ تُحكم وتُطبع «قابلةً للنشر» بـ`rc=0`. الآن: لا فرعَ
        # يُعبر البوّابة.
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
        from tools.refusal_test import build_rows                     # noqa: PLC0415
        rows, _ = build_rows(a.run)
        return rescore(a, qs, c, pack, spec, rows)

    if a.execute:
        sel = qs[: a.limit] if a.limit else qs
        return run_questions(a, sel, c, pack, spec)

    if a.validate:
        # **حاكمُ الإثبات** (الخارطة · أ-١): سؤالٌ تُشتقّ إجابتُه بلا موضعِ إثباتٍ يُسقط **قبل أن يُطرح**
        # — لا يُسأل عنه النموذجُ ثم يُكتشف أنّه لا يُكذَّب ولا يُصدَّق. والموضعُ من `truth` نفسها.
        from tools.refusal_test import build_rows as _vrows      # noqa: PLC0415 — عالمُ الصفوف الواحد
        _v_rows, _ = _vrows(a.run)
        for _q in qs:
            _, _safe = truth(_q, c, pack, _v_rows)
            # **مع الكوربوس**: الموضعُ لا يكفي أن يكون غيرَ فارغ — يُشترط أن **يقع** في نطاق الفحص
            _state, _why = classify_proof(_q, _safe, c=c, rows=_v_rows)   # **مُؤجَّلٌ مُعلَن ≠ مكسور**
            if _state == "missing":
                bad.append(f"{_q['id']}: {_why}")
            elif _state == "exception":
                print(f"  ⏸ مُؤجَّلٌ مُعلَن: {_q['id']} — {_why}")
        broken = [x for x in bad if x]
        print("المراسي: %s" % ("كلُّها تقع ✓" if not broken else f"{len(broken)} مرسًى مكسور ✗"))
        for _b in broken:
            print("  ✗", _b)
        return 1 if broken else 0

    from tools.refusal_test import build_rows as _build_rows      # noqa: PLC0415 — عالمُ الصفوف الواحد
    chain_rows, _ = _build_rows(a.run)
    table = []
    for i, q in enumerate(qs, 1):
        if a.page and i != a.page:
            continue
        val, safe = truth(q, c, pack, chain_rows)
        _st, why_proof = classify_proof(q, safe, c=c, rows=chain_rows)   # موضعُ الإثبات يُطبع مع كلّ سؤال
        # **والقيمةُ تبقى آخرَ عمود** (مستهلكٌ يقرؤها بـ`split()[-1]` — لا يُكسر عقدُ المخرَج)، والإثباتُ
        # عمودٌ **مضغوطٌ بلا مسافات** قبله، ووسمُ الاستثناءِ ملتصقٌ به لا منفصلًا.
        pj = dict(safe.get("proof") or {})
        # **ما يُكتب يُقرأ** (مقعدُ البنية): `requested`/`scan` كانا يُشتقّان ولا يُظهرهما شيء
        for k in ("requested", "scan"):
            if k in safe:
                pj[k] = safe[k]
        proof = json.dumps(pj, ensure_ascii=False, separators=(",", ":")) if a.truth else ""
        if a.truth and why_proof:
            proof += "⏸" if _st == "exception" else "⚠"
        shown = json.dumps(val, ensure_ascii=False) if a.truth else ""
        table.append((i, q["id"], q["cat"], q["metric"], q["expect"], safe.get("kind"), proof, shown))
    for i, qid, cat, metric, exp, kind, proof, shown in table:
        tail = (proof + (" " + shown if shown else "")).strip()
        print(f"{i:02d} {qid:9s} {cat:8s} {metric:14s} {exp:9s} {kind:14s} {tail}".rstrip())
    if not a.truth:
        print("\n(بلا مبالغ — والتفصيلُ الكاملُ بـ`--truth` على الشاشة وحدها)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
