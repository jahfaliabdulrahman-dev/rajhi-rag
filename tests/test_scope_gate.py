"""The scope gate: deterministic answers, and no real question swallowed.

Gate 4 exists because three measured defects shared one cause — a question whose
premise lies outside the document was handed to a model with tools, and the
model did the most helpful-looking thing: a refusal that varied between runs, a
figure for a year the statement does not cover, a confirmation of an amount that
does not exist.

The in-scope tests below matter MORE than the refusal tests: a gate that
swallows a real question is worse than the defects it was built for.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_qa import render, scope  # noqa: E402

YEARS = {2025, 2026}
AMOUNTS = frozenset({Decimal("1000.00"), Decimal("250.00"), Decimal("100.00")})
MAX_PAGE = 629


def _kind(q, years=YEARS, max_page=MAX_PAGE, amounts=AMOUNTS):
    return scope.classify(q, years, max_page, amounts).kind


# ── out of scope: another bank, or data a statement never carries ─────────

def test_another_bank_is_refused_deterministically():
    s = scope.classify("كم رصيد حسابي في بنك الرياض؟", YEARS, MAX_PAGE, AMOUNTS)
    assert s.kind == "out_of_scope" and "الرياض" in s.reason
    assert scope.REFUSAL in s.answer
    # the same question, twice, must give the same answer — the defect was
    # that it did not: one run refused, the next answered with a Rajhi balance
    again = scope.classify("كم رصيد حسابي في بنك الرياض؟", YEARS, MAX_PAGE, AMOUNTS)
    assert again.answer == s.answer


def test_naming_our_own_bank_is_not_out_of_scope():
    """«بنك الراجحي» is the bank this statement IS — refusing it would be the
    gate swallowing the most ordinary question there is."""
    assert _kind("كم رصيد حسابي في بنك الراجحي؟") == "in_scope"
    assert _kind("ما آخر رصيد في كشف الراجحي؟") == "in_scope"


def test_personal_data_is_refused():
    for q in ("ما هو رقم جوال صاحب الحساب؟", "أعطني رقم الهوية",
              "ما عنوان صاحب الحساب؟"):
        s = scope.classify(q, YEARS, MAX_PAGE, AMOUNTS)
        assert s.kind == "out_of_scope" and scope.REFUSAL in s.answer, q


# ── no such data: answered from the statement's own facts ────────────────

def test_a_year_outside_the_statement_is_answered_without_a_model():
    s = scope.classify("كم مجموع الحركات في عام ٢٠١٩؟", YEARS, MAX_PAGE, AMOUNTS)
    import re

    assert s.kind == "no_such_data" and "2019" in s.answer  # echoed in latin
    assert "2025–2026" in s.answer          # names the period it DOES cover
    # and states no figure of its own: no decimal amount anywhere in the text
    assert re.search(r"\d+\.\d\d", s.answer) is None, s.answer


def test_a_year_inside_the_statement_passes_through():
    assert _kind("كم مجموع الحركات في 2026؟") == "in_scope"


def test_a_page_beyond_the_file_is_named():
    s = scope.classify("ماذا يوجد في الصفحة ٧٠٠؟", YEARS, MAX_PAGE, AMOUNTS)
    assert s.kind == "no_such_data" and "629" in s.answer
    assert _kind("ماذا في الصفحة 12؟") == "in_scope"


def test_an_absent_amount_is_answered_from_the_rows():
    s = scope.classify("هل يوجد تحويل بمبلغ 987,654.32 ريال؟",
                       YEARS, MAX_PAGE, AMOUNTS)
    assert s.kind == "no_such_data" and "987,654.32" in s.answer
    assert scope.REFUSAL in s.answer


def test_an_existing_amount_passes_through_to_the_tools():
    assert _kind("هل يوجد تحويل بمبلغ 1000؟") == "in_scope"


def test_thresholds_are_not_existence_questions():
    """The false-gating guard: «more than 500» names a threshold, and until a
    rule existed for it the gate answered «no such amount» — swallowing a real
    question, the one failure mode worse than the defects it prevents."""
    for q in ("كم الحركات التي تتجاوز 500؟", "هل يوجد تحويل بأكثر من 50000؟",
              "ما الحركات بين 100 و 900؟"):
        assert _kind(q) == "in_scope", q


# ── routing a compound question (measured case F) ────────────────────────

def test_the_account_question_is_never_read_as_sabb_bank():
    """The auditor's six sentences, verbatim. «ساب» sits inside «حِساب», and
    containment matching refused the question this project exists to answer."""
    from statement_qa.scope import classify

    for q in ("ما رصيد الحساب؟", "متى فُتح الحساب؟",
              "كم عدد حركات هذا الحساب؟", "كم رصيد حسابي في بنك الراجحي؟",
              "هل توجد فاتورة جوال؟", "كم مجموع السحوبات من هذا الحساب؟"):
        assert classify(q, (), None, frozenset()).kind == "in_scope", q


def test_a_real_other_bank_still_refuses():
    """…without weakening the rule it was built for: widen nothing."""
    from statement_qa.scope import classify

    for q in ("كم رصيد حسابي في بنك الرياض؟", "هل عندي حساب في ساب؟",
              "رصيد حسابي في الأهلي", "ما رصيد حسابي في بنك البلاد؟"):
        sc = classify(q, (), None, frozenset())
        assert sc.kind == "out_of_scope", q
        assert "لا يحتوي أي بيانات" not in sc.answer   # the old claim was a lie


def test_a_city_name_is_not_a_bank_without_the_word_bank():
    """«الرياض» in an ATM description is a place, not a rival branch."""
    from statement_qa.scope import classify

    assert classify("كم سحب من الصراف في الرياض؟", (), None,
                    frozenset()).kind == "in_scope"
    assert classify("كم سحب من الصراف في بنك الرياض؟", (), None,
                    frozenset()).kind == "out_of_scope"


def test_a_compound_question_splits_into_its_two_asks():
    from statement_qa.qa import split_compound

    parts = split_compound("كم مجموع الحوالات الواردة من شركة أ، وكم عدد "
                           "الحوالات من مؤسسة غير مذكورة في الكشف؟")
    assert len(parts) == 2
    assert parts[0].startswith("كم مجموع")
    assert parts[1].startswith("كم عدد")      # the conjunction is not carried


def test_a_conjunction_inside_a_phrase_is_not_a_split_point():
    """«المدين والدائن» is one thing; splitting it would invent a question."""
    from statement_qa.qa import split_compound

    for q in ("ما مجموع المدين والدائن؟", "هل يوجد أثر مقاصة في الكشف؟",
              "كم عدد الحركات في الصفحة 12؟"):
        assert split_compound(q) == [q], q


def test_numeric_questions_require_a_tool_and_others_do_not():
    from statement_qa.qa import needs_tools

    assert needs_tools("كم مجموع السحوبات من الصراف الآلي؟")
    assert needs_tools("ما إجمالي مدين الصفحة 5؟")
    assert not needs_tools("هل يوجد أثر مقاصة في الكشف؟")
    assert not needs_tools("اشرح لي شكل الكشف")


def test_an_ungrounded_numeric_answer_is_labelled_and_unpanelled():
    """A number recalled from the chunks is not a number computed from the
    statement — the reader must see which one they are reading."""
    class _Res:
        answer = "المجموع 12,345.00"
        used_row_nos = []
        tools_failed = False
        ungrounded = True

    text = render.answer_text(_Res(), {}, {})
    assert text.startswith("⚠ سؤال رقمي بلا أي استدعاء أداة")
    assert "12,345.00" in text                      # kept, labelled
    assert render.evidence_mode(_Res()) == "none"   # and no evidence shown


# ── the gate stays open when it cannot prove anything ────────────────────

def test_without_data_the_gate_refuses_only_what_needs_no_data():
    assert scope.classify("كم مجموع السحوبات؟", (), None, frozenset()).kind == "in_scope"
    assert scope.classify("ما هو رقم جوال صاحب الحساب؟", (), None,
                          frozenset()).kind == "out_of_scope"


def test_extractors_handle_both_digit_scripts():
    assert scope.years_in("عام ٢٠١٩ و 2020") == [2019, 2020]
    assert scope.page_in("الصفحة ٧٠٠") == 700
    assert Decimal("987654.32") in scope.amounts_in("بمبلغ 987,654.32 ريال")
    assert scope.amounts_in("لا أرقام هنا") == []
