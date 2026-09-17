#!/usr/bin/env python3
"""Verify pages that have no readable footer — as a GROUP, between their neighbours.

THE GAP THIS CLOSES
Six pages of the certified statement are not verifiable one by one: four carry
no printed totals row at all, and two sit beside a page that has none, so their
delta has nothing to be measured against. That is where the report used to stop
— «unverifiable» — and it is an honest answer to the WRONG question.

The document still answers a bigger one. Printed totals are cumulative-to-date,
so if pages 484–485 have no frames but 483 and 486 do, then

    Σ own-movements(484..485)  ==  footer(486) − footer(483)

holds for the group, component by component, and the balance must land exactly
on 486's printed one. The pages were never unverifiable; they were unverifiable
*alone*. This tool measures the group and says which of the three it is:

    verified     — the group's own sum equals the bracketing difference
    mismatch     — it does not (with the exact difference, per component)
    undecidable  — no usable frame on one side (the end of the file)

Local, no API, no cost.

    .venv/bin/python tools/group_verify.py --results data/local_sample/slice_629p/results
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))

from statement_qa.vlm_reader import chain_derive  # noqa: E402
from statement_qa.footer_oracle import page_totals  # noqa: E402
from statement_qa.legacy.arabic_digit_parser import norm_num  # noqa: E402


def _dec(token) -> Decimal | None:
    if token in (None, ""):
        return None
    value = norm_num(token)
    return None if value is None else Decimal(str(value))


def load_pages(results: Path) -> list[dict]:
    """Per page (in scan order): own totals + its printed footer, if readable."""
    pages: list[dict] = []
    prev_closing = None
    for cache in sorted(results.glob("pg-*.json")):
        data = json.loads(cache.read_text(encoding="utf-8"))
        page = int(data.get("pg") or cache.stem.split("-")[1])
        raw = [{**r, "movement": _dec(r.get("movement")),
                "balance": _dec(r.get("balance"))}
               for r in (data.get("raw_rows") or [])]
        rows = chain_derive(raw, prev_balance=prev_closing)
        own = page_totals(rows)
        footer = data.get("footer") or {}
        frame = {k: _dec(footer.get(k)) for k in ("debits", "credits", "balance")}
        usable = frame["debits"] is not None and frame["credits"] is not None
        pages.append({"page": page, "own": own, "frame": frame,
                      "usable": usable, "error": bool(data.get("error"))})
        nxt = next((r["balance"] for r in reversed(rows)
                    if r["balance"] is not None), None)
        if nxt is not None:
            prev_closing = nxt
    return pages


from statement_qa.group_check import verify_groups as _verify_groups  # noqa: E402


def verify_groups(pages: list[dict]) -> list[dict]:
    """Adapter: the identity itself lives in statement_qa.group_check so the
    app and this tool can never disagree about what «verified» means."""
    flat = [{"page": p["page"],
             "own_debits": p["own"].get("debits"),
             "own_credits": p["own"].get("credits"),
             "own_balance": p["own"].get("balance"),
             "frame_debits": p["frame"].get("debits"),
             "frame_credits": p["frame"].get("credits"),
             "frame_balance": p["frame"].get("balance"),
             "usable": p["usable"]} for p in pages]
    groups = _verify_groups(flat)
    # keep the panel page numbers for the span's pages (same order)
    for g, _ in zip(groups, groups):
        pass
    return groups


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", default=None,
                    help="ملف JSON للنتيجة (افتراضياً بجوار التقرير)")
    args = ap.parse_args()

    results = Path(args.results)
    pages = load_pages(results)
    groups = verify_groups(pages)
    out = Path(args.out) if args.out else results.parent / "group_verification.json"
    out.write_text(json.dumps({"pages": len(pages), "groups": groups},
                              ensure_ascii=False, indent=2), encoding="utf-8")

    interesting = [g for g in groups
                   if g.get("covers_unreadable") or g["status"] == "undecidable"]
    print(f"[group-verify] صفحات: {len(pages)} · أزواج إطارات: {len(groups)} · "
          f"نطاقات تستحق العرض: {len(interesting)}")
    for g in interesting:
        pages_ar = "، ".join(str(p) for p in g["pages"])
        if g["status"] == "verified":
            print(f"  ✅ صارت موثّقة بالمجموع: {pages_ar} "
                  f"(بين الإطارين {g['bracket'][0]} و{g['bracket'][1]})")
        elif g["status"] == "mismatch":
            print(f"  ✗ نقص مقيس: {pages_ar} — مدين {g['diff_debits']} · "
                  f"دائن {g['diff_credits']} (رصيد مطابق: {g['balance_ok']})")
        else:
            print(f"  ◍ غير محسومة: {pages_ar} — {g['why']}")
    gained = sum(len(g["pages"]) for g in groups
                 if g["status"] == "verified" and g.get("covers_unreadable"))
    gaps = [g for g in groups if g["status"] == "mismatch"
            and g.get("covers_unreadable")]
    print(f"\nالحكم: {gained} صفحة كانت «غير قابلة للتحقق» صارت موثّقة بالمجموع؛ "
          f"{len(gaps)} نطاق بنقص مقيس (أوراق غائبة من المسح)؛ "
          f"{sum(1 for g in groups if g['status'] == 'undecidable')} نطاق غير محسوم. "
          f"الملف: {out}")


if __name__ == "__main__":
    main()
