#!/usr/bin/env python3
"""**مولِّدُ الأرضيّة الصناعيّة** — صفحاتٌ مُصنَّعةٌ صغيرةٌ تُلتزم مع المستودع.

## لماذا وُلد (القرارُ الثالث من تسليم مراجعة ٤٧)

سمومُ الختم كانت تُقاس على `data/local_sample` **المحجوبةِ عن git** (`.gitignore`) ⇒ في أيّ استنساخ
أو CI تُتخطّى الاختباراتُ كلُّها `skip`، **فالرجوعُ عن الإصلاح يمرّ أخضرَ في الآلة الوحيدة التي لا
تملك الأدلّة**. وهذه الأرضيّةُ الصناعيّةُ تُغلق ذلك: بياناتٌ **ليست من كشفٍ حقيقيّ** (لا مبلغَ حقيقيًّا
ولا نصًّا مصرفيًّا)، صغيرةٌ (أقلُّ من ٤ كيلوبايت)، ومُشتقّةٌ من **الشكل المُعلن للكوربوس** لا من نسخةٍ
مُختصرةٍ تُنحرف.

## القاعدة (القاعدة ١٣)

الأرقامُ هنا **مصنوعة**: ١٫٠٠ · ٢٫٠٠ · ٠٫٥٠ — لا قيمةَ من كشف. والنصُّ: «قيدٌ تجريبيّ» ونحوُه.
والتشغيل: `python3 tests/fixtures/make_mini_corpus.py` (يكتب تحت `mini_corpus/`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "mini_corpus"
RESULTS = OUT / "results"

#: نتيجةُ القارئ (الهويةُ تظهر في التقرير) — صناعيّةٌ ومُعلَنة
READER_STAMP = {"reader_stamp": {"prompt_version": "الصناعيّة-١", "model": "بلا نداء — بياناتٌ مُصنَّعة"}}
IDENTITY = "0f0f0f0f0f0f0f0f"


def _row(i: int, date: str, movement: str, balance: str, desc: str) -> dict:
    """صفٌّ بالشكل المُعلن للكوربوس (لا نسخةَ مُختصرة: المفاتيحُ التي يقرأها الإسقاطُ نفسُه)."""
    return {"row_no": i, "date": date, "date_source": "cell", "col": None, "printed_col": None,
            "movement": movement, "balance": balance, "desc": desc,
            "raw_movement": movement, "raw_balance": balance}


def _page(pg: int, first_balance: str, rows: list[dict], debits: str, credits: str, close: str) -> dict:
    """صفحةٌ بإطارٍ مطبوع مطابقٍ لحركاتها (فتصلح للقياس الماليّ أيضاً)."""
    return {"pg": pg, "page_no": pg, "ms_read": 12.5, "ms_footer": 3.25,
            "footer": {"debits": debits, "credits": credits, "balance": close,
                       "raw": {"debits": debits, "credits": credits, "balance": close}},
            "raw_rows": rows, "usage": {}, "date_backfill": {},
            "first_balance": first_balance}


#: نصٌّ **أطولُ من ١٢٠ خانةً** — فهو يمسك الثقبَ الذي كان يقطع النصَّ صمتاً (بوّابةُ التسليم)
LONG_TAIL = ("حوالةٌ واردةٌ من بنكٍ آخرَ — قيدٌ تجريبيٌّ فقط لا حملَ ماليّاً، والذيلُ هو المقصودُ "
             "بالفحص عند الخانة المئة والعشرين وما بعدها")

PAGES = [
    _page(2, "10.00", [
        _row(1, "2026/01/01", "1.00", "11.00", "قيدٌ تجريبيّ ١"),
        _row(2, "2026/01/02", "2.00", "13.00", LONG_TAIL),
        _row(3, "2026/01/03", "", "13.00", "رصيدٌ مُدوَّر (صفٌّ بلا حركة)"),
        _row(4, "2026/01/04", "3.00", "10.00", "قيدٌ تجريبيّ ٢"),
    ], "1.00", "5.00", "10.00"),
    _page(3, "10.00", [
        _row(1, "2026/01/05", "4.00", "14.00", "قيدٌ تجريبيّ ٣"),
        _row(2, "2026/01/06", "5.00", "19.00", "قيدٌ تجريبيّ ٤"),
    ], "4.00", "5.00", "19.00"),
    _page(4, "19.00", [
        _row(1, "2026/01/07", "6.00", "25.00", "قيدٌ تجريبيّ ٥"),
        _row(2, "2026/01/08", "7.00", "18.00", "قيدٌ تجريبيّ ٦"),
    ], "6.00", "7.00", "18.00"),
]


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="يولّد الأرضيّةَ الصناعيّة (وبلا حجّة: موضعَها المُلتزم)")
    ap.add_argument("--out", type=Path, default=HERE,
                    help="أين تُكتب `mini_corpus/` (والافتراضُ: بجانب هذا الملفّ — للالتزام)")
    args = ap.parse_args(argv)
    out = (args.out / "mini_corpus") if args.out != HERE else OUT
    results = out / "results"
    results.mkdir(parents=True, exist_ok=True)
    for p in PAGES:
        (results / f"pg-{p['pg']:03d}.json").write_text(
            json.dumps(p, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "slice_report.json").write_text(json.dumps(
        {**READER_STAMP, "corpus_provenance": {"doc_id": IDENTITY},
         "pages": len(PAGES), "synthetic": True,
         "note": ("أرضيّةٌ صناعيّةٌ صغيرةٌ مُلتزمة: لا مبلغَ حقيقيًّا ولا نصَّ كشفٍ (القاعدة ١٣) — "
                  "وُلدت لتُعضّ سمومُ الختم في أيّ استنساخ؛ مُشتقّةٌ بيد المستودع نفسه")},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"كُتبت {len(PAGES)} صفحاتٍ صناعيّةٍ في {results}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
