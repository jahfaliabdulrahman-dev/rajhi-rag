#!/usr/bin/env python3
"""**سمُّ كلِّ بوابة** — بند ٧ من عُرف الدمج (§الأدب): «لكلِّ بوابةٍ سمٌّ يُثبت أنها تَعَضّ».

يُشغَّل: `.venv/bin/python tools/guard_bite_sweep.py` · والخروجُ 1 إن مرّت بوّابةٌ بلا سمّ.
**ووجودُه في المستودع مقصود** (بند ٦ من العُرف: كلُّ ما يُتحقَّق منه ممثَّلٌ في المستودع): قياسٌ لا يُعاد إنتاجُه من المستودع ليس دليلًا للمدقّق.

الطريقةُ: لكل ضابطٍ نُفسد **السببَ الوحيد** الذي وُجد له، ونُشغّل الضابطَ وحده.
- **السليم** = الضابطُ المقصود **يسقط** ⇒ البوابةُ تَعَضّ (ليست زينة).
- **العطب** = الضابطُ يبقى يمرّ ⇒ دعوى حمايةٍ كاذبة (وهذا ما نُريد أن نكتشفه، لا أن نُخفيه).
- **التخطّي (R57-5)** = الضابطُ **لم يُقَس**: يُتخطّى لغياب بياناته المحلّيّة (`data/local_sample`) فيخرج
  بـ`rc=0` ⇒ كان يُقرأ «البوّابةُ تمرّ — دعوى كاذبة»، وهي دعوى كاذبةٌ تُطبع في الاتجاه المعاكس: التخطّي
  ليس مروراً ولا سقوطاً، بل **غيابُ قياس**. والحصيلةُ تُطبع بثلاث خانات (عَضّ · دعاوى · لم يُقَس) وببيئتها.

والتغطيةُ هنا هي **حصيلةُ جولة مراجعة ٥٢ وإصلاحِ إسقاطاتها** (١٢ بوابة): R52-1 · R52-2 (ثلاثة أوجه) ·
R52-3 · R52-4 · R52-5 (وجهان) · F6 · ومعيارُ الحالة · وسلوكُ سطر الأوامر.
ولا يُلمس الملفُّ الأصليّ: نسخةٌ احتياطيّة تُعاد في `finally` — والنتيجةُ تُقاس بمخرَج pytest لا بالنوايا.
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent   # الجذرُ من الملفّ لا من مسارٍ مكتوب


def _interpreter() -> str:
    """المفسّرُ يُحلّ كما في `pre-push`: نسخةُ الشجرة ← نسخةُ المستودع الرئيسيّ ← `python3`.

    (كان مساراً مكتوباً `.venv/bin/python` ⇒ يسقط في أيّ نسخةٍ أخرى — **أمسكه المدقّق في مراجعة ٥٣**
    وكان عليه أن يُنشئ رابطاً ليُعيد القياس؛ والأسوأ: سقوطُ الأداة يخرج **1** فلا يُميَّز عن «بوّابةٍ عَضّت».)
    """
    cands = [ROOT / ".venv" / "bin" / "python"]
    try:
        gd = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            cwd=str(ROOT), capture_output=True, text=True).stdout.strip()
        if gd:
            cands.append(pathlib.Path(gd).parent / ".venv" / "bin" / "python")
    except Exception:                            # noqa: BLE001 — لا أمرّ بالحواجز
        pass
    cands.append(pathlib.Path(shutil.which("python3") or "python3"))
    for c in cands:
        if str(c) and pathlib.Path(c).exists():
            return str(c)
    return "python3"


PY = _interpreter()
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


def _verdict(rc: int, out: str) -> str:
    """«سقط» · «لم يسقط» · **«تعذّر التشغيل»** · **«لم يُقَس» (تخطٍّ)** — والحكمُ من **علامة pytest نفسها**.

    (لأنّ `python3 -m pytest` بلا pytest مُثبَّتٍ يخرج **1** أيضاً — فيلتبس «تعذّر» بـ«عَضّ»؛
    وهذا ما جعل المدقّق في مراجعة ٥٣ يجعل `.venv/bin/python` رابطاً ليعرف الفرق.)

    **والحالةُ الرابعة (R57-5 · قاسها المدقّق في مراجعة ٥٧):** ضابطٌ **يُتخطّى** لغياب بياناته المحلّيّة
    (`data/local_sample`) يخرج بـ`rc=0` ⇒ كانت الأداةُ تطبع له **«✗ البوابةُ تمرّ — دعوى كاذبة»**، وهي
    تُطبع دعوى كاذبةً بنفسها: التخطّي **ليس** «مرّت البوّابة» — بل **لم يُقَس شيء** (وهو صنفُ «التخطّي
    يُقرأ نجاحاً» الذي يُطارده المستودع). والتخطّي يُقرأ من مخرَج pytest لا من رمز الخروج.
    """
    if re.search(r"\bFAILED\b", out) or re.search(r"\b\d+ (failed|error)", out):
        return "bite"
    if rc == 0:
        return "skipped" if re.search(r"\bskipped\b", out) else "no_bite"
    return "unrunnable"


#: نصُّ كلّ حالةٍ **في موضعٍ واحد** (كان النصُّ مبثوثاً في فرعين ⇒ ضابطُ الصيغة لم يكن ممكناً).
LABELS = {
    "bite": "✓ البوابةُ تَعَضّ",
    "no_bite": "✗ البوابةُ تمرّ — دعوى كاذبة",
    "skipped": "⚪ لم يُقَس (تخطٍّ مُعلَن: لا شهادةَ ولا دعوى)",
    "unrunnable": "🔴 تعذّر التشغيل — ليست شهادةً لبوّابة",
}


def _verdict_label(kind: str) -> str:
    """الصيغةُ المطبوعةُ لكلّ حالة — دالّةٌ خالصةٌ ⇒ تُقاس بسمٍّ في الذاكرة (لا بالعين على مخرَج)."""
    return LABELS[kind]


def _run(test: str) -> tuple[int, str]:
    """يُعيد (رمزَ الخروج، المخرَج). **والسمُّ يقع إذا وفقط إذا كان الرمزُ 1** (سقوطُ ضابط)،

    أمّا رموزُ pytest الأخرى (2 تعذّرُ جمعٍ/مقاطعة · 3 عطبٌ داخليّ · 4 خطأُ استعمال) فهي **تعذّرُ تشغيلٍ**
    لا «بوّابةٌ عَضّت» — وكان الخلطُ بينهما يجعل الأداةَ تشهد لبوّابةٍ لم تُقَس (عطبُ مراجعة ٥٣).
    """
    r = subprocess.run([PY, "-m", "pytest", "-q", "-x", test], cwd=ROOT, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _report(name: str, kind: str, bad: int) -> int:
    print(f"{name:52s} | {'مُطبَّق':6s} | {kind:7s} | {_verdict_label(kind)}")
    return bad + (0 if kind == "bite" else 1)


def _environment() -> str:
    """بيئةُ القياس تُطبع بجانب العدد (R57-5): الضوابطُ التي تحتاج `data/` تُتخطّى هنا، والعددُ بلا
    بيئته يُقرأ «١٣/١٤ فشلٌ» بينما هو **تخطٍّ** — فرقمٌ بلا بيئةٍ ليس رقماً."""
    data = ROOT / "data" / "local_sample"
    return (f"المفسّر={PY} · data/local_sample: {'موجود' if data.exists() else 'غائب'} "
            f"⇒ الضوابطُ التي تحتاج أدلّةً محلّيّة تُتخطّى هنا وتُقاس في نسخة المالك")


def main() -> int:
    print(f"المفسّرُ المستعمل: {PY}")
    print(f"{'البوابة':52s} | {'السمّ':6s} | {'الضابط':6s} | النتيجة")
    print("-" * 92)
    bad = 0
    total = 0
    unmeasured: list[str] = []

    for name, path, old, new, test in CASES:
        bak = path.with_suffix(path.suffix + ".bak_bite")
        shutil.copy2(path, bak)
        try:
            src = path.read_text(encoding="utf-8")
            assert old in src, f"نصُّ السمّ لم يُطابق في {path.name} — القياسُ لا يُكمَل بالنوايا"
            path.write_text(src.replace(old, new, 1), encoding="utf-8")
            rc, out = _run(test)
        finally:
            shutil.copy2(bak, path)
            bak.unlink()
        total += 1
        kind = _verdict(rc, out)
        if kind == "unrunnable":
            print(f"{name:52s} | {'مُطبَّق':6s} | {'?':6s} | {_verdict_label(kind)} (rc={rc}) — "
                  f"{out.strip().splitlines()[-1][:90] if out.strip() else ''}")
            bad += 1
            continue
        if kind == "skipped":
            unmeasured.append(name)
        bad = _report(name, kind, bad)

    # م١٢أ: ملفُّ منفّذٍ **غيرِ مُعلَن** في صندوق المدقّق
    INTRUDER.write_text("# س\n", encoding="utf-8")
    try:
        rc = _run("tests/test_mailbox_ownership.py::test_no_implementer_report_lives_in_the_auditors_box_unless_declared")
    finally:
        INTRUDER.unlink()
    total += 1
    kind = "bite" if rc != 0 else "no_bite"
    bad = _report("م١٢أ · صندوقُ المدقّق بلا تقرير منفّذ (R52-5)", kind, bad)

    # م١٢ب: نقلٌ غيرُ مُعلَن (بإخفاء سجلّ الإعلان — والحركةُ قائمةٌ في المسرَح فعلًا)
    hidden = RENAMES.with_suffix(".md.hidden")
    RENAMES.rename(hidden)
    try:
        rc = _run("tests/test_mailbox_ownership.py::test_every_move_or_delete_under_handoff_is_declared")
    finally:
        hidden.rename(RENAMES)
    total += 1
    kind = "bite" if rc != 0 else "no_bite"
    bad = _report("م١٢ب · النقلُ غيرُ المُعلَن يُرفض (R52-5)", kind, bad)

    # م١٢ج: استثناءٌ متقادم يبقى في القائمة بعد زوال سببِه ⇒ يُكشَف
    intruder2 = ROOT / "handoff/claude/20260924-9999-REPORT-poison-undeclared.md"
    intruder2.write_text("# س\n", encoding="utf-8")
    try:
        rc = _run("tests/test_mailbox_ownership.py::test_no_implementer_report_lives_in_the_auditors_box_unless_declared")
    finally:
        intruder2.unlink()
    total += 1
    kind = "bite" if rc != 0 else "no_bite"
    bad = _report("م١٢ج · الدخيلُ غيرُ المُعلَن يُكشَف — لا قائمةَ صمّاء", kind, bad)

    print("-" * 92)
    # **العددُ يُطبع ببيئته، و«لم يُقَس» يُسمّى بأسمائه** (R57-5): `total - bad` كانت تخلط التخطّيَ بالعَضّ
    # حين يكون `rc=0`، فيُقرأ العددُ وكأنّ البوّابةَ عَضّت وهي لم تُقَس. والحصيلةُ الآن ثلاثُ خانات.
    bites = total - bad - len(unmeasured)
    print(f"الحصيلة: {bites}/{total} بوّاباتٍ تعضّ" + (f" · {len(unmeasured)} لم يُقَس (تخطٍّ مُعلَن)" if unmeasured
                                                       else " · صفرُ تخطٍّ")
          + ("" if not bad else "  ⛔ دعاوى بلا حماية!"))
    if unmeasured:
        print("   لم يُقَس: " + " · ".join(unmeasured))
    print(f"   البيئة: {_environment()}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
