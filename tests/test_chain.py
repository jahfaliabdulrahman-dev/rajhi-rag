"""Unit tests: chain_derive cross-page + fresh-start rules (no network)."""

from decimal import Decimal

from statement_qa.vlm_reader import chain_derive


def _r(desc, amount, balance, **kw):
    return {"movement": None if amount is None else Decimal(amount),
            "balance": None if balance is None else Decimal(balance),
            "desc": desc, "date": None, **kw}


# ---------- fresh start (no previous balance) ----------

def test_fresh_start_plain_opening_stays_opening():
    rows = chain_derive([_r("الرصيد الافتتاحى", None, "0.00"),
                         _r("تحويل FRACCT", "300.00", "300.00")])
    assert rows[0]["opening"] is True
    assert rows[1]["opening"] is False
    assert rows[1]["derived_movement"] == Decimal("300.00")
    assert rows[1]["side"] == "credit"


def test_fresh_start_missing_opening_row_keeps_movement():
    # The VLM missed the dots-zero row: the first row is a real transfer —
    # it must stay a transaction (side undecided, never guessed).
    rows = chain_derive([_r("تحويل FRACCT/10005761FR", "300.00", "300.00")])
    assert rows[0]["opening"] is False
    assert rows[0]["derived_movement"] == Decimal("300.00")
    assert rows[0]["side"] == ""
    assert rows[0]["ok"] is True


# ---------- cross-page continuity (previous closing supplied) ----------

def test_boundary_transaction_keeps_movement():
    # The owner's page-10 case: previous closing 676, transfer +1000 -> 1676.
    rows = chain_derive([_r("تحويل FRACCT", "1000.00", "1676.00")],
                        prev_balance=Decimal("676.00"))
    assert rows[0]["opening"] is False
    assert rows[0]["derived_movement"] == Decimal("1000.00")
    assert rows[0]["side"] == "credit"
    assert rows[0]["ok"] is True


def test_boundary_carry_row_is_opening():
    # Same balance as the previous closing → carried balance row.
    rows = chain_derive([_r("رصيد سابق", None, "676.00")],
                        prev_balance=Decimal("676.00"))
    assert rows[0]["opening"] is True


def test_boundary_unverifiable_amount_is_anchor():
    # delta != printed amount → cannot verify the boundary (non-consecutive
    # page or misread): anchor as opening, never fabricate a movement.
    rows = chain_derive([_r("سحب الصراف الآلي", "500.00", "1676.00")],
                        prev_balance=Decimal("676.00"))
    assert rows[0]["opening"] is True
    assert rows[0]["derived_movement"] == Decimal("0")


def test_boundary_then_chain_continues():
    rows = chain_derive([
        _r("تحويل FRACCT", "1000.00", "1676.00"),
        _r("سحب الصراف الآلي DAMMAM", "1000.00", "676.00"),
        _r("سحب الصراف الآلي", "200.00", "476.00"),
    ], prev_balance=Decimal("676.00"))
    assert rows[0]["side"] == "credit" and rows[0]["derived_movement"] == Decimal("1000.00")
    assert rows[1]["side"] == "debit" and rows[1]["derived_movement"] == Decimal("1000.00")
    assert rows[2]["balance"] == Decimal("476.00")
