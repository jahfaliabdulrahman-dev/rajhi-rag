"""Deterministic balance verification — Polars, Decimal, zero LLM.

Checks (Al Rajhi rules: no +/- signs, exact match):
  balance_ok       opening + Σcredit − Σdebit == closing
  balance_chain_ok every row's balance == prev_balance + credit − debit
  suspect_rows     rows where the chain breaks — primary suspicion is an
                   OCR digit error, not a bank error.
"""

from __future__ import annotations

import polars as pl


def verify_statement(df: pl.DataFrame) -> dict:
    if df.is_empty():
        return {"balance_ok": False, "balance_chain_ok": False,
                "n_rows": 0, "suspect_rows": [], "opening": None, "closing": None}

    d = df.with_columns(
        pl.col("debit").cast(pl.Decimal(18, 2)).fill_null(pl.lit(0, pl.Decimal(18, 2))),
        pl.col("credit").cast(pl.Decimal(18, 2)).fill_null(pl.lit(0, pl.Decimal(18, 2))),
        pl.col("balance").cast(pl.Decimal(18, 2)),
    )

    opening = d["balance"][0]
    closing = d["balance"][-1]

    # Aggregate check: opening + Σcredit − Σdebit == closing
    # (first row is the opening marker with zero movement)
    total_debit = d["debit"][1:].sum() if d.height > 1 else 0
    total_credit = d["credit"][1:].sum() if d.height > 1 else 0
    expected = opening + total_credit - total_debit
    balance_ok = expected == closing

    # Row-by-row chain: balance[i] == balance[i-1] + credit[i] − debit[i]
    prev = d.with_columns(
        pl.col("balance").shift(1).alias("_prev_bal")
    )
    bad: list[int] = []
    rows = prev.select(["_prev_bal", "debit", "credit", "balance"]).iter_rows()
    for idx, (pb, deb, cre, bal) in enumerate(rows):
        if idx == 0 or pb is None:
            continue
        if bal != pb + cre - deb:
            bad.append(idx)  # 0-based row index in df
    balance_chain_ok = not bad

    return {
        "balance_ok": bool(balance_ok),
        "balance_chain_ok": balance_chain_ok,
        "n_rows": d.height,
        "suspect_rows": bad,
        "opening": opening,
        "closing": closing,
    }
