#!/usr/bin/env python3
"""Record a human arbitration of a printed footer total — with its provenance.

WHY THIS EXISTS
The footer oracle re-derives every claim from stored evidence, and the whole
claim «621 documented · 0 shifted» is only honest if that re-derivation works.
On three pages it did not: the oracle's field held the CORRECT value while the
`raw` token next to it still held the model's misread, so anyone re-deriving
from the repository got 615 ok · 6 mismatch — and no code produced the key that
explained the difference. The verdict was right; the evidence chain was broken.

WHAT A HUMAN DOES — and this is the whole of it
The machine says «this page shifts from its footer»; the fix is to look at the
printed sheet and read one number. That is the arbitration. The tool then
writes the number AND who decided AND why, keeps the original reading beside
it, and the re-derivation works for anyone again. High-uncertainty, low-volume
cases only — never a way to edit a number quietly.

    python3 tools/arbitrate_footer.py --results <dir> --page 491 \\
        --field credits --value 9001.00 \\
        --why "أثر 100.00 في خانة واحدة — رصده المالك بعينه" \\
        --by "المالك + قراءة إطار طازجة" --evidence docs/suspects_log.md

Rules enforced here:
1. `--why` is mandatory: no arbitration without a written reason.
2. The new value MUST differ from the stored one, or there is nothing to record.
3. The original raw token is preserved (`raw_original`), never overwritten.
4. Existing legacy markers (`footer_reread`) are folded into the record instead
   of being left as keys no code produces.
5. Writes are atomic (temp + os.replace), like every other checkpoint write.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))

from statement_qa.legacy.arabic_digit_parser import norm_num  # noqa: E402
from statement_qa.footer_oracle import FIELDS  # noqa: E402

REQUIRED_RECORD_KEYS = ("by", "why", "at", "field", "old_value", "new_value")


def _parse_raw(token: str | None) -> Decimal | None:
    if token in (None, ""):
        return None
    value = norm_num(token)
    return None if value is None else Decimal(str(value))


def arbitrate(results: Path, page: int, field: str, value: str, why: str,
              by: str, evidence: str = "") -> dict:
    cache = results / f"pg-{page:03d}.json"
    if not cache.exists():
        raise SystemExit(f"لا يوجد كاش للصفحة {page}: {cache}")
    if not why.strip():
        raise ValueError("لا تحكيم بلا سبب مكتوب (--why إلزامي).")
    data = json.loads(cache.read_text(encoding="utf-8"))
    footer = data.get("footer")
    if not footer:
        raise SystemExit(f"الصفحة {page} بلا إطار مُخزَّن — لا شيء لتحكيمه.")
    if field not in FIELDS:
        raise SystemExit(f"حقل غير معروف: {field} (المتوقع أحد {list(FIELDS)})")
    new = Decimal(str(value))
    stored = footer.get(field)
    raw = (footer.get("raw") or {}).get(field)
    parsed_raw = _parse_raw(raw)
    # Two different jobs, one command. (a) The value in the cache is wrong →
    # correct it. (b) The value is already right but the stored EVIDENCE
    # (`raw`) says something else — which is exactly the state an earlier
    # manual fix left behind: correct number, broken chain. Case (b) must be
    # recordable, because otherwise the fix can never be re-derived.
    if (stored is not None and Decimal(str(stored)) == new
            and (parsed_raw is None or parsed_raw == new)):
        raise SystemExit(
            f"القيمة المخزّنة ({new}) تساوي الخام المقروء أيضاً — لا فرق ولا "
            f"انقطاع في الإثبات، فلا شيء لتسجيله.")
    record = {
        "by": by,
        "why": why,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "field": field,
        "old_value": str(stored),
        "new_value": str(new),
        "raw_token": raw,
        "raw_parsed": str(parsed_raw) if parsed_raw is not None else None,
        "evidence": evidence,
    }
    # keep the printed token as the primary evidence, and a copy under an
    # explicit name so nobody has to guess which one was the model's output
    footer.setdefault("raw_original", {})
    if raw is not None:
        footer["raw_original"].setdefault(field, raw)
    footer[field] = str(new)
    legacy = data.pop("footer_reread", None)
    if legacy:
        record["legacy_footer_reread"] = legacy
    records = data.get("arbitrated_by") or []
    records.append(record)
    data["arbitrated_by"] = records
    tmp = cache.with_suffix(cache.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, cache)
    return record


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", required=True, help="مجلد results للكاش")
    ap.add_argument("--page", type=int, required=True)
    ap.add_argument("--field", required=True, choices=list(FIELDS))
    ap.add_argument("--value", required=True, help="القيمة المطبوعة الصحيحة")
    ap.add_argument("--why", required=True, help="السبب (إلزامي)")
    ap.add_argument("--by", default="المالك", help="مَن حكّم")
    ap.add_argument("--evidence", default="", help="دليل (ملف/صورة/ملاحظة)")
    args = ap.parse_args()

    rec = arbitrate(Path(args.results), args.page, args.field, args.value,
                    args.why, args.by, args.evidence)
    print("سُجِّل التحكيم:")
    for k in REQUIRED_RECORD_KEYS + ("raw_token", "raw_parsed", "evidence"):
        print(f"  {k}: {rec.get(k)}")
    print("\nشغّل مدقّق الإثبات للتأكد: "
          "python3 tools/verify_provenance.py --results "
          f"{args.results}")


if __name__ == "__main__":
    main()
