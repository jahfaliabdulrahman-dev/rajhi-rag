#!/usr/bin/env python3
"""تعميم قانون التواريخ على الكاش كلّه — بلا نموذج وبلا كلفة.

لماذا هذا الملف موجود
---------------------
صفحةٌ قُرئت قبل أن يكتسب القارئ قانون التواريخ تبقى بلا تواريخ إلى الأبد: الكاش
لا يُعاد قراءته (كل صفحة قُرئت لا تُقرأ ثانية)، والدفع لا يتكرّر. فنُطبّق القانون
على الكاش نفسه: تاريخ من خانة الورق، فإن فرغت فمن نصّ السطر **نفسه**، مع إعلان
المصدر في كل صفّ — لا تعبئة صامتة، ولا أخذ تاريخ من صفّ آخر.

    python3 tools/backfill_dates.py --run <dir>            # جرد فقط (بلا كتابة)
    python3 tools/backfill_dates.py --run <dir> --apply    # يكتب ويُعلن المصدر
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))

from statement_qa.row_dates import resolve  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="مجلد التشغيلة (فيه results/)")
    ap.add_argument("--apply", action="store_true", help="اكتب النتيجة في الكاش")
    args = ap.parse_args()

    run = Path(args.run)
    files = sorted((run / "results").glob("pg-*.json"),
                   key=lambda p: int(p.stem.split("-")[1]))
    if not files:
        print("لا كاش في", run, file=sys.stderr)
        return 1

    counts: Counter = Counter()
    mismatches: list[tuple[int, str]] = []
    filled = 0
    for path in files:
        page = int(path.stem.split("-")[1])
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("raw_rows") or []
        changed = False
        for row in rows:
            verdict = resolve(row)
            counts[verdict["date_source"]] += 1
            if verdict["date_text_mismatch"]:
                mismatches.append((page, str(row.get("desc") or "")[:40]))
            if verdict["date_source"] == "text" and \
                    str(row.get("date") or "").strip() in ("", "None", "null"):
                if args.apply:
                    row["date"] = verdict["date"]
                    row["date_source"] = "text"
                    changed = True
                filled += 1
            elif args.apply and verdict["date_source"] in ("cell", "not_a_movement"):
                if row.get("date_source") != verdict["date_source"]:
                    row["date_source"] = verdict["date_source"]
                    changed = True
        if changed and args.apply:
            data["date_backfill"] = "row_dates.resolve — تاريخ من نصّ السطر حيث فرغت الخانة"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                            encoding="utf-8")

    print(f"صفحات: {len(files)} · صفوف: {sum(counts.values())}")
    for k in ("cell", "text", "not_a_movement", "missing"):
        labels = {"cell": "تاريخ من خانة الورق", "text": "تاريخ من نصّ السطر نفسه",
                  "not_a_movement": "سطر ليس حركة (رصيد افتتاحي/ملخّص)",
                  "missing": "بلا تاريخ في الخانة ولا في النصّ"}
        print(f"  {labels[k]}: {counts[k]}")
    print(f"قابل للتعبئة الآن: {filled}"
          + (" — كُتب ✓" if args.apply else " — لم يُكتب (أضف --apply)"))
    print(f"تنازع بين خانة التاريخ ونصّ السطر: {len(mismatches)}")
    for page, desc in mismatches[:5]:
        print(f"   ص{page}: {desc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
