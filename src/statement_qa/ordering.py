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


def check_page_numbers(pairs: list[tuple[int, int | None]]) -> dict:
    """Printed page numbers vs scan positions — the scan-order truth.

    `pairs` = (scan_position, printed_number|None) in scan order. Position is
    NOT identity: a scan that skips or duplicates a sheet makes the printed
    sequence jump, and a footer delta across such a pair then spans the
    missing sheets' movements (proven on this statement: index 427 -> printed
    ٤٢٨ with ٤٢٦/٤٢٧ absent, deficit == their movements exactly).

    Returns: gaps [(pos_before, n_before, pos_after, n_after, missing[...])],
    duplicates {printed: [positions]}, backwards [(pos, n, pos2, n2)],
    checked/unread counts. Nothing here blocks a run — it NAMES what it saw.
    """
    seq = [(pos, pn) for pos, pn in pairs if isinstance(pn, int)]
    gaps: list[tuple] = []
    backwards: list[tuple] = []
    positions: dict[int, list[int]] = {}
    for pos, pn in seq:
        positions.setdefault(pn, []).append(pos)
    for (p1, n1), (p2, n2) in zip(seq, seq[1:]):
        if n2 == n1 + 1:
            continue
        if n2 == n1:
            continue          # a repeat — already captured in `duplicates`
        if n2 > n1 + 1:
            gaps.append((p1, n1, p2, n2, list(range(n1 + 1, n2))))
        else:
            backwards.append((p1, n1, p2, n2))
    return {
        "gaps": gaps,
        "duplicates": {n: ps for n, ps in positions.items() if len(ps) > 1},
        "backwards": backwards,
        "checked": len(seq),
        "unread": len(pairs) - len(seq),
    }


def summarize_page_numbers(pn: dict) -> str:
    """Run-level one-liner for the ticker: is the scan order sound or not?"""
    if not pn["checked"]:
        return "الترقيم المطبوع: لم يُقرأ"
    seg = f"الترقيم المطبوع: ✓ متسلسل ({pn['checked']} صفحة)"
    if pn["gaps"]:
        miss = []
        for _p1, _n1, p2, _n2, missing in pn["gaps"]:
            miss.append(f"ص{p2} ينقص قبلها {'، '.join(str(m) for m in missing)}")
        seg = "⚠ الترقيم المطبوع: " + " · ".join(miss)
    if pn["duplicates"]:
        dups = "، ".join(f"{n} (مواقع {'/'.join(str(p) for p in ps)})"
                        for n, ps in list(pn["duplicates"].items())[:3])
        seg += f" — أرقام مكررة: {dups}"
    if pn["backwards"]:
        p1, n1, p2, n2 = pn["backwards"][0]
        seg += f" — رجوع ترقيم: موقع {p1} (#{n1}) → {p2} (#{n2})"
    return seg


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
