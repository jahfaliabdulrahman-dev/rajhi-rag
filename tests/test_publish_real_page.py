"""The real page's redaction works by rule, on shapes a statement gives ($0: made-up text, no statement).

tools/publish_real_page.py publishes one page of a real statement (docs/SHOWCASE_PLAN.md section 6). Its text must
hide what its picture hides: a transfer's parties, a bracketed reference, a masked card number, whatever digits the
reader wrote them in; and nothing is written while one of the owner's private identity patterns survives.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from publish_real_page import HIDDEN, extract, redact, surviving_patterns  # noqa: E402


def test_a_transfer_keeps_its_first_line_only():
    text, hidden = redact("تحويل وارد\nمن حساب فلان الفلاني\nمرجع ABC")
    assert text == f"تحويل وارد\n{HIDDEN}" and hidden == 1
    assert redact("تحويل")[0] == "تحويل", "سطرٌ واحدٌ لا أطرافَ تحته"


def test_references_and_masked_cards_are_hidden_in_every_digit_system():
    for digits in ("12345678", "١٢٣٤٥٦٧٨", "۱۲۳۴۵۶۷۸"):   # past the rule's six, short of the guard's ten
        text, _ = redact(f"شراء ({digits}-{digits} 8) STORE, CITY")
        assert digits not in text and f"({HIDDEN})" in text and "STORE, CITY" in text
    for card in ("405400******1234", "٤٠٥٤٠٠******١٢٣٤", "۴۰۵۴۰۰******۱۲۳۴"):
        text, n = redact(f"خصم بطاقة\npayment - {card}")
        assert card not in text and n == 1


def test_a_footer_without_a_verdict_is_not_labelled_cumulative():
    doc = {"source": "s.pdf", "source_sha256": "0" * 64, "n_pages": 2, "read_on": "2026-10-31",
           "rows": [], "footers": {"1": {"verdict": "absent", "basis": ""}, "2": {"verdict": "ok", "basis": ""}}}
    assert extract(doc, 1)[0]["footer"] == {"verdict": "absent", "basis": ""}
    assert extract(doc, 2)[0]["footer"] == {"verdict": "ok", "basis": "cumulative"}


def test_a_surviving_private_pattern_is_counted_never_shown(tmp_path):
    patterns = tmp_path / "patterns.txt"
    patterns.write_text("[anywhere]\nSA00TEST\n[header]\nاسمٌ للاختبار\n", encoding="utf-8")
    assert surviving_patterns("نصٌّ نظيف", patterns) == 0
    assert surviving_patterns("فيه اسمٌ للاختبار وSA00TEST", patterns) == 2
