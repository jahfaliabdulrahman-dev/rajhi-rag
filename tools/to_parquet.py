#!/usr/bin/env python3
"""One queryable index over the page checkpoints (audit §5, option ب).

A statement costs ~149 MB: 629 JSON checkpoints, a 433 KB report, and ~144 MB of
PNG renders. The checkpoints ARE the evidence and stay; the renders are
reproducible from the original PDF at the same DPI, so they are the only thing
that may be dropped. What the JSONs lack is a way to ASK something: «which pages
are not proven?» currently means writing a script per question — and the
documented trap (checkpoints store `raw_rows` without a chain `side`, so a naive
re-derivation returns zeros and once produced two wrong conclusions) means every
new script re-risks it.

This writes `index.parquet` next to the report: one row per statement row, with
page, verdict, printed values and the page's repair flags — so the questions
become one filter each.

    python3 tools/to_parquet.py --results data/local_sample/slice_629p/results

Deliberately ABSENT from the index: `side` and `ok`. Those are chain-derived
facts, and re-deriving them here would duplicate the arbiter instead of asking
it — the exact mistake the trap punished. Use `chain_derive` for those.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))

import polars as pl  # noqa: E402


def load_rows(results: Path) -> list[dict]:
    out: list[dict] = []
    for cache in sorted(results.glob("pg-*.json")):
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            continue
        page = data.get("pg")
        footer = data.get("footer") or {}
        arbitrated = {r.get("field") for r in (data.get("arbitrated_by") or [])}
        for i, row in enumerate(data.get("raw_rows") or [], start=1):
            out.append({
                "page": page,
                "row_no": i,
                "date": row.get("date"),
                "desc": row.get("desc"),
                "movement_raw": row.get("movement"),
                "balance_raw": row.get("balance"),
                "page_recovered": bool(data.get("recovered")),
                "page_reread": bool(data.get("reread")),
                "page_error": bool(data.get("error")),
                "footer_arbitrated": bool(arbitrated),
                "footer_debits": footer.get("debits"),
                "footer_credits": footer.get("credits"),
                "footer_balance": footer.get("balance"),
            })
    return out


def build(results: Path, out: Path | None = None) -> Path:
    rows = load_rows(results)
    if not rows:
        raise SystemExit(f"لا صفوف في {results} — هل المسار صحيح؟")
    lf = pl.LazyFrame(rows, schema_overrides={
        "page": pl.Int64, "row_no": pl.Int64,
        "movement_raw": pl.Utf8, "balance_raw": pl.Utf8,
        "footer_debits": pl.Utf8, "footer_credits": pl.Utf8,
        "footer_balance": pl.Utf8})
    target = out or (results.parent / "index.parquet")
    lf.sink_parquet(target, compression="zstd")
    return target


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    target = build(Path(args.results),
                   Path(args.out) if args.out else None)
    df = pl.read_parquet(target)
    print(f"[to-parquet] {target} — {df.height} صفاً × {df.width} عموداً")
    print(df.select(["page", "row_no", "movement_raw", "balance_raw"]).head(3))
    print("\nمثال استعلام: صفحات فيها إعادة قراءة أو استدراك ⇒")
    print(df.filter(pl.col("page_recovered") | pl.col("page_reread"))
            .select(pl.col("page").unique()).sort("page"))


if __name__ == "__main__":
    main()
