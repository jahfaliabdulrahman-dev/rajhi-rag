#!/usr/bin/env python3
"""Validate a Gemini structure-aware re-read JSONL for a bank statement.

Input: JSONL where each line is
{"page": N, "rows": [{"date","desc_main","amount","balance"}, ...],
 "footer": {"debits","credits","balance"}}
with digits kept AS PRINTED (Arabic-Indic / Persian allowed).

Checks per page:
  1. Internal chain: |amt[i+1]| == |bal[i] - bal[i+1]| for every consecutive
     balance pair that has a parsed amount.
     INDEXING PITFALL: the balance prints AFTER the transaction, so the delta
     bal[i]-bal[i+1] belongs to row i+1 — checking it against row i yields a
     false 0% pass on a perfectly read page.
  2. Footer lock: footer.balance == last row balance (when both parse).

Number parsing (proven rules for Saudi bank prints):
  - Translate BOTH Arabic-Indic (٠-٩) AND Persian (۰-۹) digit ranges.
  - '.' present -> standard decimal point (2-digit frac expected).
  - No dot: digits after the LAST comma — 2 = decimal comma ("300,00" = 300.00,
    old-era pages), 3 = thousands separator ("2,900" = 2900), >3 = lost-dot
    case ("61,16512" = 61,165.12).

Usage: python validate_reread_chain.py reread.jsonl [--verbose]
Exit 0 if all chain pairs pass; 1 otherwise. Prints a per-page summary.
"""
import json
import re
import sys

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def norm_num(s):
    if s is None:
        return None
    t = str(s).translate(DIGITS)
    t = t.replace("٫", ".").replace("٬", ",").replace("،", ",")
    t = re.sub(r"[^0-9.,]", "", t)
    if not t:
        return None
    if "." in t:
        a, _, b = t.partition(".")
        a = a.replace(",", "")
        b = re.sub(r"\D", "", b)
        if len(b) == 2 and a:
            return round(float(a) + int(b) / 100, 2)
        if len(b) == 0 and a:
            return float(a)
        return None
    if "," in t:
        a, _, b = t.rpartition(",")
        a = a.replace(",", "")
        if len(b) == 2:
            return round(float(a) + int(b) / 100, 2) if a else float(b) / 100
        if len(b) == 3:
            return float(a) * 1000 + float(b) if a else float(b)
        if len(b) > 3:
            return round(float(a) * 1000 + float(b[:3]) + int(b[3:5]) / 100, 2)
        return float(a) if a else None
    return float(t)


def main():
    path = sys.argv[1]
    verbose = "--verbose" in sys.argv
    pages = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    total_pairs = total_ok = 0
    foot_ok = foot_total = 0
    bad_pages = []
    for gd in pages:
        grows = gd.get("rows") or []
        bals = [norm_num(r.get("balance")) for r in grows]
        amts = [norm_num(r.get("amount")) for r in grows]
        pairs = ok = 0
        for i in range(len(grows) - 1):
            if bals[i] is not None and bals[i + 1] is not None and amts[i + 1] is not None:
                pairs += 1
                if abs(abs(bals[i] - bals[i + 1]) - abs(amts[i + 1])) < 0.02:
                    ok += 1
        foot = gd.get("footer") or {}
        fbal = norm_num(foot.get("balance"))
        last = bals[-1] if bals else None
        if fbal is not None and last is not None:
            foot_total += 1
            if abs(fbal - last) < 0.02:
                foot_ok += 1
            else:
                bad_pages.append((gd["page"], "footer", fbal, last))
        if pairs and ok < pairs:
            bad_pages.append((gd["page"], "chain", ok, pairs))
        total_pairs += pairs
        total_ok += ok
        if verbose:
            print(f"p{gd['page']:3d}: chain {ok}/{pairs}  footer_bal={fbal} last_bal={last}")
    print(f"TOTAL: chain {total_ok}/{total_pairs} | footer lock {foot_ok}/{foot_total}")
    if bad_pages:
        print("FAILING PAGES:", bad_pages[:20])
    sys.exit(0 if total_ok == total_pairs else 1)


if __name__ == "__main__":
    main()
