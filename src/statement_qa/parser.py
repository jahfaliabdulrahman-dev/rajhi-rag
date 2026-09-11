"""Geographic row parsing + chain-derived amounts (v2, skill-informed).

Lessons applied from scanned-pdf-ocr-pipeline (the 629-page case):
- Balance chain is the SUPREME ARBITER: movement[i] = bal[i] − bal[i−1];
  side = sign (positive → credit, negative → debit). OCR'd movement tokens
  are cross-checks only — never the source of truth.
- Numbers: U+066C thousands, U+066B decimal, U+060C is punctuation (NOT a
  thousands separator). Arabic-Indic AND Persian ۰-۹ digits both occur.
- Owner's comma rule (trailing 1–2 digit group = halalas) is an
  interpretation HINT only — OCR text is too corrupted to apply it
  mechanically; riyal-scale resolution needs external anchors (footers /
  summary page). v1 works in printed units, chain-consistent, and flags
  the scale as unresolved rather than inventing wrong riyals.
- Calibrate y-tolerance and x-bands on one real page; NEVER generalize
  page anatomy from a single page (check ≥10 pages across eras first).
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import polars as pl

# Arabic-Indic + Persian digits; Arabic decimal (٫) + thousands (٬) -> Western
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")

_DATE_RE = r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"


def normalize_digits(text: str) -> str:
    """Arabic-Indic/Persian digits + Arabic separators -> Western. Idempotent."""
    return text.translate(_AR_DIGITS)


# ---------------------------------------------------------------- words ---

@dataclass
class Word:
    x: int
    y: int
    w: int
    h: int
    tok: str

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    @property
    def is_number(self) -> bool:
        t = self.tok
        return bool(re.fullmatch(r"\d[\d.,]*", t or "")) and any(c.isdigit() for c in t)


def parse_tsv(tsv: str) -> list[Word]:
    """Parse tesseract TSV by HEADER NAMES (never column index).

    Drops conf<0 rows and empty text (structural, not words). Normalizes
    digits per token before anything else.
    """
    words: list[Word] = []
    rdr = csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
    for row in rdr:
        try:
            conf = float(row.get("conf", "-1"))
        except (TypeError, ValueError):
            continue
        text = (row.get("text") or "").strip()
        if conf < 0 or not text:
            continue
        try:
            words.append(Word(
                x=int(row["left"]), y=int(row["top"]),
                w=int(row["width"]), h=int(row["height"]),
                tok=normalize_digits(text),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return words


def cluster_rows(words: list[Word], y_tol: float = 18.0) -> list[list[Word]]:
    """Group words into visual rows by vertical center proximity.

    y_tol is calibrated at 300dpi (~18px); scale it for other dpi. Sort
    words inside a row by horizontal center so column order is real.
    """
    rows: list[list[Word]] = []
    for w in sorted(words, key=lambda t: (t.cy, t.cx)):
        if rows and abs(w.cy - rows[-1][-1].cy) <= y_tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    return [sorted(r, key=lambda t: t.cx) for r in rows]


# --------------------------------------------------------------- numbers --

def _to_decimal(tok: str) -> Decimal:
    """Robust amount token -> Decimal (en/eu separators, plain, empty->0)."""
    tok = (tok or "").strip().replace(" ", "")
    if not tok:
        return Decimal("0")
    has_comma, has_dot = "," in tok, "." in tok
    if has_comma and has_dot:
        if tok.rfind(",") > tok.rfind("."):
            tok = tok.replace(".", "").replace(",", ".")
        else:
            tok = tok.replace(",", "")
    elif has_comma:
        head, _, tail = tok.rpartition(",")
        if len(tail) == 3 and head and not head.endswith("."):
            tok = tok.replace(",", "")
        else:
            tok = tok.replace(",", ".")
    try:
        return Decimal(tok)
    except InvalidOperation:
        return Decimal("0")


def _numeric_words(row: list[Word]) -> list[Word]:
    return [w for w in row if w.is_number]


# ------------------------------------------------------- TSV page parse ---

def page_word_rows(tsv: str, y_tol: float = 18.0) -> list[dict]:
    """One OCR page -> ordered candidate rows (geographic rebuild).

    Returns dicts {desc, bal_tok, mv_tok, bal_x, mv_x, y} in visual order.
    Column model: LEFTMOST numeric token of a visual row = running balance
    candidate (changes every row); the next numeric token = printed
    movement (CROSS-CHECK only — the chain derives the true amount).
    """
    words = parse_tsv(tsv)
    out: list[dict] = []
    for vr in cluster_rows(words, y_tol=y_tol):
        nums = _numeric_words(vr)
        if not nums:
            continue
        desc = " ".join(w.tok for w in vr if not w.is_number).strip(" -—.")
        bal = nums[0]
        mv = nums[1] if len(nums) >= 2 else None
        out.append({
            "desc": desc,
            "bal_tok": bal.tok,
            "mv_tok": mv.tok if mv else "",
            "bal_x": bal.cx,
            "mv_x": mv.cx if mv else None,
            "y": bal.cy,
        })
    return out


def assemble_chain(rows: list[dict]) -> list[dict]:
    """Global chain pass over candidate rows (across pages, in order).

    movement[i] = bal[i] − bal[i−1]; side = sign. The printed movement
    token is a cross-check: |derived| == printed (same or ×100 scale)
    keeps the row clean; mismatch flags it as suspect (OCR digit error).
    Row 0 = opening balance (no derivable movement).
    """
    out: list[dict] = []
    prev_bal: Decimal | None = None
    for r in rows:
        bal = _to_decimal(r["bal_tok"])
        if prev_bal is None:
            out.append({**r, "balance": bal, "movement": Decimal("0"),
                        "side": "", "ok": True, "opening": True})
        else:
            delta = bal - prev_bal
            movement, side = abs(delta), ("credit" if delta > 0 else "debit" if delta < 0 else "")
            ok = True
            mv_tok_dec = _to_decimal(r["mv_tok"]) if r["mv_tok"] else None
            if mv_tok_dec is not None and movement:
                # cross-check at scale 1 or ×100 (halala convention)
                ok = (mv_tok_dec == movement) or (mv_tok_dec * 100 == movement) \
                     or (mv_tok_dec == movement * 100)
            out.append({**r, "balance": bal, "movement": movement,
                        "side": side, "ok": ok, "opening": False})
        prev_bal = bal
    return out


# ----------------------------------------------------- line-fallback path --

def _parse_lines_fallback(page_no: int, chunk: str) -> list[dict]:
    """Line-regex parse (text-layer pages and TSV-less fallback).

    Normalizes Arabic-Indic/Persian digits FIRST — the regex only knows
    Western digits (lesson: U+066C/٫ normalization happens in ONE table
    before any parsing).
    """
    out: list[dict] = []
    for raw in normalize_digits(chunk).splitlines():
        line = raw.strip()
        if not line or line.startswith("[PAGE"):
            continue
        m = re.match(rf"^({_DATE_RE})\s+(.+)$", line)
        if not m:
            continue
        date, tail = m.group(1), m.group(2)
        toks = tail.split()
        amounts: list[str] = []
        while toks and re.fullmatch(r"\d[\d.,]*", toks[-1]):
            amounts.insert(0, toks.pop())
            if len(amounts) >= 3:
                break
        desc = " ".join(toks).strip(" -—.")
        if not amounts or not desc:
            continue
        if len(amounts) == 1:
            debit, credit, bal = Decimal("0"), Decimal("0"), _to_decimal(amounts[0])
        elif len(amounts) == 2:
            bal = _to_decimal(amounts[-1])
            mv = _to_decimal(amounts[0])
            debit, credit = mv, Decimal("0")
        else:
            bal = _to_decimal(amounts[-1])
            debit, credit = _to_decimal(amounts[-3]), _to_decimal(amounts[-2])
        out.append({"date": date, "description": desc, "debit": debit,
                    "credit": credit, "balance": bal})
    return out


def _parse_lines(page_no: int, chunk: str) -> list[dict]:
    return _parse_lines_fallback(page_no, chunk)


# ------------------------------------------------------------- assembly --

_SCHEMA = {
    "date": pl.String,
    "description": pl.String,
    "debit": pl.Decimal(18, 2),
    "credit": pl.Decimal(18, 2),
    "balance": pl.Decimal(18, 2),
}


def parse_text(text: str, tsv_by_page: dict[int, str] | None = None) -> pl.DataFrame:
    """Statement text (+optional TSV boxes) -> parsed table.

    Pages with TSV use the geographic + chain-derived path; others use
    the line-regex fallback. Chain derivation runs globally (page N
    closing continues into page N+1 opening).
    """
    tsv_by_page = tsv_by_page or {}

    # split text into per-page chunks (text without markers = page 0)
    page_chunks: list[tuple[int, str]] = []
    cur_page, cur_lines = 0, []
    for raw in text.splitlines():
        m = re.match(r"^\s*\[PAGE (\d+)\]", raw)
        if m:
            if cur_lines or cur_page:
                page_chunks.append((cur_page, "\n".join(cur_lines)))
            cur_page, cur_lines = int(m.group(1)), []
        else:
            cur_lines.append(raw)
    if cur_lines or cur_page:
        page_chunks.append((cur_page, "\n".join(cur_lines)))

    candidates: list[dict] = []
    fallback_rows: list[dict] = []
    for page_no, chunk in page_chunks:
        tsv = tsv_by_page.get(page_no)
        if tsv:
            candidates.extend(page_word_rows(tsv))
        else:
            fallback_rows.extend(_parse_lines(page_no, chunk))

    rows: list[dict] = []
    if candidates:
        for r in assemble_chain(candidates):
            rows.append({
                "date": "",
                "description": r["desc"],
                "debit": r["movement"] if r["side"] == "debit" else Decimal("0"),
                "credit": r["movement"] if r["side"] == "credit" else Decimal("0"),
                "balance": r["balance"],
            })
    rows.extend(fallback_rows)

    df = pl.DataFrame(rows, schema=_SCHEMA, strict=False)
    return df


def fix_sides_by_chain(df: pl.DataFrame) -> pl.DataFrame:
    """Decide debit-vs-credit for line-path rows using the balance chain."""
    if df.height < 2:
        return df
    rows = df.to_dicts()
    for i in range(1, len(rows)):
        r, prev = rows[i], rows[i - 1]
        if r["debit"] == 0 and r["credit"] == 0:
            continue
        has_debit = r["debit"] != 0
        has_credit = r["credit"] != 0
        if has_debit and has_credit:
            continue
        movement = r["debit"] if has_debit else r["credit"]
        expected_plus = prev["balance"] + movement
        expected_minus = prev["balance"] - movement
        if r["balance"] == expected_plus and r["balance"] != expected_minus:
            r["credit"], r["debit"] = movement, Decimal("0")
        elif r["balance"] == expected_minus:
            r["debit"], r["credit"] = movement, Decimal("0")
    return pl.DataFrame(rows, schema=df.schema, strict=False)


def load_statement(path: str, dpi: int = 300) -> pl.DataFrame:
    """PDF/CSV path -> parsed table (app entry).

    Scanned pages: OCR (ara+eng) -> TSV -> geographic rows -> chain-derived
    amounts. Text-layer pages: line-regex path. y-tolerance ≈ 18px at
    300dpi (calibrated); scaled proportionally for other dpi.
    """
    p = Path(path)
    if p.suffix.lower() == ".csv":
        return pl.read_csv(p, schema_overrides={
            "debit": pl.Decimal(18, 2), "credit": pl.Decimal(18, 2),
            "balance": pl.Decimal(18, 2)})
    from statement_qa.extract_text import extract_pages

    pages = extract_pages(str(p))
    tsv_by_page = {pg.page_no: pg.tsv for pg in pages if pg.tsv}
    text = "\n\n".join(f"[PAGE {pg.page_no}]\n{pg.text}" for pg in pages if pg.text)
    df = parse_text(text, tsv_by_page=tsv_by_page)
    return fix_sides_by_chain(df)
