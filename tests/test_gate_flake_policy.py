"""سياسةُ اللاحتميّة في الفحص الشامل: دالّةٌ خالصةٌ تُقاس بلا خدمةٍ ولا شبكةٍ ولا نموذج.

**ولماذا وحدةٌ مستقلّة؟** لأنّ هذه السياسةَ تُحدّد لونَ البوّابة عند كلّ إقلاعٍ عبر قراءةٍ غيرِ حتميّة —
فهي منطقُ حكمٍ لا تفصيلًا؛ والقاعدةُ في `tools/qa_gate.py::decide_two_runs`. والوحدةُ خفيفةٌ
(ستاندرد + `tools.qa_gate`) فتُدرَج في الـCI الخفيف، ولا تعتمد على خدمةٍ حيّة.

**ولا تُقرأ السياسةُ من نصٍّ عامّ:** الأساسُ الذي تُقاس عليه هو `_run` أدناه — عدّادٌ صريحٌ لكلّ قراءة.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.qa_gate import decide_two_runs  # noqa: E402


def _run(total: int = 104, clean: int = 104, ids: tuple[str, ...] = ()) -> dict:
    """قراءةٌ واحدةٌ كما تُقاس: العدّادُ الثلاثيّ + هويّةُ الصفوف المشبوهة."""
    return {"total": total, "clean": clean, "susp": len(ids), "ids": list(ids)}


def test_a_clean_first_read_passes_and_costs_one_read():
    ok, why = decide_two_runs(_run())
    assert ok, why
    assert "الأولى" in why, why


def test_a_lone_dirty_read_is_never_a_pass_by_itself():
    """القراءةُ الواحدةُ المشبوهةُ لا تكون حكمًا — الحكمُ يحتاج قراءةً ثانية."""
    ok, why = decide_two_runs(_run(clean=103, ids=("10:41",)))
    assert not ok, "قراءةٌ واحدةٌ غيرُ نظيفةٍ مُرّرت"
    assert "بلا محاولةٍ ثانية" in why, why


def test_repeating_suspect_names_a_deterministic_defect():
    """عطبٌ حتميّ: المعرّفُ نفسُه يعود في القراءتين ⇒ أحمر **باسمه**، لا «شكوك». """
    ok, why = decide_two_runs(_run(clean=103, ids=("10:41", "9:7")),
                              _run(clean=103, ids=("9:7",)))
    assert not ok, "عطبٌ متكرّرٌ مُرّر"
    assert "تتكرّر" in why and "9:7" in why, why


def test_the_decisive_rule_is_no_clean_read_no_acquittal():
    """القاعدةُ الحاسمة: تقاطعٌ فارغٌ لا يعني براءةً ما دامت لا قراءةَ نظيفةَ واحدة.

    (والتقاطعُ **تشخيصيٌّ** لا حاسم: أيُّ تقاطعٍ يستلزم أنّ الثانيةَ غيرُ نظيفةٍ حتمًا.)
    """
    ok, why = decide_two_runs(_run(clean=103, ids=("10:41",)),
                              _run(clean=102, ids=("10:42", "9:7")))
    assert not ok, "قراءتان غيرُ نظيفتين مُرّرتَا لمجرّد اختلاف المعرّفات"
    assert "لا قراءةَ نظيفة" in why, why


def test_a_flaky_read_passes_declared_when_one_read_is_clean():
    ok, why = decide_two_runs(_run(clean=103, ids=("10:41",)), _run())
    assert ok, why
    assert "غيرُ حتميّة" in why, why


def test_a_lost_row_is_not_clean_even_with_zero_suspects():
    """صفرُ شكوكٍ مع صفٍّ مفقودٍ من العدّ = عطبُ عدّ ∎ لا نظافة."""
    ok, _ = decide_two_runs(_run(total=104, clean=103, ids=()))
    assert not ok, "صفٌّ مفقودٌ مع صفرِ شكوكٍ عُدَّ نظافة"
