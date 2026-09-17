#!/usr/bin/env python3
"""Prove that every footer claim can be re-derived from the stored evidence.

THE CLAIM THIS PROTECTS
The project's headline numbers — «621 documented pages, 0 shifted» — are put
in front of a reviewer as gate 5 of the handoff protocol. A reviewer must be
able to check them with one command. They could not: three pages stored a
corrected value beside an unchanged `raw` token, so a faithful re-derivation
returned 615 ok · 6 mismatch, and asked «which code produced this key?» of a
key (`footer_reread`) that existed in no line of the codebase.

WHAT THIS DOES
For every page checkpoint and every footer field it compares

    _parse_amount(footer.raw[field])   vs   Decimal(footer[field])

and demands one of two answers:
  1. equal — the stored value IS the evidence; or
  2. unequal but recorded in `arbitrated_by` with by/why/at/old/new — a human
     decision, written down, with the original reading preserved.

Anything else is a violation and the exit code is 1. Local, no API, no cost.

    python3 tools/verify_provenance.py --results data/local_sample/slice_629p/results
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))

from statement_qa.legacy.arabic_digit_parser import norm_num  # noqa: E402
from statement_qa.footer_oracle import FIELDS  # noqa: E402

REQUIRED_RECORD_KEYS = ("by", "why", "at", "field", "old_value", "new_value")


def _parse_raw(token) -> Decimal | None:
    if token in (None, ""):
        return None
    value = norm_num(token)
    return None if value is None else Decimal(str(value))


def audit(results: Path) -> dict:
    """-> {checked, unmarked[], bad_records[], arbitrated[]}."""
    checked = 0
    unmarked: list[tuple] = []
    bad_records: list[tuple] = []
    arbitrated: list[tuple] = []
    for cache in sorted(results.glob("pg-*.json")):
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            unmarked.append((cache.name, "cache", "كاش غير مقروء", None, None))
            continue
        footer = data.get("footer") or {}
        raw = footer.get("raw") or {}
        records = data.get("arbitrated_by") or []
        by_field = {}
        for rec in records:
            if not all(k in rec for k in REQUIRED_RECORD_KEYS):
                bad_records.append((cache.name, rec))
                continue
            by_field[rec["field"]] = rec
        for field in FIELDS:
            stored = footer.get(field)
            if stored is None:
                continue
            checked += 1
            parsed = _parse_raw(raw.get(field))
            if parsed is not None and parsed == Decimal(str(stored)):
                continue
            if field in by_field:
                arbitrated.append((cache.name, field, str(parsed), str(stored),
                                   by_field[field].get("by")))
            else:
                unmarked.append((cache.name, field, raw.get(field), stored,
                                 parsed))
    return {"checked": checked, "unmarked": unmarked,
            "bad_records": bad_records, "arbitrated": arbitrated}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", required=True)
    args = ap.parse_args()

    res = audit(Path(args.results))
    print(f"[verify-provenance] حقول فُحصت: {res['checked']} · "
          f"تحكيم موثَّق: {len(res['arbitrated'])} · "
          f"غير مبرَّر: {len(res['unmarked'])} · "
          f"سجلات ناقصة: {len(res['bad_records'])}")
    for name, field, parsed, stored, who in res["arbitrated"]:
        print(f"  موثَّق  {name} {field}: {parsed} → {stored}  (حكّمها: {who})")
    for name, field, token, stored, parsed in res["unmarked"]:
        print(f"  ✗ غير مبرَّر {name} {field}: الخام {token!r} "
              f"(يُحلّل {parsed}) مقابل المخزّن {stored}")
    for name, rec in res["bad_records"]:
        print(f"  ✗ سجل ناقص في {name}: {rec}")
    ok = not res["unmarked"] and not res["bad_records"]
    print("\nالحكم: " + ("كل رقم قابل لإعادة الاشتقاق من دليله." if ok else
                        "لا — يوجد رقم لا يسنده دليله ولا تحكيم موثَّق."))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
