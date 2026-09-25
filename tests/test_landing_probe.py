"""**مسبارُ الهبوط (P-11) — ضوابطُ الأداة نفسِها** (R61-2 · وأوّلُ ما أمسكه مسبارُ الهبوط قبل أن يُودَع).

ولماذا وحدةٌ مستقلّة: المسبارُ يقيس «هل تهبط مراجعة؟» بأداةٍ تقرأ الـworkflow وتبني نسخةً وتُودِع شاهدًا
اصطناعيًّا — فإن اعتلّت الأداةُ نفسُها (قائمةٌ مقروءةٌ خطأً · اسمٌ لا يوافق قاعدةَ الأسماء · شكلُ الشاهد
ناقص) صار القياسُ شهادةً كاذبةً **بلا أن يصرخ أحد**. والضوابط هنا **خفيفةٌ بلا نسخٍ ولا شبكة** (النسخُ
يُقاس في الـCI بخطوة `gate_landing` نفسِها، والسمومُ في `guard_bite_sweep` م٢١/م٢٢).

**وحدُّها مُعلَن:** لا تختبر البناءَ الفعليّ للنسخة (ذاك يقتضي clone)، ولا «هل الشكلُ الاصطناعيُّ يشبه
مراجعةً حقيقيّةً بالكامل» — الشكلُ متّفقٌ عليه بين الطرفَين (شرطُ المدقّق في مراجعة ٥٩).
"""
from __future__ import annotations

import re
import sys
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


def test_list_prints_the_measured_list_and_the_poisons(capsys):
    """`--list` يُعلن ما سيقيسه (القائمةُ والخطواتُ والسموم) بلا نسخٍ ولا تشغيل — فالمسبارُ يُقرأ قبل أن يُشغَّل."""
    assert lp.main(["--list"]) == 0
    out = capsys.readouterr().out
    for needle in ("قائمةُ الـCI", "tools/publish_guard.py", "name-stamp", lp.BOX):
        assert needle in out, f"`--list` لا يُعلن «{needle}»"
