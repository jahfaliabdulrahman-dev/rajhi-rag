#!/usr/bin/env python3
"""**سمُّ كلِّ بوابة** — بند ٧ من عُرف الدمج (§الأدب): «لكلِّ بوابةٍ سمٌّ يُثبت أنها تَعَضّ».

يُشغَّل: `.venv/bin/python tools/guard_bite_sweep.py` · والخروجُ 1 إن مرّت بوّابةٌ بلا سمّ.
**ووجودُه في المستودع مقصود** (بند ٦ من العُرف: كلُّ ما يُتحقَّق منه ممثَّلٌ في المستودع): قياسٌ لا يُعاد إنتاجُه من المستودع ليس دليلًا للمدقّق.

الطريقةُ: لكل ضابطٍ نُفسد **السببَ الوحيد** الذي وُجد له، ونُشغّل الضابطَ وحده.
- **السليم** = الضابطُ المقصود **يسقط** ⇒ البوابةُ تَعَضّ (ليست زينة).
- **العطب** = الضابطُ يبقى يمرّ ⇒ دعوى حمايةٍ كاذبة (وهذا ما نُريد أن نكتشفه، لا أن نُخفيه).

والتغطيةُ هنا هي **حصيلةُ جولة مراجعة ٥٢ وإصلاحِ إسقاطاتها** (١٢ بوابة): R52-1 · R52-2 (ثلاثة أوجه) ·
R52-3 · R52-4 · R52-5 (وجهان) · F6 · ومعيارُ الحالة · وسلوكُ سطر الأوامر.
ولا يُلمس الملفُّ الأصليّ: نسخةٌ احتياطيّة تُعاد في `finally` — والنتيجةُ تُقاس بمخرَج pytest لا بالنوايا.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent   # الجذرُ من الملفّ لا من مسارٍ مكتوب
PY = str(ROOT / ".venv/bin/python")
EQ = ROOT / "tools/eval_questions.py"
SPEND = ROOT / "tools/spend.py"
STAMP = ROOT / "tools/eval_stamp.py"
RS = ROOT / "tools/render_state.py"
RENAMES = ROOT / "handoff/RENAMES.md"
INTRUDER = ROOT / "handoff/claude/20260924-9999-REPORT-to-claude-poison.md"
PROOF_T = "tests/test_eval_proof_rows.py"

CASES = [
    ("م١ · الموضعُ خارج النطاق يُرفض (R52-2)", EQ,
     '    stray = sorted({p for p in (pr.get("pages") or []) if p not in scope})\n'
     '    if stray:\n'
     '        return f"موضعُ إثباتٍ خارج نطاق الفحص: {stray[:5]} من {len(scope)} صفحة"',
     '    stray = []',
     f"{PROOF_T}::test_a_locus_outside_the_scan_is_refused"),

    ("م٢ · لا مطابقةَ تضيع بصمت (R52-2)", EQ,
     '        covered = len(pr.get("rows") or []) + len(pr.get("unmapped") or [])\n'
     '        if covered != safe["hits"]:',
     '        covered = safe["hits"]\n'
     '        if False:',
     f"{PROOF_T}::test_a_silent_loss_in_a_matching_locus_is_refused"),

    ("م٣ · الموضعُ = الصفوفُ المطابِقة لا كلُّ صفوف الصفحة (R52-2)", EQ,
     "    return sorted(set(ids)), unmapped",
     '    return _ids_for_pages(rows, {p for p, _ in hits}), []',
     f"{PROOF_T}::test_the_matching_locus_is_the_matching_rows_themselves"),

    # **الجديد في جولة الإصلاح** (مقعدا المعايير والبنية): الفهرسُ ليس هويّة
    ("م٤ · هويّةُ الصفّ المطابِق (لا الفهرس) — R52-2", EQ,
     '                got = str((rows[chain[i] - 1] or {}).get("desc") or "")\n'
     '                if pattern and pattern not in got:',
     '                got = ""\n'
     '                if False:',
     f"{PROOF_T}::test_a_shifted_match_is_declared_not_cited"),

    ("م٥ · سببُ عدم التموضع يُقاس لا يُفترض", EQ,
     '            why = ("الصفُّ المطابِق بلا رصيدٍ مطبوع ⇒ يخرج من السلسلة (build_rows يُسقط رصيدَه None)"\n'
     '                   if i < len(src) and num(src[i].get("balance")) is None\n'
     '                   else "المطابقةُ عند فهرسٍ لا صفَّ له في السلسلة (فهرسُ الصفحة أطولُ من صفوفها في السلسلة)")',
     '            why = "الصفُّ المطابِق بلا رصيدٍ مطبوع ⇒ يخرج من السلسلة (build_rows يُسقط رصيدَه None)"',
     f"{PROOF_T}::test_the_unmapped_reason_is_measured_not_presumed"),

    ("م٦ · الكاتبُ يحمل الأثرَ كاملًا (R52-3)", EQ,
     '        trace = list(getattr(res, "used_row_nos", None) or []) if res else []',
     '        trace = list(getattr(res, "used_row_nos", None) or []) if res else []\n'
     '        trace = trace[: 40]',
     "tests/test_eval_cap_loop.py::test_the_stored_record_carries_the_whole_trace_and_its_length"),

    # **الوحدةُ المشتركة** (R52-4 · مقعدُ البنية F7): العائمُ الخامّ يعود في المواضع الخمسة
    ("م٧ · المقارنةُ الماليّةُ بالسنتات (R52-4/F7)", SPEND,
     "    return cents(spent) > cents(cap)",
     "    return float(spent) > float(cap)",
     "tests/test_spend_unit.py::test_the_float_trap_that_started_this"),

    # **هويّةُ الأثر** (مقعدُ البنية F6): وجودُ الطول كان يُقرأ «نظيفًا» بلا مقارنة
    ("م٨ · هويّةُ طول الأثر تُقاس لا تُصدَّق (F6)", STAMP,
     "        return int(tl) != len(rec.get(\"used_row_nos\") or [])",
     "        return False",
     "tests/test_eval_rescore_controls.py::test_a_record_whose_declared_length_disagrees_with_its_trace_is_suspect"),

    ("م٩ · الخاسرُ في تعارض الحالة يبقى مُعلَّقًا (R52-1)", RS,
     '        lines.extend(LOSER_PREFIX + x for x in lose              # حقولُ الخاسر: مُعلَّقةٌ لا محذوفة\n'
     '                     if x.strip() and not LOG.match(x))',
     '        pass',
     "tests/test_state_union.py::test_the_winner_is_the_newest_and_the_loser_is_marked"),

    # **سلوكُ سطر الأوامر** (مقعدُ المعايير): تعارضٌ مفتوح ⇒ حكمٌ مُسمّى لا أثرُ بايثون
    ("م١٠ · تعارضٌ مفتوح ⇒ رمزُ خروجٍ مميّز (لا أثر)", RS,
     "    except ValueError as exc:",
     "    except ValueError as e:\n        raise",
     "tests/test_state_union.py::test_an_unclosed_conflict_is_a_named_verdict_not_a_traceback"),

    # **معيارُ الفائز** (مقعدُ البنية): يُقرأ من السطر المحكوم لا من أيِّ سطر
    ("م١١ · الفائزُ يُحكَم بسطر الحالة لا بسطر السجلّ", RS,
     "    for x in lines:\n        if x.startswith(\"status:\"):\n            d = ISO_DATE.search(x)",
     "    for x in lines:\n        if True:\n            d = ISO_DATE.search(x)",
     "tests/test_state_union.py::test_a_date_on_a_log_line_does_not_decide"),
]


def _run(test: str) -> int:
    r = subprocess.run([PY, "-m", "pytest", "-q", "-x", test], cwd=ROOT, capture_output=True, text=True)
    return r.returncode


def _report(name: str, ok: bool, bad: int) -> int:
    print(f"{name:52s} | {'مُطبَّق':6s} | {'سقط':6s} | "
          f"{'✓ البوابةُ تَعَضّ' if ok else '✗ البوابةُ تمرّ — دعوى كاذبة'}")
    return bad + (0 if ok else 1)


def main() -> int:
    print(f"{'البوابة':52s} | {'السمّ':6s} | {'الضابط':6s} | النتيجة")
    print("-" * 92)
    bad = 0
    total = 0

    for name, path, old, new, test in CASES:
        bak = path.with_suffix(path.suffix + ".bak_bite")
        shutil.copy2(path, bak)
        try:
            src = path.read_text(encoding="utf-8")
            assert old in src, f"نصُّ السمّ لم يُطابق في {path.name} — القياسُ لا يُكمَل بالنوايا"
            path.write_text(src.replace(old, new, 1), encoding="utf-8")
            rc = _run(test)
        finally:
            shutil.copy2(bak, path)
            bak.unlink()
        total += 1
        bad = _report(name, rc != 0, bad)

    # م١٢أ: ملفُّ منفّذٍ **غيرِ مُعلَن** في صندوق المدقّق
    INTRUDER.write_text("# س\n", encoding="utf-8")
    try:
        rc = _run("tests/test_mailbox_ownership.py::test_no_implementer_report_lives_in_the_auditors_box_unless_declared")
    finally:
        INTRUDER.unlink()
    total += 1
    bad = _report("م١٢أ · صندوقُ المدقّق بلا تقرير منفّذ (R52-5)", rc != 0, bad)

    # م١٢ب: نقلٌ غيرُ مُعلَن (بإخفاء سجلّ الإعلان — والحركةُ قائمةٌ في المسرَح فعلًا)
    hidden = RENAMES.with_suffix(".md.hidden")
    RENAMES.rename(hidden)
    try:
        rc = _run("tests/test_mailbox_ownership.py::test_every_move_or_delete_under_handoff_is_declared")
    finally:
        hidden.rename(RENAMES)
    total += 1
    bad = _report("م١٢ب · النقلُ غيرُ المُعلَن يُرفض (R52-5)", rc != 0, bad)

    # م١٢ج: استثناءٌ متقادم يبقى في القائمة بعد زوال سببِه ⇒ يُكشَف
    intruder2 = ROOT / "handoff/claude/20260924-9999-REPORT-poison-undeclared.md"
    intruder2.write_text("# س\n", encoding="utf-8")
    try:
        rc = _run("tests/test_mailbox_ownership.py::test_no_implementer_report_lives_in_the_auditors_box_unless_declared")
    finally:
        intruder2.unlink()
    total += 1
    bad = _report("م١٢ج · الدخيلُ غيرُ المُعلَن يُكشَف — لا قائمةَ صمّاء", rc != 0, bad)

    print("-" * 92)
    print(f"الحصيلة: {total - bad}/{total} بوّاباتٍ تعضّ." + ("" if not bad else "  ⛔ دعاوى بلا حماية!"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
