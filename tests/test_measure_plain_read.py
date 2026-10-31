"""The plain-read comparison counts what it says it counts ($0: no network, no key).

tools/measure_plain_read.py compares a plain model answer with the ledger. Its counts become figures on the
public page, so the reading of a figure and the matching must hold on the shapes a model returns.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from measure_plain_read import compare, flagged_rows, number, rows_of  # noqa: E402


def test_a_figure_is_read_in_every_shape_a_page_or_a_model_gives():
    assert number("١٤,٣٦٥.٧٧") == Decimal("14365.77")
    assert number("١٤٬٣٦٥٫٧٧") == Decimal("14365.77")
    assert number("14,365.77 SAR") == Decimal("14365.77")
    assert number(883.29) == Decimal("883.29")
    assert number("-733.43") == Decimal("-733.43")
    assert number(None) is None and number("") is None and number(True) is None


def test_the_array_is_found_inside_fences_and_prose():
    answer = 'Here it is:\n```json\n[{"amount": "1.00", "balance": "2.00"}]\n```'
    assert rows_of(answer) == [{"amount": "1.00", "balance": "2.00"}]
    assert rows_of("no table on this page") == []
    assert rows_of("[not json]") == []


def _row(seq, movement, balance, derived=None, ok=True):
    return {"seq": seq, "page": 1, "movement": movement, "balance": balance,
            "derived_movement": derived or movement, "chain_ok": ok}


def test_matches_and_breaks_are_counted_per_figure():
    opening = {**_row(1, None, "100.00"), "opening": True}
    expected = [opening, _row(2, "10.00", "90.00"), _row(3, "5.00", "95.00")]
    returned = [{"amount": "10.00", "balance": "90.00"},
                {"amount": "5.00", "balance": "96.00"}]          # one balance misread
    counts = compare(expected, returned)
    assert counts["balances_matched"] == 1 and counts["balances_expected"] == 2   # the opening row is not asked for
    assert counts["amounts_matched"] == 2 and counts["amounts_expected"] == 2
    assert counts["breaks_inside_the_answer"] == 1                                  # 96 - 90 is not 5
    assert counts["rows_with_other_fields"] == 0
    consistent = compare(expected, [{"amount": "10.00", "balance": "90.00"}, {"amount": "6.00", "balance": "96.00"}])
    assert consistent["breaks_inside_the_answer"] == 0 and consistent["balances_matched"] == 1   # wrong, and silent
    assert compare(expected, returned + [{"amount": "1.00", "balance": "2.00", "note": "?"}])["rows_with_other_fields"] == 1


def test_a_flagged_row_says_which_figure_the_plain_answer_carried():
    expected = [_row(7, "4501.20", "9000.00", derived="4510.20", ok=False)]
    printed = flagged_rows(expected, [{"amount": "٤,٥٠١.٢٠", "balance": "9000.00"}])
    assert printed == [{"seq": 7, "page": 1, "answer_has_printed_amount": True,
                        "answer_has_balance_difference": False}]
    fixed = flagged_rows(expected, [{"amount": 4510.2, "balance": "9000.00"}])
    assert fixed[0]["answer_has_balance_difference"] is True
