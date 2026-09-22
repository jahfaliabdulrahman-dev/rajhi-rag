"""Phase-0 audit for the type-classification round (temporary dev tool).

Reads the real 10-page sample through the SAME pipeline the app uses
(dpi=200 renders -> chain_derive per page with cross-page prev_closing,
final row shaping identical to app.process_pdf), then reports:

  1. every distinct description + its count        (classifier vocabulary)
  2. every row with movement == 4331.11            (owner's four-row question)
  3. direction audit: delta sign vs stored side, mismatches listed
  4. chain status summary + the page-10 tail near the owner's صف 94

Dumps /tmp/rajhi_audit/rows.json for offline reuse by later phases.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdf2image import convert_from_path  # noqa: E402
from statement_qa.vlm_reader import chain_derive, read_rows_vlm  # noqa: E402

PDF = ROOT / "data" / "local_sample" / "sample_10p.pdf"
OUT = Path("/tmp/rajhi_audit")


def pages_to_pngs(pdf_path: Path, dpi: int = 200) -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    imgs = convert_from_path(str(pdf_path), dpi=dpi)
    out: list[Path] = []
    for i, img in enumerate(imgs, start=1):
        p = OUT / f"pg-{i:02d}.png"
        img.save(p)
        out.append(p)
    return out


def read_all(pages: list[Path]) -> list[dict]:
    """Replicates app.process_pdf row-shaping exactly (no chunk/index build)."""
    all_rows: list[dict] = []
    prev_closing = None
    for pg, img in enumerate(pages, start=1):
        rows = chain_derive(read_rows_vlm(str(img)), prev_balance=prev_closing)
        for r in rows:
            if r["balance"] is None:
                continue
            if r["opening"]:
                all_rows.append({"page": pg, "kind": "opening",
                                 "balance": r["balance"], "movement": None,
                                 "side": "", "ok": True,
                                 "desc": r.get("desc"), "date": r.get("date")})
            else:
                all_rows.append({"page": pg, "kind": "txn",
                                 "balance": r["balance"],
                                 "movement": r["derived_movement"],
                                 "printed_mv": r["movement"],
                                 "side": r["side"], "ok": r["ok"],
                                 "scale_fixed": r.get("scale_fixed", False),
                                 "desc": r.get("desc"), "date": r.get("date")})
            prev_closing = r["balance"]
        print(f"page {pg:2d}: read {len(rows)} raw rows")
    for i, r in enumerate(all_rows, start=1):
        r["row_no"] = i
    return all_rows


def main() -> None:
    pages = pages_to_pngs(PDF)
    rows = read_all(pages)

    def ser(r: dict) -> dict:
        return {k: (str(v) if isinstance(v, Decimal) else v)
                for k, v in r.items()}

    (OUT / "rows.json").write_text(
        json.dumps([ser(r) for r in rows], ensure_ascii=False, indent=1))

    txns = [r for r in rows if r["kind"] == "txn"]
    susp = [r for r in rows if not r["ok"]]
    print(f"\n=== TOTALS: {len(rows)} rows | txn={len(txns)} | "
          f"opening={len(rows) - len(txns)} | suspect={len(susp)} ===")

    print("\n=== [1] DISTINCT DESCRIPTIONS ===")
    for desc, n in Counter((r.get("desc") or "").strip()
                           for r in rows).most_common():
        print(f"{n:3d} × {desc[:110]}")

    print("\n=== [2] ROWS WITH AMOUNT == 4331.11 ===")
    hit = 0
    for r in rows:
        mv = r.get("movement")
        if isinstance(mv, Decimal) and mv == Decimal("4331.11"):
            hit += 1
            print(f"row {r['row_no']:3d} | صفحة {r['page']:2d} | "
                  f"side={r['side'] or '—':6s} | balance={r['balance']} | "
                  f"desc={str(r.get('desc'))[:95]}")
    print(f"-> {hit} row(s) with 4331.11")

    print("\n=== [3] DIRECTION AUDIT (balance-delta sign vs stored side) ===")
    print("side distribution:", dict(Counter(r["side"] or "undecided"
                                             for r in txns)))
    prev_bal = None
    mism, undecided = [], []
    for r in rows:
        if r["balance"] is None:
            continue
        if prev_bal is not None and r["kind"] == "txn":
            delta = r["balance"] - prev_bal
            exp = "credit" if delta > 0 else "debit" if delta < 0 else ""
            mv = r["movement"]
            if mv not in (None, Decimal("0.00")) and exp and r["side"] and r["side"] != exp:
                mism.append((r, exp, delta))
            if not r["side"] and mv not in (None, Decimal("0.00")):
                undecided.append(r)
        prev_bal = r["balance"]
    print(f"mismatches: {len(mism)} | undecided-side txns: {len(undecided)}")
    for r, exp, delta in mism[:12]:
        print(f"  MISMATCH row {r['row_no']} صفحة {r['page']}: stored={r['side']} "
              f"expected={exp} delta={delta} desc={str(r.get('desc'))[:60]}")
    for r in undecided[:12]:
        print(f"  UNDECIDED row {r['row_no']} صفحة {r['page']}: "
              f"mv={r['movement']} desc={str(r.get('desc'))[:60]}")

    print("\n=== [4] PAGE-10 TAIL (owner's context: rows 88+) ===")
    for r in [r for r in rows if r["page"] == 10 and r["row_no"] >= 88]:
        mv = r.get("movement")
        print(f"row {r['row_no']:3d} | {r['kind']:7s} | side={r['side'] or '—':6s} | "
              f"mv={mv if mv is not None else '—'} | bal={r['balance']} | "
              f"{str(r.get('desc'))[:80]}")

    print(f"\nrows.json -> {OUT / 'rows.json'}")


if __name__ == "__main__":
    main()
