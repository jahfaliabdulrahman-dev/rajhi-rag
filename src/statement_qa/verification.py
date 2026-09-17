"""Page-verification vocabulary — one language for «is this page proven?».

WHY THIS MODULE EXISTS
Every verification device the project owns (ok / mismatch / gap / absent /
unchecked) lived in the reading tab. It never reached the tab where the numbers
are actually consumed: the answer, the table and the export. So a figure taken
from a page whose neighbours are missing from the scan arrived looking exactly
like a figure from a page verified three ways (audit P1-4, P1-5). And the banner
that summarised it all counted only the comparable pages, so «621/621 matching»
was printed on a 629-page file that also held two scan gaps and four frameless
pages (audit P1-2).

Pure by construction: no state, no IO, no model. `app.py` renders it; the tests
prove it.
"""
from __future__ import annotations

# The five oracle statuses, in the words a reader sees.
PAGE_VERDICTS = {
    "ok": "✓ موثّق",
    "mismatch": "✗ غير مطابق",
    "gap": "⚠ فجوة مسح",
    "absent": "◔ بلا إطار مطبوع",
    "unchecked": "— غير قابل للتحقق",
}
UNPROVEN = "— لم تُفحص"


def verdicts_from_checks(checks) -> dict[int, str]:
    """[{page, status}, …] → {page: status}. Missing status = unproven."""
    out: dict[int, str] = {}
    for c in checks or []:
        try:
            out[int(c["page"])] = str(c.get("status") or "unchecked")
        except (KeyError, TypeError, ValueError):
            continue
    return out


def verdict_label(status: str | None) -> str:
    if not status:
        return UNPROVEN
    return PAGE_VERDICTS.get(status, UNPROVEN)


def is_proven(status: str | None) -> bool:
    return status == "ok"


def unproven_pages(verdicts: dict[int, str]) -> list[int]:
    return sorted(p for p, s in (verdicts or {}).items() if not is_proven(s))


def coverage_line(verdicts: dict[int, str]) -> str:
    """Two numbers, never one: how much was checked and how it went.

    A single ratio hid both a scan gap and four frameless pages (audit P1-2).
    """
    total = len(verdicts or {})
    if not total:
        return "تغطية التحقق: لا صفحات مفحوصة"
    proven = sum(1 for s in verdicts.values() if is_proven(s))
    return (f"تغطية التحقق: {proven}/{total} صفحة موثّقة "
            f"({proven / total:.1%}) — والباقي مسمّى بالاسم")


def caution(used_pages, verdicts: dict[int, str]) -> str:
    """The line attached to an answer built from pages that are not proven.

    Names only the pages actually used, and stays silent when every page used
    is proven — a caution printed unconditionally is a caution nobody reads.
    """
    bad = []
    for p in sorted({p for p in (used_pages or []) if p is not None}):
        status = (verdicts or {}).get(p)
        if not is_proven(status):
            bad.append(f"ص{p} ({verdict_label(status)})")
    if not bad:
        return ""
    return ("⚠ يشمل صفحات غير موثّقة: " + "، ".join(bad)
            + " — راجع الحكم في تبويب «قراءة وتحقق» قبل بناء قرار على هذه الأرقام.")
