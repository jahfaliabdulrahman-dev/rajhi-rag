#!/usr/bin/env python3
"""أداةُ الدفتر (أ-٣): **بناءُ** دفتر كشفٍ من نتائج تشغيله، و**سؤالُه بأقصدٍ ثابتة**.

**العِلّة في وجودها (البندُ الثاني من ترتيب المالك):** الخارطةُ تشترط أنّ «**النموذجَ لا يكتب SQL**» —
وهذا شرطٌ لا يتحقّق ببندٍ في وثيقة، بل بواجهةٍ **لا يملك فيها الوكيلُ إلا اختيارَ قصدٍ وتقديمَ قيمة**.
فالأداةُ هنا: `ask <intent>` بقائمةٍ مغلقة (`coverage` · `unproven` · `totals` · `search` · `pages` · `qa`)
ومعاملَين قيميّين فقط (`--pg` · `--q`). ويُرفض ما سواها بالاسم — فلا استعلامَ حرٌّ ولا بناءَ نصّ.

والاستعمال:
    python tools/ledger.py build --run data/local_sample/slice_629p_v2 --db ~/دفتر.sqlite
    python tools/ledger.py ask --db ~/دفتر.sqlite totals
    python tools/ledger.py ask --db ~/دفتر.sqlite search --q "حوالة صادرة" --json

**والكتابةُ في مسارٍ مُهمَل**: الدفترُ بياناتٌ مُشتقّةٌ من كشف العميل، ومسارُه الافتراضيّ
(`data/ledgers/<اسم>.sqlite`) مُهمَلٌ في `.gitignore` ويحرسه `publish_guard` بامتداد `.sqlite`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from statement_qa import ledger as L            # noqa: E402

REPO = Path(__file__).resolve().parents[1]      # **الجذرُ يُشتقّ من موضع الملفّ لا من الـCWD:** الضابطُ
                                                # الذي أمسك هذا (مقعدُ الترتيب P3) بنى من CWD آخر
                                                # فأنشأ الدفترَ **خارج الشجرة** حيث لا يُهمَل ولا يُحرس.


def _build(args) -> int:
    import to_xlsx                              # noqa: PLC0415  (يُستورد عند الحاجة فقط: يحتاج polars)

    run = Path(args.run).expanduser()
    rows, _report, per_page, _flags = to_xlsx.load(run)
    if not rows:
        print(f"لا صفوف في {run}/results — هل المسار صحيح؟", file=sys.stderr)
        return 2
    db = Path(args.db).expanduser() if args.db else default_db(run)
    conn = L.open_ledger(db)                    # البناءُ يُنشئ (create=True)
    try:
        written = L.ingest(conn, rows, per_page)
        cov = L.answer(conn, "coverage")
    finally:
        conn.close()
    print(f"الدفتر: {db}")
    print(f"  صفوفٌ مُدخَلة: {written} · صفحات: {cov['pages']} · بلا إثبات: {cov['unproven']}")
    print(f"  أحكامُ الصفحات: {cov['page_verdicts']}")
    print("  (لم يُكتب شيءٌ في مجلّد المصدر: القراءةُ وحدَها)")
    return 0


def default_db(run: Path) -> Path:
    """المسارُ الافتراضيّ: `<جذرُ المستودع>/data/ledgers/<اسم التشغيل>.sqlite` — مُهمَلٌ ومحروس.

    **مثبَّتٌ بالجذر لا بالـCWD** (مقعدُ الترتيب P3 · مُثبت): كان نسبيًّا، فيُنشئ الدفترَ حيث تُشغَّل
    الأداة — خارجَ الشجرة عند التشغيل من غير الجذر، فلا يشملُه الإهمالُ ولا حارسُ النشر.
    """
    return REPO / Path(*L.LEDGER_SUBDIR) / f"{Path(run).name}.sqlite"


def _ask(args) -> int:
    try:
        conn = L.read_ledger(Path(args.db).expanduser())   # للقراءة: قاعدةٌ غائبةٌ تُعلَن ولا تُخترع
    except L.LedgerUnavailable as e:
        # **والخطأُ المسمّى يُعرَض مسمًّى** (مقعدُ الترتيب P3 · مُثبت): كان `LedgerUnavailable` يخرج
        # traceback خامًا من واجهةٍ تشترط على نفسها «خطأٌ مسمّى لا انهيار».
        print(f"تعذّر فتحُ الدفتر — {e}", file=sys.stderr)
        return 2
    try:
        out = L.answer(conn, args.intent, pg=args.pg, q=args.q, limit=args.limit)
    except ValueError as e:                     # قصدٌ غيرُ مُعدَّد ⇒ خطأٌ مسمًّى لا استعلامٌ عرضيّ
        print(f"رفض: {e}", file=sys.stderr)
        return 2
    finally:
        conn.close()
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0
    if out["intent"] == "totals":
        print(f"المجموعُ المدين:  {out['debit']}  ({out['debit_rows']} صفًّا)")
        print(f"المجموعُ الدائن: {out['credit']}  ({out['credit_rows']} صفًّا)")
    elif out["intent"] == "coverage":
        print(f"صفوف: {out['rows']} · صفحات: {out['pages']} · بلا إثبات: {out['unproven']}")
        print(f"أحكام: {out['page_verdicts']}")
    elif out["intent"] == "unproven":
        print(f"بلا إثبات: {out['count']}")
        for r in out["rows"]:
            print(f"  ص{r['pg']} · {r['row_no']} · {r['desc'][:60]} · {r['amount']}")
    elif out["intent"] == "search":
        print(f"«{out['query']}» ⇒ {len(out['rows'])} صفًّا")
        for r in out["rows"]:
            print(f"  ص{r['pg']} · {r['desc'][:60]}")
    elif out["intent"] == "pages":
        for r in out["pages"]:
            print(f"  ص{r['pg']}: {r['verdict']} · صفوف {r['rows_count']}")
    else:
        for r in out["qa"]:
            print(f"  [{r['asked_at']}] {r['question'][:70]} ⇒ {(r['answer'] or '—')[:40]} · أدلّة {r['evidence']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="دفترُ الكشوف (أ-٣): بناءٌ وسؤالٌ بأقصدٍ ثابتة")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="ابنِ دفترًا من نتائج تشغيل")
    b.add_argument("--run", required=True, help="مجلّدُ التشغيل (فيه results/ وslice_report.json)")
    b.add_argument("--db", default=None, help="مسارُ الدفتر (افتراضًا data/ledgers/<اسم>.sqlite)")
    b.set_defaults(fn=_build)

    a = sub.add_parser("ask", help="اسأل الدفترَ بقصدٍ من قائمةٍ مغلقة")
    a.add_argument("--db", required=True)
    a.add_argument("intent", choices=L.INTENTS, help="الأقصدُ المسموحُ بها (لا استعلامَ حرّ)")
    a.add_argument("--pg", type=int, default=None, help="للقصد pages: صفحةٌ بعينها")
    a.add_argument("--q", default=None, help="للقصد search: نصُّ البحث (يُعقَّم داخليًّا)")
    a.add_argument("--limit", type=int, default=20)
    a.add_argument("--json", action="store_true")
    a.set_defaults(fn=_ask)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
