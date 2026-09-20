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
    """الختم يوافق الكود: الافتراضي v2 — والتلقينة v1 تُسمّى باسمها."""
    assert reader_stamp()["prompt_version"] == "v2"
    assert reader_stamp(FRONTIER_PROMPT_V2)["prompt_version"] == "v2"
    assert reader_stamp(FRONTIER_PROMPT)["prompt_version"] == "v1"
    assert reader_stamp(PROMPTS["v2"])["prompt_version"] == "v2"


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
