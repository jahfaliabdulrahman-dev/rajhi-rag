#!/usr/bin/env python3
"""يُعلن حقيقة هوية القارئ **ودورَ التذييل** (وهويةَ المستند) لتشغيلةٍ سبقت تسجيلها.

الـ629 صفحة قُرئت **قبل** أن يُختم القارئ في نقاط الفحص، ولا شيء يقول بأيّ
تلقينةٍ ونموذجٍ قُرئت. وإعادةُ قراءتها لدفع ثمن المعلومة **إتلافٌ لا إصلاح**
(وقرارها للمالك لا للأداة). فالعلاج هنا: أن **يُعلن العدد صراحةً** بدل أن يُسكَت
عنه — «المفتوح يُعلن بعدده لا بوصفه».

**وقاعدةُ عدم التدهور (درسٌ مدفوع الثمن):** كان الحارسُ يشترط `reader_stamp` —
وهو `None` **بحكم التصميم** على هذا الكوربوس، لأن القارئَ مجهولٌ وهو **سببُ وجود
الأداة** ⇒ حارسٌ لا يمكن أن يَحرُس، و**تُمحى هويةٌ مُثبتة وتُستبدل بـ`null` بخروجٍ
ناجح**. فصار المسارُ مغلقاً ثلاثَ طبقات:

  1. **دمجٌ لا استبدال**: `corpus_provenance` تُدمج فيها الحقول، فلا يُمحى تصريحٌ سابق.
  2. **لا تدهور**: هويةٌ مُثبتة لا يستبدلها `null` ولا وسمٌ مخالف إلا بطلبٍ صريح.
  3. **الوقوفُ بالاسم**: تعارضٌ أو ملفٌّ مطلوبٌ غائب ⇒ خروجٌ بخطأ يسمّي السبب.

    python3 tools/backfill_reader_stamp.py --run data/local_sample/slice_629p
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]

DOC_ID_METHOD = "sha256(file)[:16] — كما في tools/capture_training.py"


def sha256_16(path: Path) -> str:
    """الوسمُ المعتمد في المشروع: `sha256(file)[:16]` — كما في capture_training وtext_reader."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def resolve_doc_id(cp: dict, doc: Path, *, explicit: bool = False,
                   replace: bool = False) -> str:
    """هويةُ المستند: تُشتقّ من الملفّ، ولا **تُدهوَر** هويةٌ مُثبتة.

    الحالةُ السابقة جزءٌ من المُدخَل لا خارجٌ عنه: فالدالّةُ تنظر إلى ما هو مُثبت
    قبل أن تكتب، وتُعيد ماذا فعلت (`stamped` · `unchanged` · `kept` · `unknown`).
    """
    previous = cp.get("doc_id")
    today = date.today().isoformat()
    if doc.exists():
        computed = sha256_16(doc)
        if previous and previous != computed and not replace:
            raise SystemExit(
                f"هويةٌ مُثبتة ({previous}) تخالف الملفَّ المعطى ({computed}) في {doc} — "
                "لا يُستبدل وسمٌ بوسمٍ صامتاً: راجع الملفّ، أو مرّر --doc الصحيح، "
                "أو أعلن الإرادة صراحةً بـ--replace-doc-id.")
        if previous == computed:
            # **حقيقةٌ عادت إلى قيمتها الأولى ليست حقيقةً لم تتغيّر:** بعد ذهابٍ وعودة
            # كان `before == after` يُعلن «لا تغيير» على مسارٍ مرّ بمستندين — والسجلُّ
            # وحدَه يفضح ذلك. فالإعلانُ يُقرأ من السجلّ متى وُجد.
            hist = list(cp.get("doc_id_history") or [])
            if hist:
                last = hist[-1]
                cp["doc_id_note"] = (
                    f"مطابقٌ للملفّ المعطى ({computed})، **والسجلُّ يُظهر أنها مرّت بـ"
                    f"{len(hist)} استبدالاً** — آخرُها {last['previous']} → "
                    f"{last['replaced_by']} في {last['at']}. فالرجوعُ إلى القيمة الأولى "
                    "لا يعني أن المسارَ لم يتغيّر.")
                return "unchanged_but_replaced"
            cp["doc_id_note"] = ("الهويةُ مُثبتةٌ سابقاً وتطابق الملفّ المعطى — لا تغيير "
                                 "(الاستدراكُ لا يُعاد).")
            return "unchanged"
        # **البابُ المعلن يُسجّل من عبَر:** استبدالُ هويةٍ مُثبتة يُقيَّد بما استُبدل،
        # بسجلٍّ تراكميّ لا بحقلِ آخرِ استبدالٍ فقط. و`doc_id` مفتاحُ بوابة التقاطع،
        # فحزمةٌ استُبدلت هويتُها تحتها **تمرّ البوابة لأن الطرفين تحرّكا معاً** —
        # وهو صنفُ «الشاهدُ يتحرّك مع المشهود له»، أخطرُ من المحو لأن المحوَ يُرى.
        replaced = bool(previous) and previous != computed
        if replaced:
            cp["doc_id_previous"] = previous
            cp["doc_id_replaced_at"] = today
            cp["doc_id_history"] = list(cp.get("doc_id_history") or []) + [{
                "previous": previous, "replaced_by": computed, "at": today,
                "reason": "استبدالٌ صريح بـ--replace-doc-id (إعلانُ إرادةٍ لا صمت)",
            }]
        cp.update({
            "doc_id": computed,
            "doc_file": doc.name,
            "doc_id_method": DOC_ID_METHOD,
            "doc_id_note": (
                f"ختمٌ صريحٌ باستبدال: من {previous} إلى {computed} في {today} — "
                "الملفُّ المعطى مخالفٌ للوسم السابق، والاستبدالُ بطلبٍ صريح."
                if replaced else
                "ختمُ استدراك: الصفحاتُ قُرئت قبل تسجيل الهوية، والوسمُ من "
                "الملف نفسه لا من قراءةٍ جديدة."),
            "doc_id_backfilled_at": today,
        })
        return "replaced" if replaced else "stamped"
    if explicit:
        raise SystemExit(f"ملفُّ الأصل المعطى غير موجود ({doc}) — لا وسمَ بلا ملفّ.")
    if previous:
        # ⚠️ مسارُ التدهور مغلق: غيابُ ملفّ لا يمحو هويةً مُثبتة
        cp["doc_id_note"] = (f"الهويةُ محفوظةٌ كما هي ({previous}): ملفُّ الأصل غير موجود "
                            "في هذه التشغيلة، ولا يُدهوَر وسمٌ مُثبت بغياب ملفّ.")
        return "kept"
    cp.update({
        "doc_id": None,
        "doc_file": None,
        "doc_id_note": (f"مجهولٌ: ملفُّ الأصل غير موجود ({doc}) — ولا يُخمَّن وسمٌ بلا "
                        "ملفّ (والترقيةُ إلى مُثبت جائزةٌ متى وُجد الملفّ)."),
        "doc_id_backfilled_at": date.today().isoformat(),
    })
    return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--model", default=None,
                    help="نموذج القراءة إن كان معلوماً من خارج الكاش (وإلا يُعلن مجهولاً)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--doc", type=Path, default=None,
                    help="ملفُّ أصل الكوربوس — تُشتقّ منه هويةُ المستند. وإن غاب الملفُّ يُعلن مجهولاً")
    ap.add_argument("--replace-doc-id", action="store_true",
                    help="يستبدل هويةً مُثبتة بهوية ملفٍّ مخالف — إعلانُ إرادةٍ صريح")
    args = ap.parse_args()

    run = args.run if args.run.is_absolute() else PROJ / args.run
    report_path = run / "slice_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    prior = dict(report.get("corpus_provenance") or {})

    # ملفُّ الأصل يُحسم **قبل** الحارس: فوجودُه يفتح بابَ التحقّق لا التخطّي.
    doc = args.doc or (run / "slice_629p.pdf")
    doc = doc if doc.is_absolute() else PROJ / doc

    # الحارسُ على الحقول التي تخصّ هذه الأداة، لا على `reader_stamp` (وهو `None` بحكم
    # التصميم هنا ⇒ حارسٌ لا يمكن أن يَحرُس). ويتخطّى **فقط** حيث لا ملفَّ يُتحقّق منه:
    # فلو تخطّى مع وجود ملفٍّ، لمرّ مستندٌ مخالف بلا كشف.
    if (prior.get("doc_id") and report.get("footer_role") and not doc.exists()
            and not args.replace_doc_id):
        print(f"هويةٌ مُثبتة ({prior['doc_id']}) ودورٌ معلن، وملفُّ الأصل غير موجود في هذه "
              "التشغيلة — لا شيء يُفعل، والهويةُ **لا تُدهوَر** بغياب ملفّ.")
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

    # **دمجٌ لا استبدال**: حقولٌ تُحدَّث وحقولٌ سابقة تبقى، فلا يُمحى تصريحٌ بكتابةٍ جديدة.
    cp = report["corpus_provenance"] = prior
    cp.setdefault("reader", None)
    cp.setdefault("stamp_conflict_pages", 0)
    cp["legacy_unstamped_pages"] = unstamped
    cp["declaration"] = "غير مختم — قُرئ قبل تسجيل الهوية"
    cp["note"] = ("الصفحات قُرئت قبل أن يُختم القارئ في نقطة الفحص، ولا يُعرف من الكاش "
                  "أي تلقينةٍ أنتجتها (والتلقينتان v1/v2 كانتا تُقاسان في هذه الفترة — "
                  "FMEA FM-2). فالإعلان بعددٍ لا يُسكَت عنه، والوزن على المالك في قرار "
                  "إعادة القراءة.")
    cp["backfilled_at"] = date.today().isoformat()
    if args.model:
        cp["model_note"] = f"نموذج القراءة المعلن خارج الكاش: {args.model}"

    # هويةُ المستند: مفتاحُ بوابة التقاطع `(doc_id, page)` — بلا تدهورٍ ولا تخمين
    status = resolve_doc_id(cp, doc, explicit=args.doc is not None,
                            replace=args.replace_doc_id)

    print(f"نقاط فحص مختمة: {stamped} · غير مختمة: {unstamped} · "
          f"دور التذييل: {report.get('footer_role')} · doc_id: {cp['doc_id']} ({status})")
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
