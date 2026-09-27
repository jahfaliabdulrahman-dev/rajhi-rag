"""Page-order / chronology check — reversal must be detectable, not guessed.

What-if workshop delta #1: the input file may arrive with pages shuffled or
reversed. (This docstring once said the scans carry NO page-number stamp; they
do — every sheet prints its number in the header, `tools/page_numbers.py` —
but a vision model reads it on a minority of pages, so it cannot carry the
order alone.) The check is built on deterministic signals instead:

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
3. **The printed footer totals are CUMULATIVE** (`footer_oracle`), so they rise
   with every sheet: sorting by them IS the true order (`footer_order`), with
   no page number read. Measured on the 629-page file: 625 footers readable,
   zero descents in file order, no two sheets equal. Two neighbours in that
   order are consecutive sheets only when their footer difference equals the
   second sheet's own sums (`adjacency`).

Output feeds the app summary; nothing here blocks a run — it NAMES what it saw.
"""
from __future__ import annotations

import re
from bisect import bisect_left

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
        if p2 != p1 + 1:
            continue          # موقعان غير متجاورين = تغطية ناقصة، ليست فجوة
        if n2 == n1 + 1:
            continue
        if n2 == n1:
            continue          # a repeat — already captured in `duplicates`
        if n2 > n1 + 1:
            gaps.append((p1, n1, p2, n2, list(range(n1 + 1, n2))))
        else:
            backwards.append((p1, n1, p2, n2))
    breaks = [(p1, p2) for (p1, _), (p2, _) in zip(seq, seq[1:])
              if p2 != p1 + 1]
    return {
        "gaps": gaps,
        "duplicates": {n: ps for n, ps in positions.items() if len(ps) > 1},
        "backwards": backwards,
        "checked": len(seq),
        "unread": len(pairs) - len(seq),
        # read positions that do NOT sit next to each other: the sheets
        # between them were never read, so a jump across them is undecidable
        # rather than absent (audit P1-3).
        "position_breaks": breaks,
    }


MIN_PAGE_COVERAGE = 0.5   # below this the evidence cannot carry a verdict


def summarize_page_numbers(pn: dict) -> str:
    """Run-level one-liner for the ticker: is the scan order sound or not?

    Coverage decides whether a verdict is allowed at all (audit P1-3). The
    first version printed «✓ متسلسل» after reading the printed number on 17 of
    629 sheets, and printed the same ✓ for a 1→50 jump between two positions
    that were not neighbours. Both are over-claims: a green check must be
    something the evidence can carry, and «لا حكم» is a legitimate answer.
    """
    checked, unread = pn["checked"], pn["unread"]
    total = checked + unread
    if not checked:
        return f"الترقيم المطبوع: لم يُقرأ (0/{total})"
    coverage = checked / total if total else 0.0
    if coverage < MIN_PAGE_COVERAGE:
        # a low-coverage ✓ is exactly the false comfort this rule removes
        seg = (f"⚠ الترقيم المطبوع: تغطية ناقصة ({checked}/{total} مقروءة) — "
               f"لا حكم على التسلسل")
    elif unread or pn.get("position_breaks"):
        seg = (f"الترقيم المطبوع: متسلسل في المقروء ({checked}/{total}) — "
               f"التسلسل بين الصفحات غير المقروءة غير محسوم")
    else:
        seg = f"الترقيم المطبوع: ✓ متسلسل ({checked}/{total})"
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
        if cov_w / cov_t < MIN_PAGE_COVERAGE:
            # same rule as the page numbers: a green ✓ needs the evidence to
            # carry it, otherwise the honest answer is «لا حكم».
            seg = f"⚠ الترتيب: تغطية تواريخ ناقصة ({cov_w}/{cov_t}) — لا حكم"
        else:
            seg += f" [تواريخ مقروءة {cov_w}/{cov_t}]"
    if boundaries:
        anchors = boundaries.get("anchor", 0)
        okb = boundaries.get("txn", 0) + boundaries.get("carry", 0)
        if anchors:
            seg += f" — التحامات الصفحات: {okb} سليمة، {anchors} مرساة غير محسومة"
    return seg


def _outside_lis(seq: list[int]) -> list[int]:
    """Items NOT on one longest increasing run of `seq` — the fewest to move."""
    tails: list[int] = []
    tail_at: list[int] = []
    parent: list[int | None] = [None] * len(seq)
    for i, v in enumerate(seq):
        j = bisect_left(tails, v)
        if j == len(tails):
            tails.append(v)
            tail_at.append(i)
        else:
            tails[j], tail_at[j] = v, i
        parent[i] = tail_at[j - 1] if j else None
    keep: set[int] = set()
    i = tail_at[-1] if tail_at else None
    while i is not None:
        keep.add(seq[i])
        i = parent[i]
    return [v for v in seq if v not in keep]


def footer_order(footers: dict[int, tuple]) -> dict:
    """{file position: (cumulative debits, cumulative credits)} -> the true order.

    The key is the pair of printed cumulative totals, which only rise sheet
    after sheet — so the sort needs no page number and no date. Honest edges:

    - `unplaced`: a footer missing a total cannot be ranked; the sheet stays
      right after its file predecessor (and its neighbours stay undecided).
    - `conflicts`: debits and credits disagree on which sheet comes first —
      a misread footer, never resolved by guessing.
    - `duplicates`: identical totals — a sheet scanned twice (or a summary
      page repeating the last footer).
    - `moved`: the FEWEST sheets whose move restores the order (outside one
      longest increasing run), in true order — what a person should look at.
    """
    placed = {p: v for p, v in footers.items()
              if v is not None and v[0] is not None and v[1] is not None}
    ranked = sorted(placed, key=lambda p: (placed[p][0], placed[p][1], p))
    conflicts = [(a, b) for a, b in zip(ranked, ranked[1:])
                 if placed[b][1] < placed[a][1]]
    groups: dict[tuple, list[int]] = {}
    for p in ranked:
        groups.setdefault(tuple(placed[p][:2]), []).append(p)
    order = list(ranked)
    unplaced = sorted(set(footers) - set(placed))
    positions = sorted(footers)
    for p in unplaced:
        prev = positions[positions.index(p) - 1] if positions.index(p) else None
        order.insert(order.index(prev) + 1 if prev is not None else 0, p)
    return {"order": order, "moved": _outside_lis(order), "unplaced": unplaced,
            "conflicts": conflicts,
            "duplicates": [ps for ps in groups.values() if len(ps) > 1]}


def adjacency(order: list[int], footers: dict[int, tuple], own: dict[int, tuple],
              printed: dict[int, int | None] | None = None) -> dict[tuple[int, int], str]:
    """Is each pair of neighbours in the TRUE order two consecutive sheets?

    `own[p]` = sheet p's own (debits, credits), derived with its TRUE
    predecessor's closing balance (a first-row movement derived from the wrong
    neighbour is wrong). Status per (a, b):

    - adjacent  — footer(b) − footer(a) == own(b) in debits AND credits: the
                  identity `footer_oracle.delta_ok` checks, applied to the true
                  neighbour instead of the file neighbour. Exact on two fields,
                  so it outranks a printed number (read on a minority of pages).
    - gap       — the printed numbers jump: a sheet between them is missing.
    - mismatch  — both sides read and the difference disagrees: a misread or
                  an unnumbered missing sheet — named, not decided here.
    - undecided — a total is missing on either side.
    """
    printed = printed or {}
    out: dict[tuple[int, int], str] = {}
    for a, b in zip(order, order[1:]):
        fa, fb, ob = footers.get(a), footers.get(b), own.get(b)
        known = all(t is not None and t[0] is not None and t[1] is not None
                    for t in (fa, fb, ob))
        if known and fb[0] - fa[0] == ob[0] and fb[1] - fa[1] == ob[1]:
            out[(a, b)] = "adjacent"
            continue
        na, nb = printed.get(a), printed.get(b)
        if isinstance(na, int) and isinstance(nb, int) and nb > na + 1:
            out[(a, b)] = "gap"
        else:
            out[(a, b)] = "mismatch" if known else "undecided"
    return out


def _second_witness(p: int, order: list[int], printed: dict, pairs: dict) -> bool:
    """Does a witness OTHER than the footer totals put sheet p where `order` puts it?

    - proven adjacency: p and a neighbour in `order` are consecutive sheets by
      arithmetic (`adjacency` = adjacent); or
    - the printed page numbers: p's number sits strictly between its
      neighbours' known numbers (at least one known).
    """
    i = order.index(p)
    prev = order[i - 1] if i else None
    nxt = order[i + 1] if i + 1 < len(order) else None
    if (prev is not None and pairs.get((prev, p)) == "adjacent") or \
            (nxt is not None and pairs.get((p, nxt)) == "adjacent"):
        return True
    n = printed.get(p)
    before = printed.get(prev) if prev is not None else None
    after = printed.get(nxt) if nxt is not None else None
    if not isinstance(n, int) or not any(isinstance(x, int) for x in (before, after)):
        return False
    return (not isinstance(before, int) or before < n) and (not isinstance(after, int) or n < after)


def decide_order(file_order: list[int], fo: dict, printed: dict,
                 pairs: dict) -> tuple[list[int], str | None]:
    """(the order to process in, why the footer order was NOT applied | None).

    The footer order is one witness, and one misread digit is enough to move a
    sheet far (review 70: on the owner's real footers, one misread digit in a
    debit total moved a page up to 100 positions and broke up to 3 chain seams;
    18 of 40 such trials showed as conflicts). So it is applied only when it has
    no conflicts and no duplicates AND every sheet it moves has a second witness
    (`_second_witness`, with `printed`/`pairs` measured on the candidate order).
    Otherwise the file order stands and the reason is said.
    """
    file_order = list(file_order)
    if fo["conflicts"]:
        return file_order, "تذييلٌ متناقض"
    if fo["duplicates"]:
        return file_order, "إجمالياتٌ مكرّرة"
    if fo["order"] == file_order:
        return file_order, None
    lone = [p for p in fo["moved"] if not _second_witness(p, fo["order"], printed, pairs)]
    if lone:
        return file_order, ("نقلٌ بلا شاهدٍ ثانٍ — المواقع "
                            + "، ".join(str(p) for p in lone[:5]) + (" …" if len(lone) > 5 else ""))
    return list(fo["order"]), None


def summarize_footer_order(fo: dict, applied: bool = False, held: str | None = None) -> str:
    """Run-level one-liner: is the file in its true order, and what moved?

    `applied`: the run PROCESSED the pages in this true order. `held`: why it
    did not (`decide_order`) — said explicitly, so «out of place» is never read
    as «processed out of place», and a withheld order is never silent.
    """
    total = len(fo["order"])
    ranked = total - len(fo["unplaced"])
    if not total or ranked / total < MIN_PAGE_COVERAGE:
        return (f"⚠ الترتيب بالإجماليات التراكمية: تغطية ناقصة ({ranked}/{total}) — "
                f"لا حكم")
    if fo["conflicts"]:
        return (f"⚠ الترتيب بالإجماليات التراكمية: تذييلٌ متناقض بين المواقع "
                f"{fo['conflicts'][0][0]} و{fo['conflicts'][0][1]} — قراءةٌ تُراجَع قبل أي حكم"
                f"{' — عولجت بترتيب الملف' if held else ''}")
    seg = (f"الترتيب بالإجماليات التراكمية: ✓ مطابقٌ لترتيب الملف ({ranked}/{total})"
           if not fo["moved"] else
           f"⚠ الترتيب بالإجماليات التراكمية: صفحاتٌ في غير موضعها — المواقع "
           f"{'، '.join(str(p) for p in fo['moved'][:5])}"
           f"{' …' if len(fo['moved']) > 5 else ''} ({ranked}/{total})"
           f"{' — عولجت بترتيبها الحقيقي' if applied else ''}"
           f"{f' — عولجت بترتيب الملف: {held}' if held and not applied else ''}")
    if fo["duplicates"]:
        seg += " — إجمالياتٌ مكرّرة: " + "، ".join(
            "/".join(str(p) for p in ps) for ps in fo["duplicates"][:3])
    return seg
