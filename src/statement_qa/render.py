"""Pure rendering logic, extracted from app.py so it can be tested.

`app.py` is 800+ lines of Gradio layout with zero tests, and the audit found
that the untested functions inside it were exactly the ones shaping what a
reader sees: the row's verification column, the citation parser that decides
which rows the evidence panel shows, and the text of the answer. Those are
pure functions — they live here now, covered by tests, while app.py keeps the
wiring (audit P3-4).
"""
from __future__ import annotations

import re

from statement_qa.verification import caution, verdict_label

_ARG_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_REF_RE = re.compile(
    r"صفحة\s*([٠-٩0-9]+)[^\d٠-٩]{0,14}?صف(?:وف)?\s*([٠-٩0-9]+)"
    r"(?:\s*[–\-—]\s*([٠-٩0-9]+))?")
_BARE_REF_RE = re.compile(
    r"(?:^|[^\d٠-٩])صف(?:وف)?\s*([٠-٩0-9]+)(?:\s*[–\-—]\s*([٠-٩0-9]+))?")


def money(v) -> str:
    return f"{v:,.2f}" if v is not None else ""


def date_cell(row: dict) -> str:
    """Gregorian `YYYY/MM/DD` for the table and the export; `*` = inherited.

    The printed cell may carry both calendars (hijri first) — parse_gregorian
    picks the gregorian run — and an unparseable cell is shown as printed,
    never dropped.
    """
    from statement_qa.ordering import parse_gregorian

    d = str(row.get("date") or "").strip()
    if not d:
        return "—"
    g = parse_gregorian(d)
    shown = f"{g[:4]}/{g[4:6]}/{g[6:]}" if g else d
    return shown + ("*" if row.get("date_source") == "inherited" else "")


def row_record(no: int, row: dict, verdicts: dict | None = None) -> dict:
    """Excel-style display record: real النوع + مدين/دائن split + verification.

    Global row numbers stay stable across filtering — the same numbers the
    tools cite («صف 94»). Direction lives ONLY in which of the two amount
    columns carries the value; it is not a type claim.

    The «التحقق» column is the page's oracle verdict. The export is the artefact
    that leaves the system and gets decided upon, and until now it carried no
    sign at all that a row came from a scan gap or a frameless page (P1-5).
    """
    verdicts = verdicts or {}
    mv = money(row["movement"])
    status = "✓" if row["ok"] else "⚠ مشبوه"
    if (row["ok"] and row.get("kind") == "txn" and mv
            and not (row.get("side") or "")):
        # the amount is real but its DIRECTION could not be derived (a page-start
        # edge where the opening row was missed) — never guess a side column
        status = "◌ اتجاه غير محسوم"
    return {"#": no,
            "الصفحة": row["page"],
            "التاريخ": date_cell(row),
            "الوصف": (row.get("desc") or "—"),
            "النوع": row.get("type") or
                    ("رصيد افتتاحي" if row.get("kind") == "opening" else "حركة"),
            "مدين": mv if row["side"] == "debit" else "",
            "دائن": mv if row["side"] == "credit" else "",
            "الرصيد": money(row["balance"]),
            "الحالة": status,
            "التحقق": verdict_label(verdicts.get(row["page"]))}


def answer_refs(answer: str) -> list[tuple[int | None, int, int]]:
    """Citations inside the answer text: (page|None, first_row, last_row)."""
    refs: list[tuple[int | None, int, int]] = []
    for m in _REF_RE.finditer(answer or ""):
        try:
            pg = int(m.group(1).translate(_ARG_DIGITS))
            a = int(m.group(2).translate(_ARG_DIGITS))
            b = int(m.group(3).translate(_ARG_DIGITS)) if m.group(3) else a
        except ValueError:
            continue
        if b < a:
            a, b = b, a
        refs.append((pg, a, b))
    if not refs:
        for m in _BARE_REF_RE.finditer(answer or ""):
            try:
                a = int(m.group(1).translate(_ARG_DIGITS))
                b = int(m.group(2).translate(_ARG_DIGITS)) if m.group(2) else a
            except ValueError:
                continue
            if b < a:
                a, b = b, a
            refs.append((None, a, b))
    return refs


def rows_for_refs(rows: list[dict], refs, cap: int = 60,
                  verdicts: dict | None = None) -> list[dict]:
    """Rows matching the citations, capped, as display records."""
    picked: list[tuple[int, dict]] = []
    for i, r in enumerate(rows, start=1):
        for pg, a, b in refs:
            if (pg is None or r["page"] == pg) and a <= i <= b:
                picked.append((i, r))
                break
    return [row_record(i, r, verdicts) for i, r in picked[:cap]]


def answer_text(res, page_of: dict, verdicts: dict) -> str:
    """The text a reader receives, with the two disclosures that must not be silent.

    1. A tool failure: the answer was NOT computed from the statement, and
       saying so is the difference between a caveat and a false number
       (audit P2-10 — the fallback used to happen invisibly).
    2. A page whose verdict is not «documented», named by page and reason
       (audit P1-4 — the verification layer never reached the answer).
    """
    text = str(getattr(res, "answer", "") or "")
    if getattr(res, "tools_failed", False):
        return ("⚠ تعذّرت الأدوات — هذا الجواب وصفي ولم يُحسَب من الكشف، "
                "فلا تعتمد أي رقم فيه.\n\n" + text)
    if getattr(res, "ungrounded", False):
        return ("⚠ سؤال رقمي بلا أي استدعاء أداة — الأرقام أدناه من نص القطع "
                "لا من حساب على الكشف، فلا تعتمدها.\n\n" + text)
    pages = [page_of.get(n) for n in (getattr(res, "used_row_nos", None) or [])]
    warn = caution([p for p in pages if p is not None], verdicts)
    return text + (("\n\n" + warn) if warn else "")


def evidence_mode(res) -> str:
    """Which evidence the panel may honestly show.

    'none'     — the tools failed: the panel is emptied on purpose, because
                 evidence assembled from the model's own citations is evidence
                 for a claim that was never computed (audit P2-10);
    'tools'    — rows a tool actually touched (the strong case);
    'fallback' — a descriptive answer: citations, else retrieval pages.
    """
    if getattr(res, "tools_failed", False) or getattr(res, "ungrounded", False):
        return "none"      # no computed evidence exists to show
    if getattr(res, "used_row_nos", None):
        return "tools"
    return "fallback"
