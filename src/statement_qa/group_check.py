"""Spans between two readable frames — the arithmetic that certifies a page
whose own totals row cannot be read.

Six pages of the certified statement carry no readable totals row (172, 484,
602 are blank separators; 485, 603 sit beside one; 629 is the last page). The
per-page oracle can only call those «absent» or «unchecked», which is honest and
useless at the same time: printed totals are cumulative-to-date, so

    Σ own-movements(p+1 … q)  ==  footer(q) − footer(p)

holds over a span bounded by two READABLE frames, component by component, and
the balance must land exactly on q's printed one. A page was never unverifiable
— it was unverifiable *alone*.

This module is the single source of that identity: the offline tool
(`tools/group_verify.py`) and the app's own read report both call it, so the
number in the banner and the number in the evidence file cannot drift apart.
"""
from __future__ import annotations

from decimal import Decimal


def _d(value) -> Decimal | None:
    if value is None or value == "":
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def verify_groups(pages: list[dict]) -> list[dict]:
    """pages: [{page, own_debits, own_credits, own_balance, frame_debits,
    frame_credits, frame_balance, usable}] in file order.

    Returns one group per pair of CONSECUTIVE readable frames, covering every
    page after the first and up to the second — plus a final «undecidable»
    group for anything after the last readable frame.
    """
    for p in pages:
        for key in ("own_debits", "own_credits", "frame_debits", "frame_credits"):
            if key not in p:
                p[key] = None
    usable_idx = [i for i, p in enumerate(pages) if p.get("usable")]
    groups: list[dict] = []
    for first, second in zip(usable_idx, usable_idx[1:]):
        span = pages[first + 1: second + 1]
        if not span:
            continue
        frames = [_d(pages[i].get(k)) for i in (first, second)
                  for k in ("frame_debits", "frame_credits")]
        if any(f is None for f in frames):
            continue      # a bracket without complete frames brackets nothing
        diffs, mismatches = {}, {}
        for fld, own_key, frame_key in (("debits", "own_debits", "frame_debits"),
                                        ("credits", "own_credits", "frame_credits")):
            got = sum((_d(p.get(own_key)) or Decimal("0") for p in span),
                      Decimal("0"))
            want = _d(pages[second].get(frame_key)) - _d(pages[first].get(frame_key))
            diffs[fld] = str(got - want)
            mismatches[fld] = (got != want)
        last_balance = next((_d(p.get("own_balance")) for p in reversed(span)
                             if _d(p.get("own_balance")) is not None), None)
        bracket_balance = _d(pages[second].get("frame_balance"))
        balance_ok = (last_balance is None or bracket_balance is None
                      or last_balance == bracket_balance)
        groups.append({
            "pages": [p["page"] for p in span],
            "bracket": [pages[first]["page"], pages[second]["page"]],
            "status": ("verified" if (not any(mismatches.values()) and balance_ok)
                       else "mismatch"),
            # Only a span hiding an unreadable page proves anything NEW: for
            # readable pages the per-page oracle already did this arithmetic.
            "covers_unreadable": any(not p.get("usable") for p in span),
            "diff_debits": diffs["debits"], "diff_credits": diffs["credits"],
            "balance_ok": balance_ok,
        })
    if usable_idx and usable_idx[-1] < len(pages) - 1:
        tail = [p["page"] for p in pages[usable_idx[-1] + 1:]]
        groups.append({"pages": tail, "status": "undecidable",
                       "why": f"لا إطار مقروء بعد ص{pages[usable_idx[-1]]['page']}"})
    return groups


def from_checks(footer_checks: list[dict], all_rows: list[dict]) -> list[int]:
    """The app's inputs (per-page verdicts + its own row list) -> the pages that
    the per-page oracle had to leave undecided and the span arithmetic certifies.

    A frame is treated as a bracket only when its own verdict is «ok»: a frame
    we could not reconcile must not bracket someone else's movement.
    """
    own_by_page: dict[int, dict] = {}
    for r in all_rows:
        if (r.get("kind") != "txn" or r.get("movement") is None
                or not r.get("side")):
            continue
        slot = own_by_page.setdefault(
            r["page"], {"debits": Decimal("0"), "credits": Decimal("0"),
                        "balance": None})
        # side is "debit"/"credit" on app rows; the slots are plural.
        slot[r["side"] + "s"] += r["movement"]
        if r.get("balance") is not None:
            slot["balance"] = r["balance"]
    pages = []
    for c in footer_checks:
        pg, status = c["page"], c["status"]
        own = c.get("own") or own_by_page.get(pg) or {}
        cum = c.get("totals") or {}
        # A scan-gap page still has a READABLE frame — its own delta is what
        # exposed the gap. Excluding it as a bracket would shrink the coverage
        # the group arithmetic can prove (auditor's answer to Q2).
        readable = status in ("ok", "gap")
        pages.append({"page": pg,
                      "own_debits": own.get("debits"),
                      "own_credits": own.get("credits"),
                      "own_balance": own.get("balance"),
                      "frame_debits": cum.get("debits") if readable else None,
                      "frame_credits": cum.get("credits") if readable else None,
                      "frame_balance": cum.get("balance") if readable else None,
                      "usable": readable})
    return gained_pages(verify_groups(pages))


def gained_pages(groups: list[dict]) -> list[int]:
    """Pages that move from «unverifiable» to «proven as a group»."""
    return [n for g in groups
            if g["status"] == "verified" and g.get("covers_unreadable")
            for n in g["pages"]]


def gap_spans(groups: list[dict]) -> list[dict]:
    """Spans bounded by readable frames whose difference is not explained —
    the money the missing sheets took out of the statement."""
    return [g for g in groups
            if g["status"] == "mismatch" and g.get("covers_unreadable")]
