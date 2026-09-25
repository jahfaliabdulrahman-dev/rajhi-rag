"""تدقيقُ الحرّاس — **الدليلُ الحاسمُ أن الحارسَ يسقط عند إعادة حقن العلّة**.

الفكرةُ من حكم المدقّق (review-33 §٢ و§٦/١):

    «ومن لم يُجرَّب سقوطُه لم يُثبت أنه حارس» · و«ضابطٌ يُعيد بناء المنطق ليس ضابطاً —
    إنه نسخةٌ ثانيةٌ من الاعتقاد».

فكلُّ حارسٍ في هذا الجدول يُختبَر بالطريقة الوحيدة التي تُثبت أنه يَعَضّ:

    (١) يُحقَن عطبُ البوابة نصّاً في الكود الحقيقيّ (والحقنُ يُتحقَّق من تطبيقه)،
    (٢) تُشغَّل اختباراتُ الحارس وحدَها،
    (٣) **يجب أن تسقط** — فإن مرّت فالحارسُ ليس حارساً،
    (٤) ويُعاد الملفُّ إلى نصّه الأصليّ **ويُتحقَّق بالبصمة** أن لا أثرَ بقي.

    python3 tools/guard_audit.py            # ينفّذ الجدولَ كلَّه ويطبع الحكم
    python3 tools/guard_audit.py --dry-run  # يتحقّق أن كل حقنٍ يُطبَّق (بلا تشغيل اختبارات)

**ولا يمسّ شيئاً دائماً:** الأصلُ في الذاكرة، والبصمةُ تُقابَل في النهاية.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]

#: كلُّ صفّ: بوابةٌ · ملفُّها · نصُّ الحقن (عطبُها الأصليّ) · الاختباراتُ التي يجب أن تسقط
CASES: list[dict] = [
    {
        "gate": "التقاطع/المجتمع",
        "file": "tools/eval_pack.py",
        "old": '    pack_pages = pack_pages_all          # المجتمعُ: الإحصاء + المديات = 200 (لا 150)',
        "new": '    pack_pages = sorted({p for m in measured for p in m["pages"]})',
        "tests": [
            "tests/test_eval_pack.py::test_the_population_control_calls_the_real_build_and_falls",
            "tests/test_eval_pack.py::test_the_build_runs_the_population_to_the_line_it_prints",
        ],
        "why": "العطبُ الأصليّ: مجتمعُ البوابة المدياتُ وحدَها ⇒ ثمنٌ ناقصٌ بالثلث (100 مقابل 133)",
    },
    {
        "gate": "الإطار التراكميّ",
        "file": "tools/eval_pack.py",
        "old": '        "delta_debit": str(pd_ - sd), "delta_credit": str(pc - sc),',
        "new": '        "delta_debit": str(pd_), "delta_credit": str(pc),', 
        "tests": ["tests/test_eval_pack.py::test_the_cumulative_frame_is_the_gate_not_the_page_sum"],
        "why": "العطبُ الأصليّ: مجموعُ الصفحات بدل دلتا الإطارين ⇒ الإطارُ تراكميّ فأعطى −21300 نظيفةً",
    },
    {
        "gate": "اتجاهُ أوّل حركةٍ في الصفحة",
        "file": "tools/eval_pack.py",
        "old": '            side = "debit" if (prev is None or cur is None or cur < prev) else "credit"',
        "new": '            side = "debit"',
        "tests": ["tests/test_eval_pack.py::test_the_first_row_of_a_page_takes_its_side_from_the_previous_frame"],
        "why": "العطبُ الأصليّ: «مدينٌ افتراضاً» لأوّل حركة ⇒ 8 صفحاتٍ من 50 انزاحت دائن→مدين",
    },
    {
        "gate": "الهوية المجهولة",
        "file": "tools/eval_pack.py",
        "old": "        raise Stopped(",
        "new": "        return 'unknown', []  # الحقن: تمريرُ المجهول بدل الوقوف بالاسم\n    def _never(self):\n        raise Stopped(",
        "tests": ["tests/test_eval_pack.py::test_identity_null_stops_the_build_by_name"],
        "why": "العطبُ الأصليّ: `null` يُمَرَّر إلى `unknown` بدل أن يوقف البناءَ بالاسم",
    },
    {
        "gate": "بصمةُ الإحصاء",
        "file": "tools/eval_pack.py",
        "old": '    fp = _sha16(json.dumps([p["page"] for p in pages]))',
        "new": '    fp = _sha16("[]")',
        "tests": ["tests/test_eval_pack.py::test_the_census_is_a_frozen_list_and_its_fingerprint_moves_with_it"],
        "why": "العطبُ المطارد: بصمةٌ ثابتة ⇒ القائمةُ تتحرّك والبصمةُ لا ⇒ «جمّد القائمة» يصير زينةً",
    },
    {
        "gate": "حارسُ المبالغ · المدى والكشف",
        "file": "tools/amount_guard.py",
        "old": "    return _decimal_printed(tok)",
        "new": "    return False   # الحقن: يُفرغ المدى ⇒ لا يرى الحارسُ مبلغاً أبداً",
        "tests": ["tests/test_amount_guard.py::test_no_location_is_exempt",
                  "tests/test_amount_guard.py::test_scope_is_length_plus_a_decimal_never_the_roundness",
                  "tests/test_amount_guard.py::test_the_repository_itself_carries_no_real_amount_in_tracked_text"],
        "why": ("العطبُ الذي طارده المدقّق: مدىً يقبل الصيغةَ الحديثةَ وحدَها (فمرّت الفاصلةُ العتيقةُ "
                "والإشارةُ المقلوبة). وحين يُفرَغ المدى يصير الفحصُ فارغاً في XPASS اختبارِ الدَّين ⇒ "
                "`xfail(strict=True)` يقلبه سقوطاً"),
    },
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _run_tests(tests: list[str]) -> tuple[int, str]:
    p = subprocess.run([sys.executable, "-m", "pytest", *tests, "-q", "--no-header"],
                       cwd=PROJ, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="تدقيقُ الحرّاس: كلُّ حارسٍ يُجرَّب سقوطُه")
    ap.add_argument("--dry-run", action="store_true", help="يتحقّق أن كل حقنٍ يُطبَّق بلا تشغيل")
    args = ap.parse_args(argv)

    print("═══ تدقيقُ الحرّاس — «ومن لم يُجرَّب سقوطُه لم يُثبت أنه حارس» ═══")
    rows, ok_all = [], True
    for case in CASES:
        path = PROJ / case["file"]
        original = path.read_text(encoding="utf-8")
        base = _sha(path)
        if case["old"] not in original:
            rows.append((case["gate"], "الحقنُ لا يُطبَّق (تغيّر النصّ)", "—", "محجوب"))
            ok_all = False
            continue
        if args.dry_run:
            rows.append((case["gate"], f"يُطبَّق ({len(case['tests'])} اختبار)", "—", "مرّ"))
            continue
        path.write_text(original.replace(case["old"], case["new"], 1), encoding="utf-8")
        try:
            rc, out = _run_tests(case["tests"])
            fell = rc != 0 and ("failed" in out or "error" in out)
            names = [t.split("::")[-1] for t in case["tests"]]
            fell_names = [n for n in names if n in out and "FAILED" in out and n in out.split("FAILED")[1]]
            rows.append((case["gate"], f"{len(case['tests'])} اختبار",
                         ("سقط ✓" + (f" ({', '.join(fell_names[:2])})" if fell_names else "") if fell
                          else "**مرّ — الحارسُ لا يحرس**"),
                         "مُثبت" if fell else "⛔ مكشوف"))
            ok_all &= fell
        finally:
            path.write_text(original, encoding="utf-8")
            after = _sha(path)
            rows.append((case["gate"], "الأثرُ بعد الإعادة", f"{base} == {after}", "نظيف" if base == after else "⛔ أثر"))
            ok_all &= base == after

    width = max(len(r[0]) for r in rows)
    for gate, what, detail, verdict in rows:
        print(f"  {gate:<{width}} · {what:<28} · {detail:<28} · {verdict}")
    print(f"\nالحكم: {'PASS — كلُّ حارسٍ مُجرَّبُ السقوط، ولا أثرَ باقٍ' if ok_all else 'FAIL — حارسٌ لا يحرس أعلاه'}")
    print("  والأمر: python3 tools/guard_audit.py" + (" (dry-run)" if args.dry_run else ""))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
