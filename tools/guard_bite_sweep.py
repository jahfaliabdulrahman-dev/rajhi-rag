#!/usr/bin/env python3
"""**سمُّ كلِّ بوابة** — بند ٧ من عُرف الدمج (§الأدب): «لكلِّ بوابةٍ سمٌّ يُثبت أنها تَعَضّ».

يُشغَّل: `.venv/bin/python tools/guard_bite_sweep.py` · والخروجُ 1 إن مرّت بوّابةٌ بلا سمّ.
**ووجودُه في المستودع مقصود** (بند ٦ من العُرف: كلُّ ما يُتحقَّق منه ممثَّلٌ في المستودع): قياسٌ لا يُعاد إنتاجُه من المستودع ليس دليلًا للمدقّق.

الطريقةُ: لكل ضابطٍ نُفسد **السببَ الوحيد** الذي وُجد له، ونُشغّل الضابطَ وحده.
- **السليم** = الضابطُ المقصود **يسقط** ⇒ البوابةُ تَعَضّ (ليست زينة).
- **العطب** = الضابطُ يبقى يمرّ ⇒ دعوى حمايةٍ كاذبة (وهذا ما نُريد أن نكتشفه، لا أن نُخفيه).
- **التخطّي (R57-5)** = الضابطُ **لم يُقَس**: يُتخطّى لغياب بياناته المحلّيّة (`data/local_sample`) فيخرج
  بـ`rc=0` ⇒ كان يُقرأ «البوّابةُ تمرّ — دعوى كاذبة»، وهي دعوى كاذبةٌ تُطبع في الاتجاه المعاكس: التخطّي
  ليس مروراً ولا سقوطاً، بل **غيابُ قياس**. والحصيلةُ تُطبع بـ**أربع خانات** (عَضّ · دعاوى · لم يُقَس ·
  تعذّر تشغيل) وبيئتها، **والتحذيرُ على الدعاوى وحدَها** (S-1/ST-1 · مقعدان قاسا الطرحَ المزدوج للعدد).
  ورموزُ pytest غيرُ 0/1 **تعذّرُ تشغيلٍ قبل أيّ قراءةٍ للنصّ** (ST-2: عطبُ الجمع كان يُقرأ «عَضّاً»).

والتغطيةُ هنا **تراكميّةٌ**: حصيلةُ جولة مراجعة ٥٢ وإصلاحِ إسقاطاتها، ثمّ ما أضافته جولاتُ ٥٨–٥٩
(الجدولُ الذهبيّ · سياسةُ اللاحتميّة بأجزائها · سجلُّ اللاحتميّة وميزانيّتُه) — **والعددُ يُقرأ من مخرَج
الأداة لا من هنا** (كتابةُ العدد نصًّا في ترويسةٍ ثانيةٍ هي نموذجُ «نسختين من الحقيقة»).
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
TFL = ROOT / "tests/test_flake_ledger.py"
WIT = ROOT / "tests/test_answer_names_witness.py"
TURN = ROOT / "tools/turn.py"
INTRUDER = ROOT / "handoff/claude/20260924-9999-REPORT-to-claude-poison.md"
PROOF_T = "tests/test_eval_proof_rows.py"
QG = ROOT / "tools/qa_gate.py"
EP = ROOT / "tools/eval_pack.py"
# **مالكُ القرار والثمن انتقل إلى وحدةٍ مجرّدة** (`tools/gate3.py` · مقعدُ البنية · مراجعة ٦١) ⇒ سمومُه
# (م١٩ · م٢٠ · م٢٤) تُحقن هناك. وإلّا بقيت السمومُ تُعدّل نصًّا غيرَ موجود فتُصنَّف «تعذّر تشغيل» —
# أي بوّاباتٌ تسقط من القياس بصمتٍ وهي تظنّ نفسها مُطبَّقة.
G3 = ROOT / "tools/gate3.py"
CIR = ROOT / "tools" / "ci_report.py"
# **ومُدقِّقُ الدفع مالكُ حُكمٍ في موضعين** (أداةٍ + تذكيرٍ في الخطّاف · R61-1 «ملحقُ الدفع») ⇒
# فسمّاه في الموضعين: `tools/ci_report.py` و`.githooks/pre-push` — لأنّ الصفّ ١٧ يحمل الاثنين.
PUSH_HOOK = ROOT / ".githooks" / "pre-push"
_LP_CMD = ["tools/landing_probe.py"]
_LP_CMD_FROM_WT = ["tools/landing_probe.py", "--from-worktree"]
TSEC = ROOT / "tests/test_secret_scan.py"
LP = ROOT / "tools/landing_probe.py"

#: **ما يجب أن يُسمّى في العَضّة** (R61-2 · اختياريّ): حالةٌ سكربتيّةٌ «تعضّ» بلا الاسم المتوقَّع في مخرَجها
#: عَضَّت **لسببٍ آخر** ⇒ فلا تُقبل شهادةً (الوسمُ لا يعدو دليله): تُطبع باسمها وتُحصى «تعذّر قياس».
MUST_NAME: dict[str, str] = {
    "م٢١ · مسبارُ الهبوط يكشف مراجعةً لا تهبط (P-11)": "tests/test_report_names.py",
    "م٢٢ · تراجعُ ضابط الهبوط (مقارنةٌ حيّةٌ تشمل الصناديق) يمسكه المسبار (R59-1)": "tests/test_secret_scan.py",
}

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

    # **الجدولُ الذهبيّ** (مقعدُ المعايير · جولة ٥٨): القفلُ الجديد لم يكن له سمٌّ ⇒ يُضاف.
    ("م١٢ · الجدولُ الذهبيّ يطابق الوثيقة (R13)", QG,
     '"٦١,١٦٥١٢": "61165.12"',
     '"٦١,١٦٥١٢": "35832.43"',
     "tests/test_gate_goldens.py::test_the_gate_goldens_agree_with_the_locked_rule"),

    # **سياسةُ اللاحتميّة** (جولة ٥٩): القاعدةُ الحاسمةُ فيها («لا براءةَ بلا قراءةٍ نظيفة») بلا سمٍّ
    # ليست حارسًا بل نصًّا — والسمُّ يجعلها تقرأ كلَّ قراءةٍ نظيفة، فتُمرّر غيرَ النظيفة.
    ("م١٣ · سياسةُ اللاحتميّة لا تُمرّر قراءةً غيرَ نظيفة (R13)", QG,
     '    if _is_clean(first):\n        return True, f"قراءةٌ نظيفةٌ من المحاولة الأولى',
     '    if True:\n        return True, f"قراءةٌ نظيفةٌ من المحاولة الأولى',
     "tests/test_gate_flake_policy.py::test_the_decisive_rule_is_no_clean_read_no_acquittal"),

    # **شطرا «النظافة» الأخريان** (مقعدُ البنية F-3): لكلٍّ سمُّه — فالقاعدةُ المركَّبةُ تُقاس بأجزائها لا بجملتها.
    ("م١٤ · فقدُ صفٍّ ليس نظافة (R13)", QG,
     '    return (run["susp"] == 0 and run["clean"] == run["total"]',
     '    return (run["susp"] == 0 and True',
     "tests/test_gate_flake_policy.py::test_a_lost_row_is_not_clean_even_with_zero_suspects"),

    # **وثغرةُ «القراءة الأنحف»** (اصطادها مقعدا المعايير والمواصفة بالقياس): سمُّها يقلب شرطَها.
    ("م١٥ · القراءةُ الثانيةُ الأنحفُ لا تُبرّئ (R13)", QG,
     '    if second["n_rows"] < first["n_rows"] or second["total"] < first["total"]:',
     '    if False:',
     "tests/test_gate_flake_policy.py::test_a_thinner_second_read_cannot_acquit"),

    # **وسجلُّ اللاحتميّة** (شرطُ مراجعة ٥٨): الحارسُ يعدّ **ويحمّر**؛ فسمُّه يُلغي العدَّ فيصير السجلُّ
    # تزييناً (وسمٌ يُطبع ولا يُقيَّد)، وهو بعينه ما وُجد السجلُّ ليمنعه.
    # **م١٦ · ميزانيّةُ اللاحتميّة تحمرّ عند التجاوز (شرطُ مراجعة ٥٨):** والسطرُ يُعدَّل مع تعديل
    # دالّة العدّ نفسِها (S6 · مراجعة ٦١: الأحداثُ = تشغيلاتٌ محفوظة ∪ قيودٌ بلا دليل) — وسمٌّ يشير
    # إلى نصٍّ زائل **يُصنَّف «تعذّر تشغيل»** (يعضّه المشغّل نفسه فعلًا عند تعديل الدالّة — وهو مقياسه).
    ("م١٦ · ميزانيّةُ اللاحتميّة تحمرّ عند التجاوز (شرطُ مراجعة ٥٨)", TFL,
     '    if len(dirty) + len(orphans) <= budget:\n        return []',
     '    return []',
     "tests/test_flake_ledger.py::test_the_budget_actually_bites_on_a_synthetic_window"),

    # **م١٧ · الشاهدُ الذاتيّ (F4 · مقعدُ المواصفة):** كان الفحصُ يقبل الملفَّ نفسَه شاهداً ⇒ فسمُّه
    # يُلغي شرطَ الذاتيّة، ويجب أن يُسقط الضابطَ الذي يقيسها.
    ("م١٧ · الشاهدُ الذاتيّ لا يُعدّ دليلاً (F4 · مراجعة ٥٩)", WIT,
     '        if witness == path:\n            out.append(',
     '        if False:\n            out.append(',
     "tests/test_answer_names_witness.py::test_the_witness_must_be_a_verdict_not_any_path_in_the_tree"),

    # **م١٨ · هويّةُ الترويسة (نقلةُ مقعد البنية · مراجعة ٥٩):** صار الشرطُ «معرّفُ الكتلة == زمنُ الاسم»
    # ⇒ فسمُّه يُلغي الهويّة فيقرأ ترويسةَ تقريرٍ آخر تُقتبَس في أعلى ملفّ ترويسةً له، ويجب أن يُسقط ضابطَه.
    ("م١٨ · الترويسةُ تُقاس بالهويّة لا بالشكل (نقلةُ مراجعة ٥٩)", TURN,
     '            return stamp_of(m.group(1)) == own',
     '            return True',
     "tests/test_turn_derivation.py::test_the_fenced_header_is_read_not_ignored"),

    # **م١٩ · سقفُ ثمن قرار المالك (R60-1 · مراجعة ٦٠):** القرارُ يقع على **ثمن الإفراج** داخل سقفه
    # المُعلَن ولا يتمدّد؛ فسمُّه يُلغي السقفَ فيصير القرارُ رخصةً لأي ثمن — ويجب أن يُسقط ضابطَه.
    ("م١٩ · قرارُ المالك لا يتمدّد فوق سقف ثمنه المُعلَن", G3,
     '    return int(price_pages) <= int(decision["price_cap_pages"])',
     '    return True',
     "tests/test_eval_pack.py::test_the_owner_decision_closes_the_price_not_the_overlap"),

    # **م٢٠ · البوابةُ (٣) لا تُرخى بقرار (R60-1 · حاجبُ مراجعة ٦٠):** كان السقفُ يُرخي **التقاطعَ نفسَه**
    # ⇒ قِيس أن ١٣٣ صفحةً تداخلًا تُعطي `PASS` (رخصةُ إدخال ثلثَي الحزمة إلى التدريب). فسمُّ
    # `gate3_overlap_ok` يُعيد الرخصةَ، ويجب أن يُسقط ضابطَ «التداخلُ عطبٌ مُسمًّى لا قرارُ مالك».
    ("م٢٠ · التداخلُ عطبٌ يُسقط البوابةَ ولا يُرخيه قرار (حاجبُ مراجعة ٦٠)", G3,
     '    return not inter\n\n\ndef gate3_price_within_cap',
     '    return True\n\n\ndef gate3_price_within_cap',
     "tests/test_eval_pack.py::test_an_overlap_is_a_named_defect_even_with_a_dated_owner_decision"),

    # **م٢١ · مسبارُ الهبوط يعضّ (P-11 · تبنّاه المالك من توصية مراجعة ٥٩):** الضابطُ الحقيقيُّ ليس عدّاداً
    # بل **الثابت**: «هل تهبط مراجعة؟». فسمُّه يجعل المراجعةَ الاصطناعيّة **لا تهبط** (زمنُ اسمها منزاحٌ
    # عن إيداعها) ⇒ يجب أن يُسقط المسبارُ ضابطَ أسماء التقارير **باسمه**، لا أن يعضَّ لسببٍ آخر (MUST_NAME).
    ("م٢١ · مسبارُ الهبوط يكشف مراجعةً لا تهبط (P-11)", LP,
     '    return measure(args.ref, args.from_worktree, args.poison, args.keep, quiet=args.quiet)',
     '    return measure(args.ref, args.from_worktree, "name-stamp", args.keep, quiet=args.quiet)',
     _LP_CMD),

    # **م٢٢ · الصنفُ نفسُه يعود فيُمسَك (R59-1 · حاجبُ مراجعة ٥٩):** يُعاد **حرفيًّا** ما كان: قياسٌ حيٌّ
    # لرقمٍ **يشمل صناديق المراسلة** (`excluded_prefix=""`) ⇒ نصُّ المدقّق يصير مُدخَلاً إلى راتشتٍ يملكه
    # المنفّذ. والمسبارُ يجب أن يسقط — **باسم ضابط الماسح** — لأن نسختَه تحمل مراجعةً تقتبس الصيغة.
    # (وهذا هو الفرقُ بين إصلاحٍ سطحيّ وإغلاقِ صنف: الأوّلُ يصلح الحالةَ، وهذا يقيس أنّ الصنفَ لا يعود.)
    ("م٢٢ · تراجعُ ضابط الهبوط (مقارنةٌ حيّةٌ تشمل الصناديق) يمسكه المسبار (R59-1)", TSEC,
     '    assert _undated_snapshot_pairs(proto) == [], (\n'
     '        f"أرقامٌ تشمل صناديق المراسلة بلا وسمِ تأريخٍ وتاريخ: {_undated_snapshot_pairs(proto)} ⇒ "\n'
     '        "يُكتب كلُّ رقمٍ مع شجرته (R59-1)، ولا يُدخَل نصُّ المدقّق في راتشتٍ يملكه المنفّذ")',
     '    lines_all, files_all, _, _ = _tatweel_form_counts(files, excluded_prefix="")\n'
     '    assert _pair_at(proto, r"(\\d+)·(\\d+)\\s*بلا حسّاس") == (lines_all, files_all), "R59-1: مقارنةٌ حيّةٌ تشمل الصناديق"',
     _LP_CMD_FROM_WT),

    # **م٢٣ · ثقبُ مقام التغطية عطبُ نظافة (R60-2 · قاسه المدقّق في مراجعة ٦٠):** كان يُقرأ «نظيفًا» عند
    # السياسة ⇒ لا إعادةَ قراءةٍ ولا وسم، ثمّ تسقط البوّابةُ على تأكيدٍ صلب ⇒ «٤/٥» ثمّ إعادةُ البوّابة
    # كلِّها **باليد**. فسمُّه يُلغي شرطَ المقام من دالّة النظافة، ويجب أن يُسقط ضابطَ الثقب.
    ("م٢٣ · ثقبُ مقام التغطية عطبُ نظافة لا سقوطٌ صامت (R60-2)", QG,
     '            and bool(cov) and f_possible == cov[1])',
     '            and True)',
     "tests/test_gate_flake_policy.py::test_a_footer_denominator_hole_is_a_dirty_read_not_a_silent_gate_failure"),

    # **م٢٤ · «عددٌ» ليس كلَّ ما `isinstance(x, int)` (مراجعة ٦١ · قاسه مقعدا المعايير والبنية):** `bool`
    # صنفٌ من `int` في بايثون ⇒ `True <= 133` صحيحة، فمانيفستٌ حقلُه `true` كان يُقرأ «ثمنًا مقيسًا»
    # داخل السقف ويُطبع `PASS`. فسمُّ الحرس يُعيد التساهل، ويجب أن يُسقط ضابطَ العدد الحقيقيّ.
    ("م٢٤ · العددُ الحقيقيّ ليس `bool` (ثمنٌ `true` لا يمرّ مقيسًا)", G3,
     '    return isinstance(x, int) and not isinstance(x, bool)',
     '    return isinstance(x, int)',
     "tests/test_eval_pack.py::test_a_boolean_field_is_not_a_measured_price"),

    # **م٢٥ · «أخضر» بلا مرساة (R62-F4 · قاسه المقاعد الثلاثة):** كان `if head and not _same_commit(…)`
    # يُسقط المقابلةَ إن **غاب** `headSha` من خَرْج `gh` ⇒ تُوسَم الأداةُ «أخضر» ولا تقيس شيئًا — وهو
    # عينُ صنفِ R61-1 (حُكمٌ بلا موضعِ قياس) طبقةً أعمق. فسمُّه يُعيد الشرطَ المتساهل، ويجب أن يُسقط
    # ضابطَ الفشل المُغلَق. (وشرطُ `and` هو الفرقُ بين «لا أدري» و«نظيف».)
    ("م٢٥ · تشغيلٌ بلا `headSha` لا يُقال له أخضر (فشلٌ مُغلَق · R62)", CIR,
     '    if not head:\n'
     '        return {"ref": ref, "state": "غيرُ مقروء",\n'
     '                "why": f"تشغيلٌ بلا `headSha` ⇒ لا مرساةَ تقيسها (والمدفوعُ {want[:7]})"}\n'
     '    if not _same_commit(want, head):',
     '    if head and not _same_commit(want, head):',
     "tests/test_ci_report.py::test_a_run_without_a_headsha_cannot_be_called_green"),

    # **م٢٦ · الخطّافُ يُسقط دفعاً مشروعاً (R62-F1 · حاجبُ الجولة ٦٢ · صاده المقاعدُ الثلاثة):** كان
    # سطرُ التذكير آخرَ سطرٍ ويستخرج المراجعَ بـ`awk` على **الحقل الأول** ⇒ وسمٌ/حذفُ فرع/دفعٌ بلا جديد
    # يُفرِغ `BRANCHES` فيخرج الخطّاف **1 بلا سبب** ⇒ دفعٌ مشروعٌ يُرفض صامتاً، ويُصنع الحافزُ على
    # `--no-verify` الذي يُسقط حارسَي الأمن. فسمُّه يُعيد الأسطرَ التي كانت، ويجب أن يُسقط ضابطَ
    # «الخطّافُ لا يُسقط دفعاً مشروعاً» — بعد أن كان يُقاس بمقعدِ مدقّقٍ لا بضابط.
    ("م٢٦ · خطّافُ الدفع لا يُسقط دفعاً مشروعاً (R62-F1)", PUSH_HOOK,
     "printf '%s\\n' \"$REFS\" | \"$PY\" tools/ci_report.py --pre-push || true\nexit 0",
     "BRANCHES=$(printf '%s\\n' \"$REFS\" | awk '{print $1}' | sed -n 's#^refs/heads/##p' | sort -u)\n"
     "[ -n \"$BRANCHES\" ] && \"$PY\" tools/ci_report.py --remind $BRANCHES",
     "tests/test_hook_gates.py::test_the_pre_push_hook_never_blocks_a_legitimate_push"),
]


def _verdict(rc: int, out: str) -> str:
    """«سقط» · «لم يسقط» · **«تعذّر التشغيل»** · **«لم يُقَس» (تخطٍّ)** — **ورمزُ الخروج يُحكم أوّلًا** (ST-2).

    (لأنّ `python3 -m pytest` بلا pytest مُثبَّتٍ يخرج **1** أيضاً — فيلتبس «تعذّر» بـ«عَضّ»؛
    وهذا ما جعل المدقّق في مراجعة ٥٣ يجعل `.venv/bin/python` رابطاً ليعرف الفرق.)

    **ولماذا الرمزُ أوّلًا (ST-2 · قاسه مقعد البنية):** كان الحكمُ يُقرأ من **نصّ المخرَج** وحدَه، ومخرَجُ
    عطبِ **الجمع** (`rc=2`) يحمل «1 error in 0.04s» ⇒ كان يُصنَّف **«عَضّ»**، أي شهادةٌ لبوّابةٍ لم تُجمَع
    أصلًا — أخطرُ الأصناف في هذا المستودع. والآن: `rc ∉ {0,1}` تعذّرٌ قبل أيّ قراءةٍ للنصّ.

    **والحالةُ الرابعة (R57-5 · قاسها المدقّق في مراجعة ٥٧):** ضابطٌ **يُتخطّى** لغياب بياناته المحلّيّة
    (`data/local_sample`) يخرج بـ`rc=0` ⇒ كانت الأداةُ تطبع له **«✗ البوابةُ تمرّ — دعوى كاذبة»**، وهي
    تُطبع دعوى كاذبةً بنفسها: التخطّي **ليس** «مرّت البوّابة» — بل **لم يُقَس شيء** (وهو صنفُ «التخطّي
    يُقرأ نجاحاً» الذي يُطارده المستودع). والتخطّي يُقرأ من مخرَج pytest لا من رمز الخروج.
    """
    if rc not in (0, 1):
        return "unrunnable"                        # 2 عطبُ جمع/مقاطعة · 3 عطبٌ داخليّ · 4 خطأُ استعمال
    if rc == 1:
        # «عَضّ» يقتضي **فشلاً مُسمّى** في المخرَج؛ ورمزُ 1 بلا علامةٍ مُسمّاةٍ ليس شهادة.
        return "bite" if _FAILURE_RE.search(out) else "unrunnable"
    return "skipped" if re.search(r"\bskipped\b", out) else "no_bite"


#: علاماتُ فشل pytest في المخرَج — تُقرأ **فقط** حين يكون رمزُ الخروج 1 (ST-2).
_FAILURE_RE = re.compile(r"\bFAILED\b|\b\d+ (failed|error)")
#: مراتبُ الحكم الأربع — تُحصى في موضعٍ واحد.
KINDS = ("bite", "no_bite", "skipped", "unrunnable")


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


def _command_for(test: str | list) -> list[str]:
    """**أمرُ الحالة — تمييزٌ صريحٌ لا استنتاجٌ من النصّ** (مقعدُ البنية · مراجعة ٦١).

    كان `_run` يقرأ **نوعَ الأمر من نصّه**: `".py" in test and not test.startswith("tests/")` ⇒ أيُّ ضابطٍ
    يحمل `.py` في اسمه أو في وسيطٍ له (ملفُّ بيانات، معرّفُ حالة) كان يُشغَّل **سكربتًا** بلا pytest فيُقاس
    «تعذّرُ تشغيل» ويُسمّى حالةً أخرى — عطبٌ صامتٌ يظهر يومَ يُضاف ضابطٌ جديد. والآن **القائمةُ أمرٌ**
    (تُشغَّل بمفسّر الشجرة، ووسائطُها لا يُعاد تفسيرُها بيد) **والنصُّ ضابطُ pytest** بمعرّفه.
    """
    if isinstance(test, list):
        return [PY, *test]
    return [PY, "-m", "pytest", "-q", "-x", test]


def _run(test: str | list) -> tuple[int, str]:
    """يُعيد (رمزَ الخروج، المخرَج). **والسمُّ يقع إذا وفقط إذا كان الرمزُ 1** (سقوطُ ضابط)،

    أمّا رموزُ pytest الأخرى (2 تعذّرُ جمعٍ/مقاطعة · 3 عطبٌ داخليّ · 4 خطأُ استعمال) فهي **تعذّرُ تشغيلٍ**
    لا «بوّابةٌ عَضّت» — وكان الخلطُ بينهما يجعل الأداةَ تشهد لبوّابةٍ لم تُقَس (عطبُ مراجعة ٥٣).

    **وهدفٌ سكربتيّ (R61-2 · مسبارُ الهبوط P-11):** الضابطُ قد يكون **أمرًا** لا ملفَّ `pytest` (المسبارُ
    يبني نسخةً ويُشغّل قائمةَ الضوابط فيها). فيُشغَّل السكربتُ بمفسّر الشجرة نفسِه عبر `_command_for`
    (والتمييزُ بين «أمرٍ» و«ضابط» صريحٌ هناك — قائمةٌ أم نصّ).
    """
    r = subprocess.run(_command_for(test), cwd=ROOT, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _emit(name: str, rc: int, out: str, counts: dict[str, int], unmeasured: list[str]) -> str:
    """يطبع سطرَ ضابطٍ واحد ويُحصيه — **والحكمُ من `_verdict` وحدَها** (رمزُ الخروج أوّلًا).

    (كانت ثلاثةُ مساراتٍ في `main` تحكم بـ`rc != 0` وحدَه ⇒ أيُّ فشلٍ — ومنه غيابُ pytest — «عَضّ»؛ ST-2.)

    **ويُعيد الحالة** (R61-2) ليُقابَل الاسمُ المتوقَّع في `MUST_NAME` **بعد** الحكم لا قبله.
    """
    kind = _verdict(rc, out)
    counts[kind] += 1
    if kind == "skipped":
        unmeasured.append(name)
    tail = out.strip().splitlines()[-1][:90] if out.strip() else ""
    extra = f" (rc={rc}) — {tail}" if kind == "unrunnable" else ""
    print(f"{name:52s} | {'مُطبَّق':6s} | {kind:7s} | {_verdict_label(kind)}{extra}")
    return kind


def _summary(counts: dict[str, int], total: int, equipped: bool) -> str:
    """سطرُ الحصيلة: كلُّ حالةٍ بخانتها، **والتحذيرُ على الدعاوى وحدَها** (S-1/ST-1 · مقعدان قاساه).

    **العلّةُ المقيسة:** `bites = total - bad - len(unmeasured)` و`bad` كان يُزاد لكلّ حالةٍ ليست عَضّاً
    ⇒ التخطّي يُطرح **مرّتين**: العددُ المطبوع أقلُّ من صفوفِ «✓ البوابةُ تَعَضّ» في المخرَج نفسِه
    (١٢ مقابل ١٣)، و«⛔ دعاوى بلا حماية!» تُطبع على **تخطٍّ** لا يدّعي شيئاً — أي وصفٌ يخالف مصدره في
    الأداة التي وُلدت لإنهاء هذا النوع من الوصف.
    """
    line = f"الحصيلة: {counts['bite']}/{total} بوّاباتٍ تعضّ"
    if counts["no_bite"]:
        line += f" · {counts['no_bite']} دعوى بلا حماية"
    if counts["skipped"]:
        line += f" · {counts['skipped']} لم يُقَس (تخطٍّ مُعلَن)"
    if counts["unrunnable"]:
        line += f" · {counts['unrunnable']} تعذّر تشغيل"
    if counts["no_bite"]:
        line += "  ⛔ دعاوى بلا حماية!"
    if counts["unrunnable"] or (counts["skipped"] and equipped):
        line += "  ⛔ عطبُ قياس — لا شهادةَ ولا دعوى"
    return line


def _exit_code(counts: dict[str, int], equipped: bool) -> int:
    """`1` إن ادّعت بوّابةٌ حمايةً لا تملكها، أو تعذّر تشغيلُها، أو لم تُقَس في بيئةٍ **مُهيّأة**.

    و«لم يُقَس» في بيئةٍ **ناقصة** (لا `data/local_sample`) ليس فشلاً: هو إعلانُ حدِّ البيئة ويُطبع باسمه
    وبيئته — وإلّا لصارت النسخةُ النقيّةُ لا تُخضِرّ أبداً، وهو صنفُ الإنذار الكاذب نفسُه (S-1).
    """
    faulty = counts["no_bite"] + counts["unrunnable"] + (counts["skipped"] if equipped else 0)
    return 1 if faulty else 0


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
    counts = {k: 0 for k in KINDS}
    unmeasured: list[str] = []
    total = 0
    equipped = (ROOT / "data" / "local_sample").exists()

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
        kind = _emit(name, rc, out, counts, unmeasured)
        want = MUST_NAME.get(name)
        if want and kind == "bite" and want not in out:
            # **عَضَّ لسببٍ آخر** ⇒ لا شهادة (R61-2): يُطبع باسمه ويُحصى «تعذّر قياس» (لا «عضّ»).
            counts["bite"] -= 1
            counts["unrunnable"] += 1
            print(f"      🔴 عَضَّ بلا الاسم المتوقَّع «{want}» ⇒ عَضٌّ لسببٍ آخر: لا شهادةَ لهذا الضابط")

    # م١٢أ: ملفُّ منفّذٍ **غيرِ مُعلَن** في صندوق المدقّق
    INTRUDER.write_text("# س\n", encoding="utf-8")
    try:
        rc, out = _run("tests/test_mailbox_ownership.py::test_no_implementer_report_lives_in_the_auditors_box_unless_declared")
    finally:
        INTRUDER.unlink()
    total += 1
    _emit("م١٢أ · صندوقُ المدقّق بلا تقرير منفّذ (R52-5)", rc, out, counts, unmeasured)

    # م١٢ب: نقلٌ غيرُ مُعلَن (بإخفاء سجلّ الإعلان — والحركةُ قائمةٌ في المسرَح فعلًا)
    hidden = RENAMES.with_suffix(".md.hidden")
    RENAMES.rename(hidden)
    try:
        rc, out = _run("tests/test_mailbox_ownership.py::test_every_move_or_delete_under_handoff_is_declared")
    finally:
        hidden.rename(RENAMES)
    total += 1
    _emit("م١٢ب · النقلُ غيرُ المُعلَن يُرفض (R52-5)", rc, out, counts, unmeasured)

    # م١٢ج: استثناءٌ متقادم يبقى في القائمة بعد زوال سببِه ⇒ يُكشَف
    intruder2 = ROOT / "handoff/claude/20260924-9999-REPORT-poison-undeclared.md"
    intruder2.write_text("# س\n", encoding="utf-8")
    try:
        rc, out = _run("tests/test_mailbox_ownership.py::test_no_implementer_report_lives_in_the_auditors_box_unless_declared")
    finally:
        intruder2.unlink()
    total += 1
    _emit("م١٢ج · الدخيلُ غيرُ المُعلَن يُكشَف — لا قائمةَ صمّاء", rc, out, counts, unmeasured)

    print("-" * 92)
    # **العددُ يُطبع ببيئته وبخاناتِه** (R57-5 · وصحّحه S-1/ST-1): كلُّ حالةٍ خانةٌ مستقلّة، والتحذيرُ على
    # **الدعاوى** وحدَها، و«لم يُقَس» يُسمّى بأسمائه. ⇒ لا عددَ يخالف صفوفَه ولا إنذارَ كاذب على تخطٍّ.
    print(_summary(counts, total, equipped))
    if unmeasured:
        print("   لم يُقَس: " + " · ".join(unmeasured))
    print(f"   البيئة: {_environment()}")
    return _exit_code(counts, equipped)


if __name__ == "__main__":
    raise SystemExit(main())
