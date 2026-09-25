#!/usr/bin/env python3
"""Keep public numbers DERIVED, never remembered (audit P2-5).

The public documents drifted from their own evidence four separate times: the
README claimed 613 documented pages while the measured number was 621; the QA
checklist claimed 78 tests while 113 existed; PLAN carried an old row count, an
old anchor count and an old cost. Every one of those was caught by a human
reading two files at once — a mechanism that fails silently the moment nobody
feels like reading.

This derives the numbers from the report the run itself wrote (plus the live
test count) and asserts the documents contain them. Local, no API, no cost.

    python3 tools/render_claims.py            # show what it derives and checks
    python3 tools/render_claims.py --check    # exit 1 on any drift
    python3 tools/render_claims.py --write    # refresh docs/claims.json (the
                                              # snapshot CI checks against when
                                              # the local cache is absent)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
REPORT = PROJ / "data" / "local_sample" / "slice_629p" / "slice_report.json"
RESULTS = PROJ / "data" / "local_sample" / "slice_629p" / "results"
# The CI-visible snapshot. It MUST have a writer: a snapshot nobody regenerates
# drifts silently, and then CI compares a fresh document against a stale copy
# and calls the fresh document the drift (this happened with the test count).
SNAPSHOT = PROJ / "docs" / "claims.json"


def _test_count() -> int | None:
    """عدُّ الاختبارات — ببيئةٍ نظيفة.

    عطلٌ مُعلن كان يُعطي أرقاماً خاطئة (227 · 232 · 233) حين يُستدعى من عمليةٍ
    أخرى: المتغيّرات الموروثة (`PYTHONPATH` خصوصاً) تُغيّر ما يُجمَع. **الوثائق
    ليست البيئة** — فالقياس يُنزع من بيئة الاستدعاء قبل أن يُشغَّل.
    """
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONPATH", "PYTHONHOME", "PYTEST_ADDOPTS")}
    out = subprocess.run([sys.executable, "-m", "pytest", "tests/",
                          "--collect-only", "-q"],
                         cwd=PROJ, capture_output=True, text=True, env=env)
    for line in reversed(out.stdout.splitlines()):
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and "test" in parts[1]:
            return int(parts[0])
    return None


def _gate3_price_cap() -> int | None:
    """**سقفُ ثمن الإفراج يُشتقّ من كائنه لا من النثر** (review-60 · R60-1).

    الرقمُ ١٣٣ كان يُكتب بيدٍ في الوثائق — وقد سُحب مرّةً إلى «١٠٠» لأن البوابةَ كانت تقيس مجتمعًا
    ناقصًا. فالآن يُشتقّ من `GATE3_DECISION` (مصدرٌ واحد: كائنُ القرار في `tools/eval_pack.py`)
    ويُقابَل في موضعين معلَنين، فمن غيّر السقفَ في الشيفرة يجد الوثائقَ تحمرّ.
    """
    try:
        sys.path.insert(0, str(PROJ))
        from tools.eval_pack import GATE3_DECISION                      # noqa: PLC0415
        return int(GATE3_DECISION["price_cap_pages"])
    except Exception:                                                   # noqa: BLE001
        return None


def derive() -> dict | None:
    if not REPORT.exists():
        return None
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    facts = {}
    if RESULTS.exists():
        sys.path.insert(0, str(PROJ / "tools"))
        import scale_slice  # noqa: PLC0415

        facts = scale_slice._cache_facts(RESULTS)
    f = rep["footer"]
    return {
        # كل رقم معلن مربوطٌ بالزوج الذي أنتجه (FMEA FM-1.4): نموذجٌ وتلقينة.
        # فحين يُعاد القياس بقارئٍ آخر، يُعرف الرقم القديم بمن قُرئ.
        "reader_stamp": rep.get("reader_stamp") or "غير مختم",
        "corpus_declaration": (rep.get("corpus_provenance") or {}).get("declaration"),
        "pages": rep["slice"]["pages_done"],
        "rows": rep["totals"]["rows"],
        "clean": rep["totals"]["clean"],
        "clean_pct": f"{rep['totals']['clean_ratio']:.1%}",
        "ok": f["ok"], "mismatch": f["mismatch"], "gap": f["gap"],
        "absent": f["absent"], "unchecked": f["unchecked"],
        "documented_ratio": f"{f['ok']}/{rep['slice']['pages_done']}",
        "clean_ratio": (f"{rep['totals']['clean']}/{rep['totals']['rows']}"),
        "recoveries": len(facts.get("recoveries", [])),
        "rereads": len(facts.get("rereads", [])),
        "arbitrations": len(facts.get("arbitrations", [])),
        "median_page_s": facts.get("median_page_s"),
        "tests": _test_count(),
        # **ومصدرٌ ثالثٌ مُعلَن**: كائنُ قرار البوابة (٣) — يُشتقّ منه سقفُ الثمن ويُقابَل في الوثائق.
        "gate3_price_cap_pages": _gate3_price_cap(),
    }


def claims(d: dict) -> list[tuple[str, str, str]]:
    """(file, must-contain, label) — the literal a reader will see."""
    return [
        ("README.md", d["documented_ratio"], "نسبة الصفحات الموثّقة"),
        ("README.md", d["clean_ratio"], "نظافة السلسلة"),
        ("README.md", d["clean_pct"], "نسبة النظافة المئوية"),
        ("PLAN.md", d["documented_ratio"], "نسبة الصفحات الموثّقة"),
        ("PLAN.md", d["clean_ratio"], "نظافة السلسلة"),
        ("PLAN.md", f"{d['recoveries']} مرساة", "عدد المراسي المُستدركة"),
        ("PLAN.md", f"{d['rereads']} إعادة قراءة", "عدد إعادات القراءة"),
        ("docs/QA_CHECKLIST.md", f"حالياً {d['tests']}", "عدد الاختبارات"),
        # The ABOUT screen said «about 1.6% of 629 pages» long after the project
        # accounted for every page: the number a stranger reads first had no
        # guard at all (external audit).
        ("app.py", f"{d['ok']} صفحة", "الصفحات المطابقة بإطارها (شاشة ABOUT)"),
        # **وسقفُ ثمن الإفراج يُقابَل في موضعين** (review-60 · R60-1): الرقمُ ١٣٣ كان يُكتب بيدٍ،
        # فسُحب مرّةً إلى «١٠٠» لمّا قاست البوابةُ مجتمعًا ناقصًا. والصيغةُ تحمل الرقمَ **معناه**
        # (سقفُ ثمنِ الإفراج) فلا يُنسَخ رقمٌ آخر في مكانه؛ والمصدرُ كائنُ القرار لا نصّ.
        ("docs/EVAL_PACK.md", f"سقفُ ثمنِ الإفراج {d.get('gate3_price_cap_pages')} صفحة",
         "سقفُ ثمن الإفراج (البوابة ٣)"),
        ("docs/GATES.md", f"سقفُ ثمنِ الإفراج {d.get('gate3_price_cap_pages')} صفحة",
         "سقفُ ثمن الإفراج (سجلّ البوابات)"),
    ]


def check(d: dict) -> list[tuple[str, str, str]]:
    """-> [(file, missing_claim, label)] for every drift."""
    drifts = []
    for rel, needle, label in claims(d):
        path = PROJ / rel
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        if needle not in text:
            drifts.append((rel, needle, label))
    return drifts


def snapshot_drift(d: dict) -> list[tuple[str, object, object]]:
    """-> [(key, في اللقطة, في الاشتقاق)] — **البوّابةُ التي كانت عمياء**.

    كان `check()` يقابل الوثائقَ بالاشتقاق الحيّ **فقط**، ولا يقرأ اللقطةَ الملتزمة التي يقرأها CI ⇒
    لقطةٌ متقادمة (٥٩٠ مقابل ٦٠٢) تمرّ محليًّا وتسقط في نسخةٍ نظيفة. اللقطةُ الآن **شاهدٌ يُقابَل** لا حجرٌ
    يُوثق به.
    """
    if not SNAPSHOT.exists():
        return [("<لقطة>", "غائبة", "مطلوبة")]
    try:
        old = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    except Exception as e:                                    # noqa: BLE001
        return [("<لقطة>", f"غيرُ مقروءة: {type(e).__name__}", "مطلوبة")]
    return [(k, old.get(k), v) for k, v in d.items() if old.get(k) != v]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any public document drifts from the report")
    ap.add_argument("--write", action="store_true",
                    help="refresh docs/claims.json from this derivation")
    args = ap.parse_args()
    d = derive()
    if d is None:
        # **بلا تقريرٍ لا يُصمت** (مراجعة ٥٠ · مقعدا Standards وSpec): كان الخروجُ هنا يسبق كلّ مقابلة ⇒
        # خطوةُ CI المسمّاة «اللقطة» كانت تقابل **لا شيء** (rc=0 ولقطةٌ مسمومة). الآن تُقابَل **اللقطةُ
        # الملتزمةُ بالوثائق** — وهو ما يفعله `tests/test_public_claims.py` في غياب الكاش — فيحمرّ على CI.
        if not SNAPSHOT.exists():
            print(f"لا تقرير مقيس هنا ({REPORT}) ولا لقطةٌ ملتزمة — لا شيء يُحرس.")
            sys.exit(0)
        snapdoc = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        sdrifts = check(snapdoc)
        if sdrifts:
            print("⚠ الوثائقُ تخالف لقطتها الملتزمة:")
            for rel, needle, label in sdrifts:
                print(f"  {rel}: تفتقد {needle!r}  ({label})")
            sys.exit(1)
        print("الحكم: الوثائقُ توافق لقطتها الملتزمة (لا تقريرٌ حيّ هنا).")
        sys.exit(0)
    print("[claims] الأرقام المشتقّة من تقرير التشغيل:")
    for k, v in d.items():
        print(f"  {k}: {v}")
    if args.write:
        SNAPSHOT.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
        print(f"\nكُتبت اللقطة: {SNAPSHOT.relative_to(PROJ)} "
              f"(مشتقّة من التقرير، لا مكتوبة بيد).")
    # **اللقطةُ شاهدٌ يُقابَل** (مراجعة ٥٠ · CI): كانت `check` تقابل الوثائقَ بالاشتقاق الحيّ وحده،
    # فلا ترى لقطةً متقادمة يقرأها CI ⇒ البوّابةُ تمرّ محليًّا وتسقط هناك.
    snap = snapshot_drift(d)
    if snap:
        print("\n⚠ اللقطةُ الملتزمة متقادمة (CI يقرأ اللقطةَ لا الاشتقاقَ الحيّ):")
        for k, o, n in snap:
            print(f"  docs/claims.json: {k}: اللقطة {o!r} ≠ الاشتقاق {n!r} ⇒ `--write`")
        if args.check:
            sys.exit(1)
    drifts = check(d)
    if not drifts:
        print("\nالحكم: كل رقم معلن يطابق مصدره.")
        sys.exit(0)
    print("\n⚠ انزياح بين الوثيقة ومصدرها:")
    for rel, needle, label in drifts:
        print(f"  {rel}: تفتقد {needle!r}  ({label})")
    sys.exit(1 if args.check else 0)


if __name__ == "__main__":
    main()
