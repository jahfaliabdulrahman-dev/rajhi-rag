"""Cross-page anchor verification + boundary-row recovery.

The owner's mechanism, formalized (proven on real pages 2→3):
  1. last balance of page N = chain anchor for page N+1.
  2. first-balance gap at a boundary = ONE missing bridging row whose
     movement equals the gap.
  3. recovery: targeted top-of-page VLM re-read; the row matching the gap
     amount is inserted; the chain closes EXACT.

Also: the recurring '119.00/11900' line at page top is the PAGE HEADER
(period/limit line), NOT the running balance — never treat it as opening.
The true opening of page N is derived from page N-1's closing.
"""

from __future__ import annotations

from decimal import Decimal

from statement_qa.vlm_reader import chain_derive, read_rows_vlm


def verify_anchors(pages_rows: dict[int, list[dict]]) -> dict:
    """pages_rows: {page_no: chain_derive(rows)} → continuity report.

    Returns {ok: [...], gaps: [(page, gap_amount)]}. A gap at page N's
    first txn means one bridging row was missed at the page top.
    """
    report: dict = {"ok": [], "gaps": []}
    prev_last: Decimal | None = None
    prev_page: int | None = None
    for pg in sorted(pages_rows):
        txns = [r for r in pages_rows[pg] if not r.get("opening")
                and r.get("balance") is not None]
        if not txns:
            continue
        first_bal = txns[0]["balance"]
        if prev_last is not None and first_bal != prev_last:
            report["gaps"].append((pg, first_bal - prev_last))
        else:
            report["ok"].append(pg)
        prev_last = txns[-1]["balance"]
        prev_page = pg
    return report


def recover_boundary_rows(pages_rows: dict[int, list[dict]],
                          page_images: dict[int, str],
                          max_pages: int | None = None) -> list[dict]:
    """Re-read page tops where a boundary gap exists; insert recovered rows.

    Returns NEW rows [{page, balance, movement, recovered: True}] for each
    gap closed. Caller re-runs the chain after insertion.
    """
    report = verify_anchors(pages_rows)
    recovered: list[dict] = []
    for pg, gap in report["gaps"]:
        if max_pages is not None and len(recovered) >= max_pages:
            break
        img = page_images.get(pg)
        if not img:
            continue
        rows = read_rows_vlm(img)  # full page; top rows included
        aud = chain_derive(rows)
        # find a row whose printed movement matches |gap|
        for r in aud:
            if r.get("movement") is not None and abs(gap) == r["movement"]:
                recovered.append({"page": pg, "balance": r["balance"],
                                  "movement": abs(gap),
                                  "side": "credit" if gap > 0 else "debit",
                                  "recovered": True})
                break
    return recovered
