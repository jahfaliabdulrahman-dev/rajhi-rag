"""The pages that could not be checked alone — checked between their neighbours.

Six pages of the certified statement carry no readable totals row, so the
per-page oracle can only say «absent» or «unchecked». That is an honest answer
to the wrong question: printed totals are cumulative-to-date, so a span between
two READABLE frames is still accountable, as a whole.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / "tools"))

from statement_qa.group_check import verify_groups  # noqa: E402


def _page(n, own_d, own_c, frame_d=None, frame_c=None, balance=None):
    usable = frame_d is not None and frame_c is not None
    return {"page": n, "usable": usable,
            "own_debits": None if own_d is None else Decimal(str(own_d)),
            "own_credits": None if own_c is None else Decimal(str(own_c)),
            "own_balance": None if balance is None else Decimal(str(balance)),
            "frame_debits": Decimal(str(frame_d)) if usable else None,
            "frame_credits": Decimal(str(frame_c)) if usable else None,
            "frame_balance": Decimal(str(balance or 0)) if usable else None}


def _span(groups, pages):
    for g in groups:
        if g.get("bracket") and set(g["pages"]) == set(pages):
            return g
    raise AssertionError(f"no span covering {pages}: {groups}")


def test_a_span_covering_a_frameless_page_is_verified_by_its_brackets():
    """Page 2 has no frame; its movements are still accountable."""
    pages = [_page(1, 10, 5, 100, 200, balance=110),
             _page(2, 7, 3, None, None),
             _page(3, 4, 1, 111, 204, balance=125)]
    g = _span(verify_groups(pages), [2, 3])
    assert g["status"] == "verified", g
    assert g["covers_unreadable"] is True
    assert g["diff_debits"] == "0" and g["diff_credits"] == "0"


def test_a_span_whose_difference_is_not_explained_reports_the_money():
    """The gap the missing sheets left is money, not a shrug."""
    pages = [_page(1, 10, 5, 100, 200, balance=110),
             _page(2, 7, 3, None, None),
             _page(3, 4, 1, 511, 204, balance=125)]      # +400 unexplained
    g = _span(verify_groups(pages), [2, 3])
    assert g["status"] == "mismatch"
    assert g["diff_debits"] == "-400"          # got − want
    assert g["balance_ok"] is True             # balances still line up


def test_a_span_with_no_frame_after_it_is_undecidable_not_guessed():
    """The last page has nothing to be bracketed against — and says so."""
    pages = [_page(1, 10, 5, 100, 200, balance=110),
             _page(2, 7, 3, None, None)]
    groups = verify_groups(pages)
    tail = [g for g in groups if g["status"] == "undecidable"]
    assert tail and tail[0]["pages"] == [2]
    assert "لا إطار مقروء بعد" in tail[0]["why"]


def test_the_app_entry_point_maps_the_oracle_output_to_the_identity():
    """from_checks() is what the app's banner calls: per-page verdicts + rows in,
    the pages it may now call verified out. The rows carry side="debit"/"credit"
    and the slots are plural — that off-by-a-word once threw KeyError."""
    from decimal import Decimal as D

    from statement_qa.group_check import from_checks

    checks = [{"page": 1, "status": "ok", "own": {"debits": D("10"), "credits": D("5"), "balance": D("105")},
               "totals": {"debits": D("10"), "credits": D("5"), "balance": D("105")}},
              {"page": 2, "status": "absent", "own": {"debits": D("7"), "credits": D("3"), "balance": D("109")},
               "totals": {"debits": D("17"), "credits": D("8"), "balance": D("109")}},
              {"page": 3, "status": "ok", "own": {"debits": D("4"), "credits": D("1"), "balance": D("112")},
               "totals": {"debits": D("21"), "credits": D("9"), "balance": D("112")}}]
    rows = [{"page": 2, "kind": "txn", "movement": D("7"), "side": "debit", "balance": D("109")},
            {"page": 2, "kind": "txn", "movement": D("3"), "side": "credit", "balance": D("109")}]
    assert from_checks(checks, rows) == [2, 3]


def test_a_frame_we_could_not_reconcile_never_brackets_another_page():
    """A mismatched frame is not evidence — it must not certify its neighbour."""
    from decimal import Decimal as D

    from statement_qa.group_check import from_checks

    checks = [{"page": 1, "status": "mismatch", "own": {"debits": D("10"), "credits": D("5"), "balance": D("105")},
               "totals": {"debits": D("10"), "credits": D("5"), "balance": D("105")}},
              {"page": 2, "status": "absent", "own": {}, "totals": {}},
              {"page": 3, "status": "ok", "own": {"debits": D("4"), "credits": D("1"), "balance": D("112")},
               "totals": {"debits": D("21"), "credits": D("9"), "balance": D("112")}}]
    assert from_checks(checks, []) == []


def test_a_span_that_hides_nothing_is_not_reported_as_new_work():
    """Two readable frames with readable pages between them prove nothing new."""
    pages = [_page(1, 10, 5, 100, 200, balance=110),
             _page(2, 7, 3, 107, 203, balance=120),
             _page(3, 4, 1, 111, 204, balance=125)]
    for g in verify_groups(pages):
        if g.get("bracket"):
            assert g["covers_unreadable"] is False
