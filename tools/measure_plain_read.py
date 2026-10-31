"""What a plain request gets from the same model on a statement page — the story page's baseline.

The system's reader model is asked, page by page, the request a student would write ("extract every
transaction as JSON"), with no balance chain and no footer check. Its answer is then compared with the
ledger the system wrote for the same statement. The point is not whether the model reads well: it is
what the answer alone lets you know about which of its numbers are right.

    python3 tools/measure_plain_read.py --budget 0.15 --out docs/measurements/plain-read.json
    python3 tools/measure_plain_read.py --pdf <run>/slice_629p.pdf --ledger docs/measurements/real-page-43.json \
        --pages 43 --runs 2 --budget 0.05 --out docs/measurements/real-plain-read.json --rows-out <scratch>/rows.json

Each run is appended to `--out`, numbered. With `--rows-out` the rows the model returned are appended there
instead, under the same run number, so a real page's figures stay on the owner's machine, `--out` holds counts
only, and any run can be recounted. `--runs` repeats the same request
under one budget: the same request on the same page need not return the same figures twice.

Same model (`vlm_reader.MODEL`), same transport (`chat_vlm_image`), same page images (200 DPI, as the app).
Paid with the evaluation key only (RAJHI_EVAL_OPENROUTER_KEY), and it stops before a call that could pass
`--budget`. Prints counts only, never a figure from the statement.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import sys
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PLAIN_PROMPT = ("This is one page of a scanned bank statement. Extract every transaction on it as a JSON array "
                "of objects with the keys date, description, amount and balance. Return only the JSON.")
RENDER_DPI = 200            # app.RENDER_DPI: the page images the system itself reads
AMOUNTS_BASIS = ("the system's reading where the chain holds; the balance difference for a flagged row between two "
                 "rows the chain holds; any other flagged row is left out (amounts_unknown)")
FIRST_CALL_ESTIMATE = 0.03  # before any call is priced, assume one page costs this much
_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def number(value) -> Decimal | None:
    """A printed or returned figure as a Decimal: Arabic-Indic digits, the Arabic separators and commas read."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).translate(_INDIC).replace("٫", ".").replace("٬", "").replace(",", "")
    text = re.sub(r"[^\d.\-]", "", text)
    if text.count(".") > 1:
        head, _, tail = text.rpartition(".")
        text = head.replace(".", "") + "." + tail
    try:
        return Decimal(text) if text not in {"", ".", "-"} else None
    except InvalidOperation:
        return None


def rows_of(answer: str) -> list[dict]:
    """The JSON array in the model's answer (fences and prose around it ignored); [] when there is none."""
    match = re.search(r"\[.*\]", answer or "", re.S)
    if not match:
        return []
    try:
        rows = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return [r for r in rows if isinstance(r, dict)]


def compare(expected: list[dict], returned: list[dict]) -> dict:
    """Counts only. `expected` are the ledger's rows of one page, `returned` the model's."""
    got_balances = Counter(b for b in (number(r.get("balance")) for r in returned) if b is not None)
    got_amounts = Counter(abs(a) for a in (number(r.get("amount")) for r in returned) if a is not None)
    # The opening balance is not a transaction, and the request asks for transactions only.
    want_balances = Counter(number(r["balance"]) for r in expected if r.get("balance") and not r.get("opening"))
    # Which amount is right (AMOUNTS_BASIS): where the chain holds, the reading; where it broke between two rows it
    # holds, the balances on both sides agree with their neighbours, so the balance difference; any other break
    # could be a misread balance, and that row is left out rather than scored against a guess.
    want_amounts, unknown = Counter(), 0
    for i, r in enumerate(expected):
        if not r.get("movement"):
            continue
        if r.get("chain_ok") is not False:
            want_amounts[number(r["movement"])] += 1
        elif 0 < i < len(expected) - 1 and expected[i - 1].get("chain_ok") and expected[i + 1].get("chain_ok"):
            want_amounts[number(r["derived_movement"])] += 1
        else:
            unknown += 1
    breaks = 0
    for prev, cur in zip(returned, returned[1:]):
        b0, b1, a = number(prev.get("balance")), number(cur.get("balance")), number(cur.get("amount"))
        if None not in (b0, b1, a) and abs(b1 - b0) != abs(a):
            breaks += 1
    return {
        "rows_expected": len(expected),
        "rows_returned": len(returned),
        "balances_expected": sum(want_balances.values()),
        "balances_matched": sum((want_balances & got_balances).values()),
        "amounts_expected": sum(want_amounts.values()),
        "amounts_matched": sum((want_amounts & got_amounts).values()),
        "amounts_unknown": unknown,
        "breaks_inside_the_answer": breaks,
        "rows_with_other_fields": sum(1 for r in returned if set(r) - {"date", "description", "amount", "balance"}),
    }


def flagged_rows(expected: list[dict], returned: list[dict]) -> list[dict]:
    """For each row the chain flagged: did the plain answer carry the system's own (wrong) reading of the amount,
    the balances' difference, or neither?"""
    got = {abs(a) for a in (number(r.get("amount")) for r in returned) if a is not None}
    out = []
    for r in expected:
        if r.get("chain_ok") is False and r.get("movement"):
            systems, derived = number(r["movement"]), number(r["derived_movement"])
            out.append({"seq": r["seq"], "page": r["page"],
                        "answer_has_systems_reading": systems in got,
                        "answer_has_balance_difference": derived in got})
    return out


def _page_b64(pdf: Path, page: int) -> str:
    from pdf2image import convert_from_path

    image = convert_from_path(str(pdf), dpi=RENDER_DPI, first_page=page, last_page=page)[0]
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", type=Path, default=ROOT / "data" / "sample" / "statement_showcase.pdf")
    ap.add_argument("--ledger", type=Path, default=ROOT / "data" / "sample" / "statement_showcase.ledger.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--budget", type=float, required=True, help="dollars, for all runs; no call starts that could pass it")
    ap.add_argument("--pages", type=int, nargs="+", default=None, help="the pages to read (all pages by default)")
    ap.add_argument("--runs", type=int, default=1, help="how many times the same request is made")
    ap.add_argument("--rows-out", type=Path, default=None, help="where the returned rows go instead of --out")
    args = ap.parse_args(argv)

    from statement_qa.api_key import get_api_key
    from statement_qa.vlm_reader import MODEL, chat_vlm_image

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    key = get_api_key("RAJHI_EVAL_OPENROUTER_KEY")
    wanted = args.pages or list(range(1, int(ledger["n_pages"]) + 1))
    empty = [page for page in wanted if not any(r["page"] == page for r in ledger["rows"])]
    if empty:
        print(f"refused before any call: no expected rows for page(s) {empty} in {args.ledger.name}")
        return 2
    runs = json.loads(args.out.read_text(encoding="utf-8"))["runs"] if args.out.exists() else []
    kept = json.loads(args.rows_out.read_text(encoding="utf-8")) if args.rows_out and args.rows_out.exists() else []
    spent, worst, records = 0.0, FIRST_CALL_ESTIMATE, []
    for run in range(args.runs):
        pages = []
        for page in wanted:
            if spent + worst * 1.5 > args.budget:
                print(f"stopped before run {run + 1} page {page}: spent {spent:.4f} + next {worst * 1.5:.4f} > budget {args.budget}")
                break
            stats: dict = {}
            answer = chat_vlm_image(_page_b64(args.pdf, page), PLAIN_PROMPT, max_tokens=6000, stats=stats, api_key=key)
            cost = float(stats.get("cost") or 0.0)
            worst = max(worst if (pages or records) else 0.0, cost)
            spent += cost
            expected = sorted((r for r in ledger["rows"] if r["page"] == page), key=lambda r: r["seq"])
            returned = rows_of(answer)
            entry = {"page": page, "cost": round(cost, 6), **compare(expected, returned),
                     "flagged": flagged_rows(expected, returned)}
            if args.rows_out:
                kept.append({"run": len(runs) + len(records) + 1, "page": page, "returned_rows": returned})
            else:
                entry["returned_rows"] = returned
            pages.append(entry)
            print(f"run {run + 1} page {page}: rows {len(returned)}/{len(expected)} · cost {cost:.4f}")
        if not pages:
            break
        totals = {k: sum(p[k] for p in pages) for k in
                  ("rows_expected", "rows_returned", "balances_expected", "balances_matched", "amounts_expected",
                   "amounts_matched", "amounts_unknown", "breaks_inside_the_answer", "rows_with_other_fields")}
        records.append({"run": len(runs) + len(records) + 1,
                        "measured_on": date.today().isoformat(), "model": MODEL, "prompt": PLAIN_PROMPT,
                        "render_dpi": RENDER_DPI, "statement": ledger["source"], "source_sha256": ledger["source_sha256"],
                        "pages_read": [p["page"] for p in pages], "pages_total": int(ledger["n_pages"]),
                        "spent": round(sum(p["cost"] for p in pages), 6), "budget": args.budget,
                        "amounts_basis": AMOUNTS_BASIS, "rows_kept": "elsewhere" if args.rows_out else "here",
                        "totals": totals, "pages": pages})
        print("totals:", json.dumps(totals))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"runs": runs + records}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if args.rows_out:
        args.rows_out.write_text(json.dumps(kept, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"spent {spent:.4f} of {args.budget} over {len(records)} run(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
