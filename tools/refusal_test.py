#!/usr/bin/env python3
"""اختبار الرفض الحقيقي (Refusal Test) — يحقن أسئلة من خارج الكشف.

المبدأ: نظام مالي لا يُقاس بنجاحه في الأسئلة التي يعرفها، بل في رفضه
للأسئلة التي لا يعرفها. هنا نطرح أسئلة **لا جواب لها في الكشف** ونرصد:
- هل يقول حرفياً «غير موجود في الكشف»؟ أم يخترع رقماً؟
- وهل الأسئلة الرقمية تُجاب من الأدوات الحتمية (لا من النموذج)؟

الاستخدام:
    .venv/bin/python tools/refusal_test.py
    .venv/bin/python tools/refusal_test.py --slice data/local_sample/slice_629p
    .venv/bin/python tools/refusal_test.py --questions "كم رصيد بنك الرياض؟"

الملاحظة: يستهلك استدعاءات LLM حقيقية (سنتات قليلة لكل سؤال).
"""
from __future__ import annotations

import argparse
import re
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_qa.chunking import chunk_rows          # noqa: E402
from statement_qa.classify import annotate_types      # noqa: E402
from statement_qa.page_footers import printed_footers_from   # noqa: E402
from statement_qa.qa import answer_question, build_llm  # noqa: E402
from statement_qa.retriever import build_index        # noqa: E402
from statement_qa.vlm_reader import _parse_amount, chain_derive  # noqa: E402

_ARABIC = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _norm(text: str) -> str:
    """توحيدُ الأرقام (عربيةٌ-هندية ⇒ لاتينية) وحذفُ الفواصل — لمقابلةِ قيمةٍ بقيمة، بلا لمس المعنى."""
    return str(text or "").translate(_ARABIC).replace(",", "").replace("٬", "")

REFUSAL = "غير موجود في الكشف"

DEFAULT_QUESTIONS = [
    {"id": "A", "kind": "خارج الكشف تماماً (بنك آخر)", "expect": "رفض",
     "q": "كم رصيد حسابي في بنك الرياض؟"},
    {"id": "B", "kind": "خارج محتوى الكشف (بيانات شخصية)", "expect": "رفض",
     "q": "ما هو رقم جوال صاحب الحساب؟"},
    {"id": "C", "kind": "رقمي — يجب أن يستدعي أداة", "expect": "أداة",
     "q": "كم مجموع السحوبات من الصراف الآلي؟"},
    {"id": "D", "kind": "وصفي داخلي — بحث دلالي", "expect": "بحث",
     "q": "هل يوجد أثر مقاصة في الكشف؟"},
    # Four cases added after an external audit noted the set held only two real
    # refusal verdicts (P3-9): the failure that matters outside the covered
    # ground is not a rude answer, it is an INVENTED NUMBER. For these the
    # verdict is mechanical: any riyal figure in the answer means the model
    # filled a gap the statement does not have.
    # CORRECTION, recorded: this case was written as «a year outside the
    # statement» and 2019 turned out to be INSIDE it (342 rows, the statement
    # spans 2013–2024). The old expectation called a correct answer a defect.
    # The outside-year case is now 2005, and the inside-year case below asserts
    # the opposite thing: the gate must NOT swallow it.
    {"id": "E", "kind": "سنة خارج مدى الكشف (٢٠٠٥)", "expect": "لا بيانات",
     "q": "كم مجموع الحركات في عام ٢٠٠٥؟"},
    {"id": "I", "kind": "سنة داخل المدى — يجب ألا تُبتلع", "expect": "أداة",
     "q": "كم مجموع الحركات في عام ٢٠١٩؟"},
    {"id": "F", "kind": "سؤال مركّب نصفه موجود", "expect": "أداة",
     "q": "كم مجموع الحوالات الواردة من شركة أ، وكم عدد الحوالات من مؤسسة "
          "غير مذكورة في الكشف؟"},
    {"id": "G", "kind": "مبلغ غير موجود", "expect": "لا بيانات",
     "q": "هل يوجد تحويل بمبلغ 951196.47 ريال؟"},
    {"id": "H", "kind": "صفحة تتجاوز الملف", "expect": "لا بيانات",
     "q": "ماذا يوجد في الصفحة ٧٠٠؟"},
]

# A riyal figure stated in the answer, western or Arabic-Indic. The AUDIT
# question is «did it invent a number?», not «did it sound polite?».
_AMOUNT_RE = re.compile(
    r"\d[\d,]*\.\d\d|[\u0660-\u0669]{1,3}[,.:\u066b\u066c][\u0660-\u0669]{2}")


def _has_amount(text: str) -> bool:
    return bool(_AMOUNT_RE.search(text or ""))


def build_rows(slice_dir: Path) -> tuple[list[dict], int]:
    """نتائج الصفحات المُصدَّقة (الكاش) → جدول الصفوف الموحّد.

    يُعيد تشغيل سلسلة الرصيد بنفس منطق التطبيق (chain_derive مع
    رصيد الصفحة السابقة)، بلا أي استدعاء VLM — الكاش مُتحقق منه سابقاً.
    """
    results = sorted((slice_dir / "results").glob("pg-*.json"))
    if not results:
        raise SystemExit(f"لا نتائج في {slice_dir / 'results'}")
    all_rows: list[dict] = []
    prev_closing = None
    for f in results:
        d = json.loads(f.read_text(encoding="utf-8"))
        pg = int(d.get("pg") or f.stem.split("-")[1])
        raw = []
        for r in d.get("raw_rows") or []:
            raw.append({**r,
                        "movement": _parse_amount(r.get("movement")),
                        "balance": _parse_amount(r.get("balance"))})
        rows = chain_derive(raw, prev_balance=prev_closing)
        for r in rows:
            if r["balance"] is None:
                continue
            if r["opening"]:
                all_rows.append({"page": pg, "kind": "opening",
                                 "balance": r["balance"], "movement": None,
                                 "side": "", "ok": True,
                                 "desc": r.get("desc"), "date": r.get("date")})
            else:
                all_rows.append({"page": pg, "kind": "txn",
                                 "balance": r["balance"],
                                 "movement": r["derived_movement"],
                                 "printed_mv": r["movement"],
                                 "side": r["side"], "ok": r["ok"],
                                 "desc": r.get("desc"), "date": r.get("date")})
        nxt = next((r["balance"] for r in reversed(rows)
                    if r["balance"] is not None), None)
        if nxt is not None:
            prev_closing = nxt
    annotate_types(all_rows)
    return all_rows, len(results)


def build_footers(slice_dir: Path) -> dict:
    """**التذييلاتُ المطبوعةُ من المصدر نفسِه** (R77): تُقرأ من `results/pg-*.json` وأحكامُها من
    `slice_report.json`، وتُبنى بـ`page_footers.printed_footers_from` — نفسِ الدالّة التي يبنيها
    التطبيق ⇒ فلا نسخةَ ثانيةَ من الصيغة في مسار القياس.
    """
    readings = {}
    for fp in sorted((slice_dir / "results").glob("pg-*.json")):
        try:
            j = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:      # ملفٌّ معطوبٌ يُعلَن غيابًا ولا يُخمَّن
            continue
        pg = j.get("page") or int(fp.stem.split("-")[-1])
        readings[int(pg)] = j.get("footer")
    checks = []
    rep = slice_dir / "slice_report.json"
    if rep.exists():
        checks = (json.loads(rep.read_text(encoding="utf-8")).get("per_page") or [])
    return printed_footers_from(readings, checks)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", default="data/local_sample/slice_629p")
    ap.add_argument("--questions", nargs="*", default=None,
                    help="أسئلة مخصّصة بدل المجموعة الافتراضية")
    ap.add_argument("--questions-file", default=None,
                    help="ملفُّ أسئلةٍ (JSON): [{id, q, expect, page, field}] — للعائلات المُشتقّة")
    ap.add_argument("--with-footers", action="store_true",
                    help="يُمرّر التذييلاتِ المطبوعةَ إلى الأدوات (R77: أداةُ page_footer)")
    args = ap.parse_args()

    slice_dir = Path(args.slice)
    if not slice_dir.is_absolute():
        slice_dir = ROOT / slice_dir

    t0 = time.time()
    print(f"[1/3] بناء الجدول من {slice_dir.name} …")
    rows, n_pages = build_rows(slice_dir)
    n_txn = sum(1 for r in rows if r["kind"] == "txn")
    print(f"      {n_pages} صفحة | {len(rows)} صف ({n_txn} حركة) "
          f"| {time.time() - t0:.1f}s")

    print("[2/3] بناء الفهرس الدلالي (محلياً، بلا شبكة للفهرسة) …")
    chunks = chunk_rows([{**r, "row_no": i + 1} for i, r in enumerate(rows)])
    store = build_index(chunks)
    print(f"      {len(chunks)} قطعة | {time.time() - t0:.1f}s")

    footers = None
    if args.with_footers:
        footers = build_footers(slice_dir)
        with_vals = sum(1 for f in footers.values() if any(f.get(k) for k in ("debits", "credits", "balance")))
        print(f"      [تذييلاتٌ مطبوعة] {len(footers)} صفحة ({with_vals} فيها أرقامٌ مقروءة) "
              f"· تُمرَّر إلى أداة `page_footer`")

    print("[3/3] طرح الأسئلة …\n")
    llm = build_llm()
    if args.questions_file:
        raw = json.loads(Path(args.questions_file).read_text(encoding="utf-8"))
        qs = [{"id": it.get("id") or f"Q{i+1}", "kind": it.get("kind") or "من ملف",
               "expect": it.get("expect") or "؟", "q": it["q"],
               "page": it.get("page"), "field": it.get("field")}
              for i, it in enumerate(raw)]
    elif args.questions:
        qs = [{"id": f"Q{i+1}", "kind": "مخصّص", "expect": "؟", "q": q}
              for i, q in enumerate(args.questions)]
    else:
        qs = DEFAULT_QUESTIONS

    verdicts = []
    for item in qs:
        print("=" * 72)
        print(f"[{item['id']}] {item['kind']}")
        print(f"السؤال: {item['q']}")
        res = answer_question(store, item["q"], rows=rows, chunks=chunks, llm=llm,
                              footers=footers)
        ans = (res.answer or "").strip()
        print(f"الجواب: {ans}")
        if res.used_row_nos:
            print(f"الأدلة (صفوف استدعتها الأدوات): {len(res.used_row_nos)} "
                  f"صفاً — أولها {res.used_row_nos[:5]}")
        else:
            print("الأدلة: لا أداة استُدعيت (مسار نصي/بحث)")
        print(f"المصادر: {len(res.sources)} قطعة")
        refused = bool(getattr(res, "refused", False)) or REFUSAL in ans
        gated = getattr(res, "scope", "in_scope") != "in_scope"
        used_tool = bool(res.used_row_nos)
        if item["expect"] == "رفض":
            ok = refused
            why = "رفض صريح ✓" if refused else "لم يرفض ✗ (خطر اختراع)"
        elif item["expect"] == "أداة":
            ok = used_tool
            why = "استدعى أداة ✓" if used_tool else "لم يستدعِ أداة ✗"
        elif item["expect"] == "لا بيانات":
            # The DETERMINISTIC verdict: did the gate decide this before the
            # model saw it? A regex over prose cannot tell an invented figure
            # from a refusal that quotes the figure it just rejected — which is
            # exactly how this check reported a false failure.
            ok = gated or not _has_amount(ans)
            why = ("منعتها البوابة قبل النموذج ✓" if gated
                   else "لم يخترع مبلغاً ✓" if ok
                   else "أجاب بمبلغ لا سند له في الكشف ✗")
        elif item["expect"] == "footer":
            # **الحكمُ من المصدر لا من العين (R77):** القيمةُ الصحيحةُ هي **المطبوعُ** في تذييل تلك
            # الصفحة، مُشتقّةً من الشريحة نفسِها — ويُقبل **الرفضُ الصريح** بديلًا (لا يُقبل رقمٌ آخر).
            f = (footers or {}).get(int(item.get("page") or 0)) or {}
            want = _norm(f.get(item.get("field") or "") or "")
            good = bool(want) and want in _norm(ans)
            refusal_ok = (REFUSAL in ans) or ("لا تذييل" in ans) or ("لم يُقرأ" in ans)
            ok = good or refusal_ok
            why = ("نُقلت القيمةُ المطبوعةُ نفسُها ✓" if good
                   else "رفضٌ صريحٌ بدل رقمٍ مخترَع ✓" if refusal_ok
                   else "لم تُنقل القيمةُ المطبوعة ✗")
        else:
            ok = True
            why = f"{'رفض' if refused else 'أجاب'} (لا حكم قاطع)"
        print(f"الحكم: {why}")
        verdicts.append((item["id"], ok, why))
        print()

    print("=" * 72)
    n_ok = sum(1 for _, ok, _ in verdicts if ok)
    print(f"الخلاصة: {n_ok}/{len(verdicts)} نجحت")
    for vid, ok, why in verdicts:
        print(f"  {'✅' if ok else '❌'} [{vid}] {why}")
    print(f"\nالزمن الكلي: {time.time() - t0:.1f}s")
    return 0 if n_ok == len(verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
