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
    """«لم يُصرف دولارٌ على صفحةٍ خارج العدّ» كان غير دقيق: المقياس $0.1963.

    ⚠️ **وكان في هذا الاختبار تأكيدٌ طائويٌّ** (`a_spend` غير موجود في المخرج ⇒
    السطر يُختصر إلى `x == round(x, 4)` فلا يفشل أبداً). والمدقّق أمسكه. فصار
    الرقمُ **يُشتقّ من ملفَّي الذراعين داخل الاختبار** ويُقابَل — فإن انكسر المشتقّ
    انكسر الاختبار.
    """
    v, _ = fv.build(A, B)
    a_arm = json.loads(A.read_text(encoding="utf-8"))
    b_arm = json.loads(B.read_text(encoding="utf-8"))
    # نفسُ صيغة الأداة المعلنة: كلُّ صفحةٍ سقط أحدُ ذراعيها ⇒ كلفةُ **الذراعين**
    # (الصفحةُ قيست مرتين ثُمّ أُسقطت ⇒ الصرفُ كله مهدور).
    a_per = {p["page"]: p for p in list(a_arm["prompts"].values())[0]["per_page"]}
    b_per = {p["page"]: p for p in list(b_arm["prompts"].values())[0]["per_page"]}
    recomputed = round(sum(float(a_per[g].get("cost_usd") or 0.0)
                           + float(b_per[g].get("cost_usd") or 0.0)
                           for g in set(a_per) | set(b_per)
                           if a_per[g].get("error") or b_per[g].get("error")), 4)
    assert recomputed > 0, "يجب أن يكون هناك صرفٌ على صفحاتٍ فيها خطأ"
    assert v["spend_on_pages_outside_the_count_usd"] == recomputed, \
        "المشتقُّ يساوي المجموع المحسوب من ملفَّي الذراعين"
    assert v["spend_usd"] == round(a_arm["spend_usd"] + b_arm["spend_usd"], 4)


def test_the_bias_sentence_is_derived_not_declared(tmp_path):
    """⚠️ كانت الجملةُ **مكتوبةً بيد** في ملفٍّ مشتقّ — وهي وحدها كانت الخطأ:
    قالت «المرجع كتبته v2» والكوربوس يقول `reader = None` و629 بلا ختم.

    فالسمّ: نسبٌ مجهول ⇒ «مجهول» صريحاً · ونسبٌ معلن ⇒ يُسمّى القارئ. ولو عادت
    الجملةُ تُكتب بيد لسقط هذا الاختبار.
    """
    def run_with(prov: dict | None) -> dict:
        run = tmp_path / "run"
        run.mkdir(parents=True, exist_ok=True)
        (run / "slice_report.json").write_text(
            json.dumps({"corpus_provenance": prov} if prov is not None else {},
                       ensure_ascii=False), encoding="utf-8")
        return fv._provenance(run)

    unknown = fv.bias_sentence(run_with(None))
    assert "مجهول" in unknown and "v2" not in unknown, unknown
    named = fv.bias_sentence(run_with({"reader": {"model": "some-model",
                                                  "prompt_version": "v9"}}))
    assert "some-model/v9" in named, named
    legacy = fv.bias_sentence(run_with({"reader": None, "legacy_unstamped_pages": 629}))
    assert "629" in legacy, "العدّاد المعلن يُذكر مع الجهل"


def test_the_verdict_is_derived_from_the_runs_own_provenance():
    """الملفُ المُلتزم يقول «مجهول» — لأن التشغيلة تقول ذلك، لا لأننا ظنّناه."""
    v, _ = fv.build(A, B)
    assert v["reference_provenance"]["source"].endswith("corpus_provenance")
    assert v["reference_provenance"]["reader"] is None
    assert "مجهول" in v["reference_bias"]
