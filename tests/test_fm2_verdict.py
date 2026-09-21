"""مشتقُّ حكم FM-2: **لكل رقمٍ كاتب، ولكل قائمةٍ اكتمال.**

سببُ هذا الملف: ملفُّ الحكم كُتب بيدٍ في جلسةٍ سابقة، فتغيّر فيه اسمُ مقياسٍ بمعناه
(`exact` = 386 في ملف الذراع و383 في الحكم)، وقُصّت `pages_where_v1_lost` إلى 14 من 21
فتُوجّه التتبّع إلى ثلثَي الدليل. والقاعدة: ملفٌّ يحمل قراراً على مالٍ لا يُكتب بيد.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import fm2_verdict as fv  # noqa: E402

A = ROOT / "docs" / "evidence" / "20260921-fm2-v1-arm.json"
B = ROOT / "docs" / "evidence" / "20260921-fm2-v2-arm.json"


def test_the_derivation_is_deterministic():
    """تشغيلتان بنفس المدخل ⇒ نفس البايتات: المشتقُّ دالّةٌ لا رواية."""
    v1, o1 = fv.build(A, B)
    v2, o2 = fv.build(A, B)
    assert json.dumps(v1, sort_keys=True) == json.dumps(v2, sort_keys=True)
    assert json.dumps(o1, sort_keys=True) == json.dumps(o2, sort_keys=True)


def test_the_lists_are_complete_not_truncated():
    """طولُ كل قائمة = عدّادُها المقابل — فلا تُقَصّ قائمةٌ تُوجّه تتبّعاً."""
    v, _ = fv.build(A, B)
    w = v["page_level_wins"]
    assert len(v["pages_where_a_lost"]) == w["b"], "قائمةُ ما خسره a يجب أن تساوي فوز b"
    assert len(v["pages_where_b_lost"]) == w["a"]


def test_every_number_has_a_criterion_declared():
    """المعيار يُعلن في الملف: `exact` كان يختلف بين ملفين بلا كاتبٍ يفصل."""
    v, _ = fv.build(A, B)
    for key in ("exact", "closed", "overread"):
        assert key in v["criteria"] and v["criteria"][key]
    assert v["reference_bias"].startswith("⚠️")


def test_the_overread_class_names_its_cause_and_its_impact():
    """الصنفُ يُسمّى من البيانات: أكبرُ مساهم + شرطُ الأثر (سلسلةٌ لم تُصدّقه)."""
    v, o = fv.build(A, B)
    top = o["named_cause"][0]
    assert top["page"] == 629, "أكبرُ مساهمٍ هو صفحة ملخّص الفترة"
    assert top["a_overread"] == 17 and top["a_chain_verified"] == 0, \
        "زيادةُ 17 صفّاً بلا تصديق سلسلة = إسقاطٌ عند التسليم"
    assert o["pages_with_any_overread"] >= 1
    assert "declared_unknown" in o


def test_the_spend_on_pages_outside_the_count_is_measured():
    """«لم يُصرف دولارٌ على صفحةٍ خارج العدّ» كان غير دقيق: المقياس $0.1963."""
    v, _ = fv.build(A, B)
    assert v["spend_on_pages_outside_the_count_usd"] > 0
    assert v["spend_usd"] == round(v["a_spend"] if "a_spend" in v else v["spend_usd"], 4)
