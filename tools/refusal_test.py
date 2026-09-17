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
from statement_qa.qa import answer_question, build_llm  # noqa: E402
from statement_qa.retriever import build_index        # noqa: E402
from statement_qa.vlm_reader import _parse_amount, chain_derive  # noqa: E402

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
     "q": "هل يوجد تحويل بمبلغ 987,654.32 ريال؟"},
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", default="data/local_sample/slice_629p")
    ap.add_argument("--questions", nargs="*", default=None,
                    help="أسئلة مخصّصة بدل المجموعة الافتراضية")
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

    print("[3/3] طرح الأسئلة …\n")
    llm = build_llm()
    if args.questions:
        qs = [{"id": f"Q{i+1}", "kind": "مخصّص", "expect": "؟", "q": q}
              for i, q in enumerate(args.questions)]
    else:
        qs = DEFAULT_QUESTIONS

    verdicts = []
    for item in qs:
        print("=" * 72)
        print(f"[{item['id']}] {item['kind']}")
        print(f"السؤال: {item['q']}")
        res = answer_question(store, item["q"], rows=rows, chunks=chunks, llm=llm)
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
