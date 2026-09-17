"""Unit tests: date carry-forward for the table/Excel export.

Al Rajhi prints the date ONCE per group; sibling rows ship a blank cell, so an
export without carry-forward loses the transaction date. The fill must be
complete AND honest: every inherited cell is marked (`date_source`), and no
date is ever invented for an opening/carry/boundary line.
"""

from statement_qa.vlm_reader import fill_missing_dates


def _txn(date: str, side: str = "debit", movement: str = "10.00") -> dict:
    return {"date": date, "kind": "txn", "side": side, "movement": movement}


def test_inherits_last_printed_date_and_marks_origin():
    rows = [_txn("٢٠٢٤/١١/١٨"), _txn(""), _txn(""), _txn("٢٠٢٤/١١/١٩"),
            _txn("")]
    assert fill_missing_dates(rows) == 3
    assert [r["date"] for r in rows[:3]] == ["٢٠٢٤/١١/١٨"] * 3
    assert rows[0]["date_source"] == "printed"
    assert rows[1]["date_source"] == "inherited"
    assert rows[3]["date_source"] == "printed"
    assert rows[4]["date_source"] == "inherited"


def test_never_invents_a_date_for_opening_or_boundary_rows():
    rows = [
        {"date": "", "kind": "opening", "balance": "100.00"},
        {"date": "", "kind": "txn", "side": "carry", "boundary": "carry",
         "movement": "100.00"},
        _txn(""),
    ]
    assert fill_missing_dates(rows) == 0
    assert all(not r.get("date") for r in rows)
    assert all("date_source" not in r for r in rows)


def test_no_previous_date_leaves_rows_untouched():
    rows = [_txn(""), _txn("")]
    assert fill_missing_dates(rows) == 0
    assert all(not r.get("date") for r in rows)


def test_already_dated_rows_are_labelled_printed_only():
    rows = [_txn("٢٠٢٤/١١/١٨"), _txn("٢٠٢٤/١١/١٨")]
    assert fill_missing_dates(rows) == 0
    assert all(r["date_source"] == "printed" for r in rows)
