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
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
REPORT = PROJ / "data" / "local_sample" / "slice_629p" / "slice_report.json"
RESULTS = PROJ / "data" / "local_sample" / "slice_629p" / "results"


def _test_count() -> int | None:
    out = subprocess.run([sys.executable, "-m", "pytest", "tests/",
                          "--collect-only", "-q"],
                         cwd=PROJ, capture_output=True, text=True)
    for line in reversed(out.stdout.splitlines()):
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and "test" in parts[1]:
            return int(parts[0])
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any public document drifts from the report")
    args = ap.parse_args()
    d = derive()
    if d is None:
        print(f"لا يوجد تقرير مقيس هنا ({REPORT}) — لا شيء لاشتقاقه. "
              f"على CI هذا طبيعي: الكاش محلي.")
        sys.exit(0)
    print("[claims] الأرقام المشتقّة من تقرير التشغيل:")
    for k, v in d.items():
        print(f"  {k}: {v}")
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
