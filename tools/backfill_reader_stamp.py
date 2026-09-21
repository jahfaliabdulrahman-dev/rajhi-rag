#!/usr/bin/env python3
"""يُعلن حقيقة هوية القارئ **ودورَ التذييل** لتشغيلةٍ سبقت تسجيلهما.

الـ629 صفحة قُرئت **قبل** أن يُختم القارئ في نقاط الفحص، ولا شيء يقول بأيّ
تلقينةٍ ونموذجٍ قُرئت. وإعادةُ قراءتها لدفع ثمن المعلومة **إتلافٌ لا إصلاح**
(وقرارها للمالك لا للأداة). فالعلاج هنا: أن **يُعلن العدد صراحةً** بدل أن يُسكَت
عنه — «المفتوح يُعلن بعدده لا بوصفه».

    python3 tools/backfill_reader_stamp.py --run data/local_sample/slice_629p
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]


def sha256_16(path: Path) -> str:
    """الوسمُ المعتمد في المشروع: `sha256(file)[:16]` — كما في capture_training وtext_reader."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--model", default=None,
                    help="نموذج القراءة إن كان معلوماً من خارج الكاش (وإلا يُعلن مجهولاً)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--doc", type=Path, default=None,
                    help="ملفُّ أصل الكوربوس — تُشتقّ منه هويةُ المستند. وإن غاب يُعلن مجهولاً")
    args = ap.parse_args()

    run = args.run if args.run.is_absolute() else PROJ / args.run
    report_path = run / "slice_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (report.get("reader_stamp") and report.get("footer_role")
            and (report.get("corpus_provenance") or {}).get("doc_id")):
        print("التقرير يحمل ختماً ودوراً وهويةَ مستندٍ بالفعل — لا شيء يُفعل.")
        return
    if not report.get("footer_role"):
        # دورُ التذييل لعقد البنك: قراءةٌ من العقد لا اجتهاد
        prof = json.loads((PROJ / "profiles" / "al-rajhi.json").read_text(encoding="utf-8"))
        report["footer_role"] = ((prof.get("statement") or {}).get("footer") or {}).get("role")
        report["footer_role_note"] = ("أُعلن عند الاستدراك: تشغيلةٌ سبقت وجود الحقل — "
                                      "والدور من عقد البنك نفسه.")

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

    # ── هويةُ المستند: مفتاحُ بوابة التقاطع `(doc_id, page)` ──────────────────
    # الصفحاتُ قُرئت قبل أن يحمل الكوربوس هويةً، فالختمُ **استدراكٌ يُعلن** لا إعادةُ
    # قراءةٍ تدفع الثمن. والوسمُ من الملف نفسه: `sha256(file)[:16]` — العُرفُ القائم
    # في `capture_training.py` و`text_reader.py`، فلا يكون للمشروع وسمان.
    doc = args.doc or (run / "slice_629p.pdf")
    doc = doc if doc.is_absolute() else PROJ / doc
    cp = report["corpus_provenance"]
    if doc.exists():
        cp["doc_id"] = sha256_16(doc)
        cp["doc_file"] = doc.name
        cp["doc_id_method"] = "sha256(file)[:16] — كما في tools/capture_training.py"
        cp["doc_id_note"] = ("ختمُ استدراك: الصفحاتُ قُرئت قبل تسجيل الهوية، والوسمُ من "
                             "الملف نفسه لا من قراءةٍ جديدة.")
    else:
        # لا يُخمَّن وسمٌ بلا ملفّ: يُعلن مجهولاً ويُسمّى المفقود
        cp["doc_id"] = None
        cp["doc_file"] = None
        cp["doc_id_note"] = (f"مجهولٌ: ملفُّ الأصل غير موجود ({doc}) — ولا يُخمَّن "
                             "وسمٌ بلا ملفّ.")
    cp["doc_id_backfilled_at"] = date.today().isoformat()

    print(f"نقاط فحص مختمة: {stamped} · غير مختمة: {unstamped} · "
          f"دور التذييل: {report.get('footer_role')} · doc_id: {cp['doc_id']}")
    if args.dry_run:
        print("(تجربة — لم يُكتب شيء)")
        return
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    try:
        shown = report_path.relative_to(PROJ)   # أقصرُ للعين حين تكون التشغيلة داخل المستودع
    except ValueError:
        shown = report_path                    # وتشغيلةٌ خارج المستودع تُطبع بمسارها الكامل
    print(f"كُتب الإعلان في {shown}")


if __name__ == "__main__":
    main()
