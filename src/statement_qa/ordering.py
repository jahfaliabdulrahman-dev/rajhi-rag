"""Page-order / chronology check — reversal must be detectable, not guessed.

What-if workshop delta #1: the input file may arrive with pages shuffled or
reversed, and the scans carry NO page-number stamp (verified on renders) —
so the check is built on two deterministic signals instead:

1. Printed dates (gregorian part, YYYYMMDD after digit translation):
   open a statement bundle reversed and dates march BACKWARD page over page;
   a single misordered pair shows as first-date(next) < last-date(prev).
   This is a cross-page check; intra-page inversions are counted separately
   (rows occasionally print same-day groups; a strict decrease is unusual and
   worth a look, not an alarm by itself).
2. Chain boundary types (from chain_derive): every page boundary beyond page 1
   is either a carried balance «carry», a real transaction «txn», or a
   conservative «anchor» (unverifiable jump — preserved as opening, movement
   never fabricated). A high anchor ratio across boundaries is a shuffle /
   misread signal; it is reported alongside the dates.

Output feeds the app summary; nothing here blocks a run — it NAMES what it saw.
"""
from __future__ import annotations

import re

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_DATE_RUN = re.compile(r"\d{8}")


def parse_gregorian(date_str) -> str | None:
    """Printed date cell -> 'YYYYMMDD' gregorian, or None.

    Cells like «١٤٣٤١٢٢٦ ۲۰۱۳۱۰۳۱» carry BOTH calendars (hijri first).
    A valid gregorian run has a 19xx–21xx year passing month/day range
    checks; when several qualify, the LAST one wins (greg prints second).
    """
    if not date_str:
        return None
    s = str(date_str).translate(_DIGITS)
    candidates = []
    for m in _DATE_RUN.finditer(s):
        v = m.group(0)
        year, month, day = int(v[:4]), int(v[4:6]), int(v[6:8])
        if 1900 <= year <= 2199 and 1 <= month <= 12 and 1 <= day <= 31:
            candidates.append(v)
    return candidates[-1] if candidates else None


def check_order(per_page_dates: dict[int, list]) -> dict:
    """{page: [date cells]} -> cross/intra inversions + date coverage."""
    parsed = {pg: [parse_gregorian(d) for d in ds]
              for pg, ds in per_page_dates.items()}
    total = sum(len(v) for v in parsed.values())
    with_date = sum(1 for v in parsed.values() for d in v if d)

    cross, intra = [], {}
    prev_last, prev_pg = None, None
    for pg in sorted(parsed):
        seq = [d for d in parsed[pg] if d]
        inv = sum(1 for a, b in zip(seq, seq[1:]) if b < a)
        if inv:
            intra[pg] = inv
        if seq:
            if prev_last is not None and seq[0] < prev_last:
                cross.append((prev_pg, pg, prev_last, seq[0]))
            prev_last, prev_pg = seq[-1], pg
    return {"cross": cross, "intra": intra, "coverage": (with_date, total)}


def summarize_ar(order: dict, boundaries: dict | None = None) -> str:
    """Run-level one-liner for the app ticker."""
    seg = "الترتيب: تواريخ تصاعدية ✓"
    if order["cross"]:
        p, q, a, b = order["cross"][0]
        seg = f"⚠ الترتيب: تواريخ تنعكس بين ص{p}→ص{q} (راجع ترتيب الملف)"
    elif order["intra"]:
        pages = ", ".join(f"ص{p}" for p in sorted(order["intra"]))
        seg = f"⚠ الترتيب: انعكاس داخل صفحات {pages}"
    cov_w, cov_t = order["coverage"]
    if cov_t and cov_w < cov_t:
        seg += f" [تواريخ مقروءة {cov_w}/{cov_t}]"
    if boundaries:
        anchors = boundaries.get("anchor", 0)
        okb = boundaries.get("txn", 0) + boundaries.get("carry", 0)
        if anchors:
            seg += f" — التحامات الصفحات: {okb} سليمة، {anchors} مرساة غير محسومة"
    return seg
