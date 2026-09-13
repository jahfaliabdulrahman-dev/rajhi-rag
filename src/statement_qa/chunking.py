"""Chunking: statement rows → RAG chunks with page/row provenance.

Each chunk = one page's transaction block, serialized in Arabic with
explicit page number and row index — the retriever returns chunks that
carry their own source, and the QA layer quotes them verbatim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

_ROWS_PER_CHUNK = 12  # keep chunks small: dense numeric Arabic context


@dataclass
class Chunk:
    page: int
    start_row: int          # 1-based within page
    end_row: int
    text: str
    meta: dict

    @property
    def chunk_id(self) -> str:
        return f"p{self.page:03d}-r{self.start_row:02d}-{self.end_row:02d}"


_SIDE_AR = {"debit": "مدين", "credit": "دائن"}


def _fmt_row(r: dict, idx: int) -> str:
    bal = r.get("balance")
    kind = r.get("kind")
    if kind == "opening":
        return f"صف {idx}: رصيد افتتاحي = {bal}"
    mv = r.get("movement")
    side = _SIDE_AR.get(r.get("side") or "", "غير محسوم")
    typ = r.get("type") or ""
    label = typ if typ and typ != "غير مصنّف" else "حركة"
    ok = "" if r.get("ok") else " [صف مشبوه — يحتاج مراجعة]"
    desc = (r.get("desc") or "").replace("\n", " ").strip()
    desc_part = f" | {desc}" if desc else ""
    return (f"صف {idx}: {label} ({side}) بمبلغ {mv} → الرصيد صار {bal}"
            f"{desc_part}{ok}")


def chunk_rows(rows: list[dict], per_chunk: int = _ROWS_PER_CHUNK) -> list[Chunk]:
    """Group consolidated statement rows into page-anchored chunks."""
    by_page: dict[int, list[tuple[int, dict]]] = {}
    for r in rows:
        by_page.setdefault(r["page"], []).append((r["row_no"], r))

    chunks: list[Chunk] = []
    for page, items in sorted(by_page.items()):
        items.sort(key=lambda t: t[0])
        for start in range(0, len(items), per_chunk):
            window = items[start:start + per_chunk]
            lines = [f"[صفحة {page} من كشف الراجحي]"]
            lines.extend(_fmt_row(r, i) for i, r in window)
            s_no, e_no = window[0][0], window[-1][0]
            chunks.append(Chunk(
                page=page, start_row=s_no, end_row=e_no,
                text="\n".join(lines),
                meta={"page": page, "row_start": s_no, "row_end": e_no,
                      "n_rows": len(window)},
            ))
    return chunks


def load_rows(path: str) -> list[dict]:
    """statement_rows.jsonl → rows with row_no assigned per page."""
    raw = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    counter: dict[int, int] = {}
    for r in raw:
        counter[r["page"]] = counter.get(r["page"], 0) + 1
        r["row_no"] = counter[r["page"]]
    return raw


if __name__ == "__main__":
    rows = load_rows("data/local_sample/statement_rows.jsonl")
    chunks = chunk_rows(rows)
    print(f"{len(rows)} rows -> {len(chunks)} chunks")
    print("--- sample chunk ---")
    print(chunks[1].text[:600])
