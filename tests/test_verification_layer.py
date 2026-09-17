"""The verification layer reaching the reader — and the rendering logic, tested.

Two audit findings meet here. P1-4/P1-5: the oracle's five verdicts never left
the reading tab, so a figure from a page beside a scan gap arrived looking like
a figure verified three ways — in the answer, the table and the export. P2-10:
when the tools failed, the answer fell back to a model with no tools and the
evidence panel was then filled from that model's own citations. P3-4: the code
that decides all of this lived in app.py, untested; it now lives in
`statement_qa.render` and is tested here.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_qa import render, verification  # noqa: E402


class _Res:
    def __init__(self, answer="جواب", used=None, failed=False):
        self.answer = answer
        self.used_row_nos = used or []
        self.tools_failed = failed


CHECKS = [
    {"page": 1, "status": "ok"},
    {"page": 2, "status": "ok"},
    {"page": 427, "status": "gap"},
    {"page": 172, "status": "absent"},
    {"page": 485, "status": "unchecked"},
]


def test_verdicts_translate_statuses_into_one_language():
    v = verification.verdicts_from_checks(CHECKS)
    assert v[427] == "gap" and v[172] == "absent"
    assert verification.verdict_label("gap") == "⚠ فجوة مسح"
    assert verification.verdict_label("ok") == "✓ موثّق"
    assert verification.verdict_label(None) == verification.UNPROVEN
    assert verification.verdict_label("something-new") == verification.UNPROVEN
    assert verification.unproven_pages(v) == [172, 427, 485]


def test_coverage_line_never_prints_one_number_alone():
    line = verification.coverage_line(verification.verdicts_from_checks(CHECKS))
    assert "2/5" in line and "%" in line and "مسمّى" in line


def test_caution_names_only_the_pages_actually_used():
    v = verification.verdicts_from_checks(CHECKS)
    assert verification.caution([1, 2], v) == ""          # all proven: silence
    line = verification.caution([1, 427], v)
    assert "ص427" in line and "فجوة مسح" in line and "ص1" not in line
    assert verification.caution([], v) == ""


def test_row_record_carries_the_page_verdict():
    """The export is what leaves the system — it must say what a row stands on."""
    v = verification.verdicts_from_checks(CHECKS)
    ok_row = {"page": 1, "ok": True, "kind": "txn", "side": "debit",
              "movement": 100, "balance": 900, "desc": "شراء"}
    gap_row = {"page": 427, "ok": True, "kind": "txn", "side": "credit",
               "movement": 50, "balance": 950, "desc": "إيداع"}
    assert render.row_record(1, ok_row, v)["التحقق"] == "✓ موثّق"
    assert render.row_record(2, gap_row, v)["التحقق"] == "⚠ فجوة مسح"
    unknown = {"page": 999, "ok": True, "kind": "txn", "side": "debit",
               "movement": 1, "balance": 1}
    assert render.row_record(3, unknown, v)["التحقق"] == verification.UNPROVEN


def test_row_record_keeps_direction_and_undecided_marking():
    row = {"page": 1, "ok": True, "kind": "txn", "side": "debit",
           "movement": 100, "balance": 900}
    rec = render.row_record(1, row, {})
    assert rec["مدين"] == "100.00" and rec["دائن"] == "" and rec["الحالة"] == "✓"
    undecided = dict(row, side="")
    assert render.row_record(2, undecided, {})["الحالة"] == "◌ اتجاه غير محسوم"
    bad = dict(row, ok=False)
    assert render.row_record(3, bad, {})["الحالة"] == "⚠ مشبوه"


def test_answer_text_announces_a_tool_failure_instead_of_hiding_it():
    v = verification.verdicts_from_checks(CHECKS)
    res = _Res(answer="مجموع السحوبات 12,345.00", failed=True)
    text = render.answer_text(res, {1: 1}, v)
    assert text.startswith("⚠ تعذّرت الأدوات")
    assert "لا تعتمد أي رقم فيه" in text
    assert "مجموع السحوبات" in text            # the prose is kept, labelled


def test_answer_text_cautions_when_the_answer_stands_on_unproven_pages():
    v = verification.verdicts_from_checks(CHECKS)
    res = _Res(answer="الجواب", used=[7, 94])          # row numbers
    text = render.answer_text(res, {7: 1, 94: 427}, v)  # row -> page
    assert "يشمل صفحات غير موثّقة" in text and "ص427" in text
    clean = render.answer_text(_Res(answer="الجواب", used=[7]),
                               {7: 1}, v)
    assert clean == "الجواب"                  # proven pages: no noise
    # a row number with no page mapping asserts nothing — silently, by design
    assert render.answer_text(_Res(answer="ج", used=[999]), {}, v) == "ج"


def test_evidence_mode_empties_the_panel_when_tools_failed():
    assert render.evidence_mode(_Res(failed=True)) == "none"
    assert render.evidence_mode(_Res(used=[5])) == "tools"
    assert render.evidence_mode(_Res()) == "fallback"


def test_format_warning_requires_a_measured_effect():
    """P3-5: ~11% of pages trip the style detector. Warning on all of them makes
    the one that matters indistinguishable from the seventy that do not."""
    from statement_qa import era

    fp = {"styles": {1: "old", 2: "new", 3: "new", 4: "none"},
          "transitions": [(1, 2, "old", "new")], "outliers": [3],
          "overall": "mixed", "majority": "new"}
    quiet = era.summarize_ar(fp, {})
    assert "⚠" not in quiet and "بلا أثر مقيس" in quiet
    loud = era.summarize_ar(fp, {2: "⚠ فجوة مسح"})
    assert "⚠" in loud and "ص2" in loud and "فجوة" in loud
    assert "بلا أثر مقيس" not in loud


def test_format_effects_only_names_pages_where_something_happened():
    v = verification.verdicts_from_checks(CHECKS)
    eff = verification.format_effects(v, suspect_pages=[9])
    assert eff[427] == "⚠ فجوة مسح" and eff[9] == "شكوك سلسلة"
    assert 1 not in eff and 2 not in eff          # proven pages stay silent
    assert verification.format_effects({}, []) == {}


def test_date_cell_shows_gregorian_marks_inheritance_and_keeps_raw():
    assert render.date_cell({"date": "١٤٣٤١٢٢٦ ٢٠١٣١٠٣١"}) == "2013/10/31"
    assert render.date_cell({"date": "2013/10/31",
                             "date_source": "inherited"}) == "2013/10/31*"
    assert render.date_cell({"date": ""}) == "—"
    assert render.date_cell({"date": "غير مقروء"}) == "غير مقروء"


def test_answer_refs_parses_both_citation_shapes():
    assert render.answer_refs("(صفحة 5، صفوف 10–12)") == [(5, 10, 12)]
    assert render.answer_refs("كما في صف 94") == [(None, 94, 94)]
    assert render.answer_refs("صفحة ٢، صف ٣") == [(2, 3, 3)]
    assert render.answer_refs("لا استشهاد هنا") == []
