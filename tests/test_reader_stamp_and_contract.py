"""Tests for the reader stamp (FMEA FM-1), the reasoning contract, and the
digital path's disclosure — three things whose failure is silent.

  · a corpus read by two readers and published under one number looks exactly
    like a clean corpus until someone asks who read it;
  · a retry budget that lives in a dependency's default is not a budget;
  · a digital file's internal consistency is not provenance, and a measurement
    that does not say so invites the reader to transfer more trust than earned.

All three are checked here without touching a real statement.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from statement_qa.vlm_reader import (  # noqa: E402
    FRONTIER_PROMPT, FRONTIER_PROMPT_V2, PROMPTS, reader_stamp, stamp_conflict,
)
from tools.probe_digital_path import non_witnesses  # noqa: E402


# ── FM-1: ختم القارئ ──────────────────────────────────────────────────────
def test_the_default_stamp_names_the_prompt_the_code_actually_uses():
    """الختم يوافق الكود — **ومن نصّ التعليمات لا من اسمٍ ثابت (R74-5).**

    الصنفُ الذي كان صامتًا: تعليمةٌ «مجمّدة» عُدِّلت 2026-09-19 (أُضيف إقصاءُ الرصيد الافتتاحي) وبقي
    ختمُها الاسمَ `v2` ⇒ الكوربوسُ المقروءُ بالتعليمتين حمل ختمًا واحدًا، والاستئنافُ مرّ على قراءةٍ
    بتعليمةٍ أخرى. الآن الختمُ بصمةُ النصّ: تعديلُ حرفٍ ⇒ ختمٌ آخر.
    """
    import hashlib

    v2 = reader_stamp()["prompt_version"]
    assert v2 == reader_stamp(FRONTIER_PROMPT_V2)["prompt_version"] == \
        reader_stamp(PROMPTS["v2"])["prompt_version"], "الافتراضي و`PROMPTS['v2']` ختمٌ واحد"
    assert v2.startswith("v2:"), f"الختمُ يسمّي العائلة ثم بصمةَ نصّها: {v2!r}"
    assert v2.split(":", 1)[1] == hashlib.sha256(
        FRONTIER_PROMPT_V2.encode("utf-8")).hexdigest()[:8], "البصمةُ ليست بصمةَ النصّ المستعمل"
    assert reader_stamp(FRONTIER_PROMPT)["prompt_version"].startswith("v1:")
    assert reader_stamp(FRONTIER_PROMPT_V2 + ".")["prompt_version"] != v2, \
        "تعليمةٌ معدّلةٌ بنقطةٍ واحدة حملت الختمَ نفسه ⇒ تعديلُ «المجمّد» يمرّ صامتًا (R74-5)"


def test_the_opening_balance_is_a_row_not_a_summary_line():
    """R74-1: الرصيدُ الافتتاحي **يحمل رصيداً مطبوعاً** ⇒ يُدرَج في rows (مرساةُ سلسلة الصفحة الأولى).

    إقصاؤه (تعليمةُ 2026-09-19) أخرجته من القراءة ⇒ الصفحةُ ١ بلا رصيدٍ تبدأ منه ⇒ مجموعُها لا يطابق
    تذييلَها ⇒ «غير قابلة للتحقق» (ولا تذييلَ قبلها لتُقارَن به) ⇒ تغطيةُ الفوتر ٩ من ١٠ ⇒ البوّابةُ تسقط.
    """
    # قائمةُ الإقصاء المسمّاة (بين «مثل» و«؛») لا تحمل الرصيدَ الافتتاحي
    excluded = FRONTIER_PROMPT_V2.split("مثل", 1)[1].split("؛", 1)[0]
    assert "الرصيد الافتتاحي" not in excluded, "الرصيدُ الافتتاحي عاد إلى قائمة الإقصاء (R74-1)"
    # والاستثناءُ مكتوبٌ صريحًا لا مفهومًا
    assert "يُدرَج في rows" in FRONTIER_PROMPT_V2, "لا سطرَ صريحًا يُدرج الرصيدَ الافتتاحي في rows"
    # **ومُقيَّدٌ بموضعه (R75-1 · قاسه المدقّق من القراءة المحفوظة للصفحة ٦٢٩):** صفحةُ الملخّص الختامية فيها
    # ١٧ سطرًا بلا رصيد، وأحدُها سطرُ «رصيد افتتاحي» — فاستثناءٌ غيرُ مُقيَّدٍ بموضعه يجرّ رصيداً خاطئاً
    # إلى السلسلة ويكسر الصفحةَ الأخيرة. فيُشترط نصُّ البراءة لمربّع الملخّص.
    assert "مربّع الملخّص" in FRONTIER_PROMPT_V2, (
        "الاستثناءُ غيرُ مُقيَّدٍ بموضعه: لا نصَّ يُبرّئ مربّعَ الملخّص/الإجماليات (R75-1)")


def test_an_unknown_prompt_is_stamped_by_its_fingerprint_not_by_a_guess():
    stamp = reader_stamp("اقرأ الصفحة كما هي")
    assert stamp["prompt_version"].startswith("custom:")
    other = reader_stamp("اقرأ الصفحة كما هي.")
    assert stamp["prompt_version"] != other["prompt_version"], \
        "تلقينتان مختلفتان تحملان الختم نفسه ⇒ الكوربوس المختلط يمرّ"


def test_resume_is_refused_across_readers_and_legacy_is_declared():
    current = {"model": "m1", "prompt_version": "v2"}
    assert stamp_conflict({"model": "m1", "prompt_version": "v2"}, current) is None
    assert "stamp-mismatch" in stamp_conflict(
        {"model": "m2", "prompt_version": "v2"}, current)
    assert "stamp-mismatch" in stamp_conflict(
        {"model": "m1", "prompt_version": "v1"}, current)
    # نقطة قديمة بلا ختم: تُعلن ولا تُعاد قراءتها (إعادةُ دفع ثمنها إتلاف)
    assert stamp_conflict({"pg": 1, "raw_rows": []}, current) == "plain_legacy"
    assert stamp_conflict(None, current) == "checkpoint-unreadable"


# ── العقد: السقف رقمٌ في العقد لا ثابتٌ في الكود ──────────────────────────
def test_the_retry_budget_is_a_number_in_the_contract():
    contract = json.loads((PROJ / "profiles" / "al-rajhi.json").read_text(encoding="utf-8"))
    reasoning = contract.get("reasoning")
    assert reasoning, "العقد لا يحمل سقف الإعادات ⇒ الكلفة بلا ميزانية معلنة"
    assert isinstance(reasoning["retry_budget"], int) and reasoning["retry_budget"] > 0
    assert isinstance(reasoning["recursion_limit"], int) and reasoning["recursion_limit"] > 0
    # القيمة التي وُجدت في الحزمة المثبّتة تُسجَّل بجانب قرارنا، فيُعرف الفرق
    assert reasoning["measured_default_without_cap"] == 10007


# ── المسار الرقمي: ما لا يشهد به ─────────────────────────────────────────
def test_the_digital_measurement_declares_what_it_does_not_witness():
    facts = non_witnesses()
    assert len(facts) >= 4, "إفصاحٌ أقصر من أن يمنع نقل الثقة"
    joined = " ".join(facts)
    assert "التوقيع" in joined or "توقيع" in joined
    assert "داخل الملف" in joined, "أخطر ما يُخفى: أن الفحوص داخلية المنشأ"
    assert any("لا" in f for f in facts)
