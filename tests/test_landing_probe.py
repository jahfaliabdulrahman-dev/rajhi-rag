"""**مسبارُ الهبوط (P-11) — ضوابطُ الأداة نفسِها** (R61-2 · وأوّلُ ما أمسكه مسبارُ الهبوط قبل أن يُودَع).

ولماذا وحدةٌ مستقلّة: المسبارُ يقيس «هل تهبط مراجعة؟» بأداةٍ تقرأ الـworkflow وتبني نسخةً وتُودِع شاهدًا
اصطناعيًّا — فإن اعتلّت الأداةُ نفسُها (قائمةٌ مقروءةٌ خطأً · اسمٌ لا يوافق قاعدةَ الأسماء · شكلُ الشاهد
ناقص) صار القياسُ شهادةً كاذبةً **بلا أن يصرخ أحد**. والضوابط هنا **خفيفةٌ بلا نسخٍ ولا شبكة** (النسخُ
يُقاس في الـCI بخطوة `gate_landing` نفسِها، والسمومُ في `guard_bite_sweep` م٢١/م٢٢).

**وحدُّها مُعلَن:** لا تختبر البناءَ الفعليّ للنسخة (ذاك يقتضي clone)، ولا «هل الشكلُ الاصطناعيُّ يشبه
مراجعةً حقيقيّةً بالكامل» — الشكلُ متّفقٌ عليه بين الطرفَين (شرطُ المدقّق في مراجعة ٥٩).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import landing_probe as lp  # noqa: E402


def test_the_measured_list_is_read_from_the_workflow_not_from_a_second_copy():
    """**مصدرٌ واحد:** قائمةُ الضوابط التي يُشغّلها المسبارُ تساوي ما في الـworkflow بالحرف — تُقاس
    بقراءةٍ مستقلّةٍ لنصّ الـworkflow (لا بالاستناد إلى دالّة الأداة نفسِها)."""
    text = lp.WORKFLOW.read_text(encoding="utf-8")
    independent = list(dict.fromkeys(re.findall(r"tests/[A-Za-z0-9_/]+\.py", text)))
    assert independent, "لم أقرأ ملفَّ ضابطٍ من الـworkflow ⇒ فشلٌ مُغلَق"
    assert lp.ci_files() == independent, (
        "قائمةُ المسبار تخالف الـworkflow ⇒ يقيس ضوابطَ غيرَ التي يعبرها الـCI")


def test_the_probe_is_wired_into_ci_as_a_registered_step():
    """**الوصلُ لا يُدَّعى:** خطوةٌ باسم `gate_landing` في الـworkflow تُشغّل الأداة، **والمعرّفُ مُسجَّل**
    في §٣ من `docs/GATES.md` (وإلّا لكان المسبارُ أداةً لا يعبرها شيءٌ في الـCI)."""
    text = lp.WORKFLOW.read_text(encoding="utf-8")
    m = re.search(r"id:\s*(gate_landing)\b(.*?)(?=\n\s*-\s|\Z)", text, re.S)
    assert m, "لا خطوةَ `gate_landing` في الـworkflow ⇒ المسبارُ خارج الـCI"
    assert "tools/landing_probe.py" in m.group(2), "الخطوةُ لا تُشغّل الأداةَ بالاسم"
    assert "gate_landing" in (ROOT / "docs" / "GATES.md").read_text(encoding="utf-8"), (
        "معرّفُ الخطوة غيرُ مُسجَّلٍ في §٣ ⇒ السجلُّ والمُشغِّل يفترقان")


def test_the_list_follows_the_tree_it_is_pointed_at(tmp_path):
    """**مصدرٌ واحد لكلّ شجرة** (أمسك سمُّ م٢١ الحاجةَ نفسَها): القائمةُ تُقرأ من الـworkflow **في الشجرة
    المقيسة**؛ فقياسُ نسخةٍ مُودَعةٍ بقائمةٍ محلّيّةٍ تحمل ضابطًا لم يُودَع بعد = «تعذّر قياس» كاذب.
    والشكلُ يُقاس بملفٍّ مصنوعٍ هنا (لا بنسخة): ترتيبٌ محفوظٌ · تكرارٌ لا يُضاعِف · غيابٌ يُعطي الفراغ."""
    wf = tmp_path / "publish-guard.yml"
    wf.write_text(
        "        python3 -m pytest tests/test_aaa.py \\\n"
        "                           tests/test_bbb.py \\\n"
        "                           tests/test_aaa.py\n",
        encoding="utf-8")
    assert lp.ci_files(wf) == ["tests/test_aaa.py", "tests/test_bbb.py"]
    assert lp.ci_files(tmp_path / "ghost.yml") == [], "قائمةٌ من ملفٍّ غير موجود"
    assert lp.ci_files() == lp.ci_files(lp.WORKFLOW), "المسارُ الافتراضيّ هو workflow المستودع"


def test_the_synthetic_review_carries_every_shape_the_counters_bite_on():
    """**شكلُ الشاهد — ستّةُ عناصرَ من قائمة مراجعة ٥٩ نفسِها** (لا من الذوق): صيغةُ الكشيدة (مبنيةً لا
    مكتوبة) · «N سطراً في M ملفّ» · `status:` في المتن · `in-reply-to:` مقتبَسًا · كلمةُ REPORT في المتن ·
    ومعرّفُ التزامٍ غريب. وشاهدٌ ينقصه عنصرٌ يقيس **أقلَّ** ممّا يدّعي."""
    body = lp._synthetic_review("20260925-120000", "abc1234def", "main", None)
    for needle, what in ((f"الـ{lp.TATWEEL}sha", "صيغةُ الكشيدة"),
                         ("سطراً في", "كمُّ الكشيدة «N سطراً في M ملفّاً»"),
                         ("status:", "سطرُ `status:` في المتن"),
                         ("in-reply-to:", "سطرُ `in-reply-to:` مقتبَسًا"),
                         ("REPORT", "كلمةُ REPORT في المتن")):
        assert needle in body, f"الشاهدُ الاصطناعيُّ لا يحمل {what} ⇒ العدّادُ لا يراه"
    assert re.search(r"commit\s+[0-9a-f]{7}\b", body), "لا معرّفَ التزامٍ غريبًا في الشاهد"


def test_the_witness_name_obeys_the_name_rule_and_the_poison_shifts_it():
    """**الاسمُ بزمنه في مقدّمته** (قاعدةُ أسماء التقارير)، **والسمُّ يُزيحه ثلاثَ ساعات** — فيجب أن
    يسقط ضابطُ الأسماء. ولو لم يكن للسمّ أثرٌ على الاسم لكان «إثباتُ العضّ» دعوى بلا فرق."""
    name = lp._name("20260925-120000", None)
    assert name == "20260925-120000-third-eye-review-99-landing-probe.md", name
    assert re.match(r"^\d{8}-\d{6}-", name), "الاسمُ لا يبدأ بزمنٍ ⇒ خارج قاعدة الأسماء"
    assert "REPORT" not in name, "اسمُ الشاهد يحمل REPORT ⇒ يُقرأ تقريرَ منفّذٍ في صندوق المدقّق"
    poisoned = lp._name("20260925-120000", "name-stamp")
    assert poisoned == "20260925-090000-third-eye-review-99-landing-probe.md", poisoned


def test_every_declared_poison_is_implemented():
    """**لا سمَّ وعدًا:** كلُّ اسمٍ في `POISONS` يجب أن يُغيّر الشاهدَ فعلًا (وإلّا فهو وعدٌ في متغيّر)."""
    assert lp.POISONS, "لا سمومَ مُعلَنة ⇒ إثباتُ العضّ بلا أداة"
    plain_name = lp._name("20260925-120000", None)
    plain_body = lp._synthetic_review("20260925-120000", "abc1234def", "main", None)
    for poison in lp.POISONS:
        assert (lp._name("20260925-120000", poison) != plain_name
                or lp._synthetic_review("20260925-120000", "abc1234def", "main", poison) != plain_body), \
            f"السمُّ «{poison}» مُعلَنٌ ولا أثرَ له ⇒ وعدٌ لا سم"


def test_the_probe_refuses_to_measure_when_it_cannot_read_the_list(capsys):
    """**فشلٌ مُغلَق:** قائمةٌ غيرُ مقروءة ⇒ `rc=2` ورسالةٌ مُسمّاة — ولا يُقرأ التعذّرُ نظافةً."""
    assert lp.ci_files(Path("/nonexistent/publish-guard.yml")) == [], "قائمةٌ تُقرأ من ملفٍّ غير موجود"
    saved = lp.ci_files
    lp.ci_files = lambda *a, **k: []                       # يقيس الجرد لا النسخ
    try:
        rc = lp.measure("HEAD", False, None, False)
    finally:
        lp.ci_files = saved
    out = capsys.readouterr().out
    assert rc == 2, f"غيابُ القائمة يجب أن يمنع القياس (صار {rc})"
    assert "تعذّر القياس" in out, out


def test_one_parser_for_the_stamp_format():
    """**مُحلِّلُ الختم مالكُه واحد — بالخاصّيّة لا بالنصّ** (P3-١١ · مراجعة ٦١ · ثمّ مقعدا المعايير
    والبنية في الجولة ٦٥).

    كان الضابطُ يعدّ نصًّا (`src.count("stamp[9:11]") == 1`) فيبقى **أخضرَ** مع مُحلِّلٍ محلّيٍّ ثانٍ
    (`_stamp_dt`) **أضيقَ من مالكه**: `_stamp_dt("20260922-240000")` ⇒ `ValueError` بينما
    `turn.as_datetime` ⇒ `2026-09-23 00:00` (واصطلاحُ `24:00` موثَّقٌ وله ضابطٌ في
    `tests/test_report_names.py`). فصار الضابطُ يقيس **الخاصّيّة** لا نصَّ الشيفرة.
    """
    # (١) الاسمُ: بلا سمٍّ يأخذ زمنه، وبالسمّ يُزاح ثلاثَ ساعات — والزمنُ من **مالك الصيغة** لا نسخة
    assert lp._name("20260925-211945", None).startswith("20260925-211945")
    assert lp._name("20260925-211945", "name-stamp").startswith("20260925-181945")
    # (٢) **الخاصّيّةُ لا النصّ:** لا مُحلِّلَ محلّيًّا للختم، واصطلاحُ نهاية اليوم يمرّ كما في مالكه
    src = Path(str(lp.__file__)).read_text(encoding="utf-8")
    assert "fromisoformat" not in src, "مُحلِّلٌ محلّيٌّ ثانٍ للختم ⇒ نسختان تفترقان (ST-4)"
    assert "def _stamp_dt" not in src, "دالّةُ تحليلٍ محلّيّةٌ باقيةٌ (المالكُ واحد: `turn.as_datetime`)"
    assert lp.as_datetime("20260922-240000").strftime("%Y%m%d-%H%M%S") == "20260923-000000", \
        "اصطلاحُ نهاية اليوم لا يمرّ ⇒ نسخةٌ أضيقُ من مالكها"
    # (٣) والحقائقُ الزمنيّةُ **مستورَدةٌ من المالك** لا معرَّفةٌ هنا (نمطُ الاسم · اصطلاحُ زمنه · منطقتُه)
    assert lp.as_datetime.__module__ == "turn" and lp.stamp_of.__module__ == "turn", \
        "الحقيقةُ الزمنيّةُ ليست من مالكها (`tools/turn.py`)"
    assert lp.NAMING_TZ.utcoffset(None) == timedelta(hours=3), "منطقةُ التسمية من مالكها (+03)"


def test_list_prints_the_measured_list_and_the_poisons(capsys):
    """`--list` يُعلن ما سيقيسه (القائمةُ والخطواتُ والسموم) بلا نسخٍ ولا تشغيل — فالمسبارُ يُقرأ قبل أن يُشغَّل.

    **ويُعلن شجرتَه** (مقعدُ البنية · مراجعة ٦١): القائمةُ تُقرأ الآن من شجرة المنفّذ ويُقاس من نسخةٍ
    منها ⇒ فالقارئُ يجب أن يعرف أيَّ شجرةٍ يقرأ، وإلّا نسب حكمًا لورقٍ غيرِ المقيس.
    """
    assert lp.main(["--list"]) == 0
    out = capsys.readouterr().out
    for needle in ("قائمةُ الـCI", "tools/publish_guard.py", "name-stamp", str(lp.BOX),
                   str(lp.PROJ), str(lp.WORKFLOW_REL)):
        assert needle in out, f"`--list` لا يُعلن «{needle}»"


def test_a_detached_head_does_not_ask_for_a_branch_called_head():
    """**`HEAD` ليس اسمَ فرع** (حاجبُ مقعد المعايير · مراجعة ٦١ — عطبٌ في الـCI لا في القياس).

    `actions/checkout` في `pull_request` يُنتج رأسًا مفصولًا ⇒ `rev-parse --abbrev-ref HEAD` يُعيد
    `HEAD` بالحرف ⇒ `git clone --branch HEAD` يفشل بـ`128` ⇒ المسبارُ يُعيد «تعذّر قياس» (2) ⇒
    **`gate_landing` تحمرّ في كلّ طلب دمجٍ ولو كان العملُ سليمًا** (إشارةُ فشلٍ من البيئة لا من السلوك).
    والقاعدةُ الآن صريحة: `HEAD`/الفراغ ⇒ `None` ⇒ نسخةٌ بلا `--branch` ثمّ `checkout --detach <sha>`.
    """
    assert lp._branch_for_clone("HEAD") is None, "`HEAD` يُمرَّر اسمَ فرعٍ ⇒ الـCI أحمر في كلّ pull_request"
    assert lp._branch_for_clone("") is None and lp._branch_for_clone("   ") is None
    assert lp._branch_for_clone("(no branch)") is None, "حالةُ git الأخرى للرأس المفصول"
    assert lp._branch_for_clone("chore/round56-evidence") == "chore/round56-evidence", \
        "فرعٌ حقيقيّ يجب أن يُمرَّر كما هو (وإلّا قِيس فرعٌ آخر)"
    # **والوصلُ لا الوعد**: `measure` يجب أن يمرّر الناتجَ لا الاسمَ الخام.
    src = (ROOT / "tools" / "landing_probe.py").read_text(encoding="utf-8")
    assert "_clone(PROJ, dst, sha, _branch_for_clone(branch))" in src.replace("clone_branch", "_branch_for_clone(branch)") \
        or "clone_branch = _branch_for_clone(branch)" in src, \
        "`measure` ما زال يمرّر اسمَ الفرع الخام ⇒ الإصلاحُ في دالّةٍ لا تُنادى"


def _witness_gate():
    """**حارسُ §٢٧ نفسُه** (لا محاكاةً ثانية): مناطُ الرابطِ ورسائلُه من `tests/test_answer_names_witness.py`."""
    spec = importlib.util.spec_from_file_location(
        "witness_gate", ROOT / "tests" / "test_answer_names_witness.py")
    assert spec is not None and spec.loader is not None, "تعذّر تحميلُ حارس §٢٧ ⇒ لا قياس"
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_stamp_follows_the_tree_clock_and_never_lands_in_an_answer_window():
    """**R65-1 (قاسها المدقّق في مراجعة ٦٥): الختمُ بساعة الشجرة لا ساعة العدّاء.**

    والعطبُ صنفيٌّ لا حادثة: أسماءُ `handoff/` بتوقيت +03 وعدّاءُ GitHub بتوقيت UTC ⇒ ختمٌ من العدّاء
    يقع ثلاثَ ساعاتٍ قبل اسم الجواب نفسِه، فيصير الشاهدُ الاصطناعيُّ **أحدثَ حُكمٍ قبل الجواب** ويسقط
    `tests/test_answer_names_witness.py` على جوابٍ هبط صحيحًا — ويُخفي المنفّذَ محلّيًّا (ساعتُه +03).

    والضابطُ يقيس **الاتّجاهين بأسماء الجولة الحقيقيّة وبآلة الحارس نفسِها** (لا نسخةً ثانية من المنطق):
    ‹١› عطبٌ قبل الإصلاح: ختمُ العدّاء يقع في النافذة فيُسقِط الجوابَ، ‹٢› وبعد الإصلاح: الختمُ بساعة
    الشجرة ⇒ الجوابُ يمرّ، ‹٣› والأرضيّة: ختمٌ في الشجرة يتجاوز ساعة العدّاء ⇒ الشاهدُ يتجاوزه،
    ‹٤› والوصل: `measure` ينادي الدالّةَ ويُمرّر اللحظةَ نفسَها للإيداع (وإلّا فالإصلاحُ في دالّةٍ لا تُنادى).
    """
    gate = _witness_gate()
    answer = ("handoff/sulaiman/20260926-0455-REPORT-to-claude-round64-seat-verdict-closure-"
              "and-two-measured-mutations.md")
    witness = ("handoff/claude/20260926-032854-third-eye-review-64-the-instrument-counts-a-stray-digit.md")
    # `turn.stamp_of` يُطابِق من **بداية الاسم** ⇒ القياسُ بالأسماء لا بالمسارات (كما تفعل `_tree_stamps`)
    stamps = [lp.stamp_of(Path(answer).name), lp.stamp_of(Path(witness).name)]
    assert stamps == ["20260926-045500", "20260926-032854"], f"مفاتيحُ الزمن لم تُقرأ: {stamps}"
    # ساعةُ العدّاء كما تكون فعلًا: ٠٦:٤٠:٣٢ (+03) هي ٠٣:٤٠:٣٢ UTC — داخل النافذة المقيسة
    runner_clock = datetime(2026, 9, 26, 3, 40, 32, tzinfo=timezone.utc)

    # ‹١› **العطبُ قبل الإصلاح** (الاسمُ بساعة العدّاء كما كان `datetime.now().astimezone()` تحتها)
    old_key = runner_clock.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
    old_path = f"handoff/claude/{old_key}-third-eye-review-99-landing-probe.md"
    bad = gate.ungated_answers({answer: f"in-reply-to: {witness}\n"}, {answer, witness, old_path})
    assert len(bad) == 1 and "ليس أحدث" in bad[0], (old_key, bad)

    # ‹٢› **وبعد الإصلاح**: ساعةُ الشجرة (+03) ⇒ الشاهدُ يبقى أحدثَ حُكمٍ قبل الجواب
    stamp = lp._probe_stamp(runner_clock, stamps)
    assert stamp.utcoffset() == timedelta(hours=3), f"الختمُ ليس بساعة الشجرة: {stamp}"
    key = stamp.strftime("%Y%m%d-%H%M%S")
    assert key == "20260926-064032", f"الختمُ لم يُحوَّل إلى +03: {key}"
    assert gate.ungated_answers(
        {answer: f"in-reply-to: {witness}\n"},
        {answer, witness, f"handoff/claude/{key}-third-eye-review-99-landing-probe.md"}) == []

    # ‹٣› **والأرضيّة**: ختمٌ في الشجرة متأخّرٌ عن ساعة العدّاء (ساعةٌ متأخّرة · إيداعٌ مُبكَّر الاسم)
    ahead = "20260926-080000-REPORT-to-claude-later.md"
    later = lp._probe_stamp(runner_clock, stamps + [lp.stamp_of(ahead)])
    later_key = later.strftime("%Y%m%d-%H%M%S")
    assert later > datetime(2026, 9, 26, 8, 0, 0, tzinfo=lp.NAMING_TZ), later
    assert later.utcoffset() == timedelta(hours=3)
    # والقاعدةُ العامّة: لا نافذةَ (شاهد, جواب] يحلّ فيها الختمُ — بالختم الذي يخصّ كلَّ حالة
    for stamped, a, w in ((key, answer, witness), (later_key, f"handoff/sulaiman/{ahead}", witness)):
        assert not (lp.stamp_of(Path(w).name) < stamped <= lp.stamp_of(Path(a).name)), \
            f"الختمُ {stamped} يقع في نافذة {a}"
    # والساعةُ لا تعتمد على منطقة العملية: **اللحظةُ نفسها** (وإن اختلف تمثيلها) تُعطي الختمَ نفسه
    aware_local = datetime(2026, 9, 26, 6, 40, 32).astimezone()
    assert lp._probe_stamp(aware_local, []) == lp._probe_stamp(aware_local.astimezone(timezone.utc), []), \
        "الختمُ يتغيّر بتغيّر منطقة العملية بدل أن يتبع ساعة الشجرة"

    # ‹٤› **والوصل لا الوعد**: `measure` ينادي الدالّةَ، والإيداعُ يأخذ اللحظةَ نفسَها (مصدرٌ واحد).
    #     والمطابقةُ **مُطبَّعةٌ عن الفراغات** فلا يسقط الضابطُ بإعادة تنسيقٍ وكودُه سليم (نقدُ مقعد المواصفة)
    flat = "".join((ROOT / "tools" / "landing_probe.py").read_text(encoding="utf-8").split())
    assert "_probe_stamp(datetime.now().astimezone(),_tree_stamps(dst))" in flat, \
        "`measure` ما زال يختم بساعة العدّاء ⇒ الإصلاحُ في دالّةٍ لا تُنادى"
    assert "_commit(review,dst,stamp_dt)" in flat, \
        "زمنُ الإيداع لا يتبع اللحظةَ المُصلَحة ⇒ الاسمُ والإيداع يفترقان عن الشجرة"
    assert "_tree_stamps(dst)" in flat, "الأرضيّةُ تُقرأ من شجرة المنفّذ لا من الشجرة المقيسة"


def test_the_floor_covers_the_witness_scope():
    """**أرضيّةُ الختم تُغطّي نطاقَ حارس §٢٧ — ونطاقُهما مالكٌ واحد** (مقعدُ البنية · الجولة ٦٥).

    الأرضيّةُ وحدَها ما يُخرج الشاهدَ الاصطناعيَّ من نافذة `(شاهد, جواب]`، فلو وُسّع نطاقُ الحارس
    (صندوقُ مراسلةٍ ثالث) وبقي نطاقُ الأرضيّة أضيقَ ⇒ شاهدٌ يقع في نافذة جوابٍ حقيقيّ ⇒ `gate_landing`
    يُعلن «المراجعةُ لم تهبط» على شجرةٍ **سليمة** — وهو صنفُ الفشل الكاذب الذي لاحقته الجولات.
    والضابطُ: تساوي المجموعتين مع ثوابت الحارس **المستورَدة**، والنطاقُ مُشتقٌّ من مالك التخطيط.
    """
    gate = _witness_gate()
    scope = {gate.BOX.rstrip("/"), gate.WITNESS_ROOT.rstrip("/")}
    assert set(lp.BOXES) == scope, \
        f"نطاقُ الأرضيّة {set(lp.BOXES)} ≠ نطاقُ حارس §٢٧ {scope} ⇒ شاهدٌ قد يقع في نافذة جوابٍ حقيقيّ"
    assert "sorted(SIDES)" in Path(str(lp.__file__)).read_text(encoding="utf-8"), \
        "النطاقُ مكتوبٌ بيدٍ لا من مالكه (`turn.SIDES`)"


def test_the_probe_stamp_chain_under_a_utc_clock_keeps_a_recent_answer_gated(tmp_path):
    """**السلسلةُ الحقيقيّةُ بساعة عدّاء UTC** (المواصفةُ نصًّا · R65-1): «ضابطٌ يُشغّل المسبارَ بـ`TZ=UTC`
    على شجرةٍ فيها جوابٌ حديثٌ وشاهدُه، وهي الحالةُ أعلاه بعينها».

    يُبنى **شجرةٌ حقيقيّة** (صندوقا المراسلة بجوابٍ حديث وشاهده) ثم تُشغَّل **سلسلةُ الختم الحقيقيّة**:
    `_tree_stamps` على الشجرة، و`_probe_stamp` بساعة العملية الحقيقيّة بعد `time.tzset()` على `UTC`،
    ثم **حارسُ §٢٧ الحقيقيّ** على الاسم الناتج — فلا محاكاةَ للّحظة ولا نسخةَ ثانية للمنطق.

    **وحدُّه مُعلَن:** لا يُشغّل المسبارَ كاملًا (كلفتُه ١٩ ملفَّ CI لكلّ تشغيل) — وهذا يقيسه الـCI نفسُه
    حيث ساعةُ العدّاء UTC (`gate_landing`)، وقد قِيس حيًّا (`TZ=UTC … ⇒ rc=0` والختمُ ساعةَ الشجرة).
    """
    import os
    import time

    (tmp_path / "handoff" / "sulaiman").mkdir(parents=True)
    (tmp_path / "handoff" / "claude").mkdir(parents=True)
    answer = "handoff/sulaiman/20260926-160000-REPORT-to-claude-recent.md"
    witness = "handoff/claude/20260926-150000-third-eye-review-99-recent.md"
    (tmp_path / answer).write_text(f"in-reply-to: {witness}\n", encoding="utf-8")
    (tmp_path / witness).write_text("حُكمٌ حديثٌ.\n", encoding="utf-8")

    saved = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "UTC"                      # ساعةُ عدّاء GitHub
        time.tzset()
        stamp = lp._probe_stamp(datetime.now().astimezone(), lp._tree_stamps(tmp_path))
    finally:
        if saved is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = saved
        time.tzset()

    key = stamp.strftime("%Y%m%d-%H%M%S")
    assert stamp.utcoffset() == timedelta(hours=3), f"الختمُ ليس بساعة الشجرة: {stamp}"
    assert key > "20260926-160000", f"الختمُ لم يتجاوز أحدثَ اسمٍ في الشجرة: {key}"
    gate = _witness_gate()
    tree = {answer, witness, f"handoff/claude/{key}-third-eye-review-99-landing-probe.md"}
    assert gate.ungated_answers({answer: f"in-reply-to: {witness}\n"}, tree) == [], \
        "جوابٌ حديثٌ صار غيرَ محروسٍ بالشاهد ⇒ الشاهدُ الاصطناعيُّ دخل نافذته (R65-1)"
