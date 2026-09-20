#!/usr/bin/env python3
"""يُعلن حقيقة هوية القارئ لتشغيلةٍ سبقت تسجيل الهوية (FMEA FM-1).

الـ629 صفحة قُرئت **قبل** أن يُختم القارئ في نقاط الفحص، ولا شيء يقول بأيّ
تلقينةٍ ونموذجٍ قُرئت. وإعادةُ قراءتها لدفع ثمن المعلومة **إتلافٌ لا إصلاح**
(وقرارها للمالك لا للأداة). فالعلاج هنا: أن **يُعلن العدد صراحةً** بدل أن يُسكَت
عنه — «المفتوح يُعلن بعدده لا بوصفه».

    python3 tools/backfill_reader_stamp.py --run data/local_sample/slice_629p
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--model", default=None,
                    help="نموذج القراءة إن كان معلوماً من خارج الكاش (وإلا يُعلن مجهولاً)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    run = args.run if args.run.is_absolute() else PROJ / args.run
    report_path = run / "slice_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("reader_stamp"):
        print("التقرير يحمل ختماً بالفعل — لا شيء يُفعل.")
        return

    stamped = unstamped = 0
    for f in sorted((run / "results").glob("pg-*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("model") and d.get("prompt_version"):
            stamped += 1
        else:
            unstamped += 1

    report["corpus_provenance"] = {
        "reader": None,
        "legacy_unstamped_pages": unstamped,
        "stamp_conflict_pages": 0,
        "declaration": "غير مختم — قُرئ قبل تسجيل الهوية",
        "note": ("الصفحات قُرئت قبل أن يُختم القارئ في نقطة الفحص، ولا يُعرف من الكاش "
                 "أي تلقينةٍ أنتجتها (والتلقينتان v1/v2 كانتا تُقاسان في هذه الفترة — "
                 "FMEA FM-2). فالإعلان بعددٍ لا يُسكَت عنه، والوزن على المالك في قرار "
                 "إعادة القراءة."),
        "backfilled_at": date.today().isoformat(),
    }
    if args.model:
        report["corpus_provenance"]["model_note"] = f"نموذج القراءة المعلن خارج الكاش: {args.model}"

    print(f"نقاط فحص مختمة: {stamped} · غير مختمة: {unstamped}")
    if args.dry_run:
        print("(تجربة — لم يُكتب شيء)")
        return
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"كُتب الإعلان في {report_path.relative_to(PROJ)}")


if __name__ == "__main__":
    main()
