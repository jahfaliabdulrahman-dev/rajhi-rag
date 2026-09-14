"""Era detector — a per-page «fingerprint» of the printed number FORMAT.

What-if workshop delta #2 («بصمة صيغة لكل صفحة»): the 629-page file mixes
printing generations; a page whose separator/zero conventions differ from its
neighbours is an early-warning for a silent ×100 / sign shift. The detector
runs on the RAW tokens returned by the VLM reader (raw_movement/raw_balance —
what was ON the paper before normalization) and classifies, per page:

  old       — comma as decimal point («٣٠٠,٠٠») or thousand-group style
  new       — dot halalas («٢٩٠٠.٠٠»), thousands separator allowed
  lost_dot  — the missing-decimal-dot family («٥٧,٥٠٢٧٥»)
  zero_style— the printed zero («.,..»)
  plain     — digits only

Outputs: per-page counts, per-page style (majority with a 3:1 margin — below
that the page reads «mixed»), transitions between consecutive pages, and
outliers (a page disagreeing with BOTH neighbours while they agree).
Heuristic by design and REPORTED, not blocking: its first job is to make a
format change visible the moment it happens.
"""
from __future__ import annotations

import re
from collections import Counter

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_DOT_CHARS = ".٫"
_COMMA_CHARS = ",،٬"

STYLE_NAMES = {
    "old": "عتيقة (فاصلة عشرية)",
    "new": "حديثة (نقطة عشرية)",
    "mixed": "مختلطة",
    "none": "غير محددة",
}


def token_style(tok) -> str | None:
    """One raw printed token -> separator-era style (None if unusable)."""
    if tok is None:
        return None
    s = str(tok).strip().translate(_DIGITS)
    if not s:
        return None
    has_dot = any(c in s for c in _DOT_CHARS)
    has_comma = any(c in s for c in _COMMA_CHARS)
    digits = re.sub(r"\D", "", s)
    if not digits:
        return "zero_style"  # «.,..» and friends — the printed zero
    if has_dot:
        return "new"
    if has_comma:
        # trailing separator group: 2 digits = decimal comma (old era);
        # 3 = thousands separator; >3 = the lost-dot family.
        tail = re.sub(r"\D", "", re.split("[" + re.escape(_COMMA_CHARS) + "]", s)[-1])
        if len(tail) == 2:
            return "old"
        if len(tail) == 3:
            return "new"
        if len(tail) > 3:
            return "lost_dot"
        return "old"
    return "plain"


def page_fingerprint(raw_tokens: list) -> dict:
    """Raw tokens of ONE page -> style counts + dominant style."""
    counts = {"old": 0, "new": 0, "lost_dot": 0, "zero_style": 0,
              "plain": 0, "none": 0}
    for tok in raw_tokens:
        counts[token_style(tok) or "none"] += 1
    o, n = counts["old"], counts["new"]
    if o == 0 and n == 0:
        style = "none"
    elif n == 0:
        style = "old"
    elif o == 0:
        style = "new"
    elif o > n * 3:
        style = "old"
    elif n > o * 3:
        style = "new"
    else:
        style = "mixed"
    return {"counts": counts, "style": style,
            "n_tokens": sum(counts.values())}


def fingerprint_pages(pages_raw: dict[int, list]) -> dict:
    """{page: [raw tokens]} -> per-page fingerprints + transitions + outliers."""
    per = {pg: page_fingerprint(toks) for pg, toks in sorted(pages_raw.items())}
    styles = {pg: f["style"] for pg, f in per.items()}

    transitions = []
    prev_pg, prev_style = None, None
    for pg in sorted(styles):
        st = styles[pg]
        if st == "none":
            continue
        if prev_style is not None and st != prev_style:
            transitions.append((prev_pg, pg, prev_style, st))
        prev_pg, prev_style = pg, st

    real = [s for s in styles.values() if s != "none"]
    majority = Counter(real).most_common(1)[0][0] if real else "none"
    outliers = []
    order = sorted(styles)
    for i, pg in enumerate(order):
        st = styles[pg]
        if st in ("none", majority, "mixed"):
            continue
        prev = styles.get(order[i - 1]) if i > 0 else None
        nxt = styles.get(order[i + 1]) if i < len(order) - 1 else None
        nb = [s for s in (prev, nxt) if s is not None]
        if nb and all(s == majority for s in nb):
            outliers.append(pg)

    distinct = {s for s in real}
    overall = majority if len(distinct) <= 1 else "mixed"
    return {"per_page": per, "styles": styles, "transitions": transitions,
            "outliers": outliers, "overall": overall, "majority": majority}


def summarize_ar(fp: dict) -> str:
    """Run-level one-liner for the app ticker."""
    styles = {p: s for p, s in fp["styles"].items() if s != "none"}
    if not styles:
        return "الصيغة: —"
    if fp["overall"] != "mixed" and not fp["transitions"] and not fp["outliers"]:
        return f"الصيغة: {STYLE_NAMES.get(fp['majority'], fp['majority'])} — كل الصفحات"
    bits = []
    for p, q, a, b in fp["transitions"]:
        bits.append(f"تحوّل ص{p}→ص{q} ({STYLE_NAMES.get(a, a)}→{STYLE_NAMES.get(b, b)})")
    if fp["outliers"]:
        bits.append(f"⚠ صفحات شاذة عن جيرانها: {fp['outliers']}")
    seg = "· ".join(bits) if bits else "صيغة غير موحّدة"
    return f"الصيغة: متغيرة — {seg}"
