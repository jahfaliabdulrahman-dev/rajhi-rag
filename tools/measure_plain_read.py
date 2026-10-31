"""What a plain request gets from the same model on the synthetic statement — the page's baseline (step 5b).

The system's reader model is asked, page by page, the request a student would write ("extract every
transaction as JSON"), with no balance chain and no footer check. Its answer is then compared with the
ledger the system wrote for the same statement. The point is not whether the model reads well: it is
what the answer alone lets you know about which of its numbers are right.

    python3 tools/measure_plain_read.py --budget 0.15 --out docs/measurements/plain-read.json

Each run is appended to `--out` with the rows the model returned (the statement is synthetic).

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
    want_amounts = Counter(number(r["movement"]) for r in expected if r.get("movement"))
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
        "breaks_inside_the_answer": breaks,
        "rows_with_other_fields": sum(1 for r in returned if set(r) - {"date", "description", "amount", "balance"}),
    }


def flagged_rows(expected: list[dict], returned: list[dict]) -> list[dict]:
    """For each row the chain flagged: did the plain answer carry the printed amount, the balances' difference, or neither?"""
    got = {abs(a) for a in (number(r.get("amount")) for r in returned) if a is not None}
    out = []
    for r in expected:
        if r.get("chain_ok") is False and r.get("movement"):
            printed, derived = number(r["movement"]), number(r["derived_movement"])
            out.append({"seq": r["seq"], "page": r["page"],
                        "answer_has_printed_amount": printed in got,
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
    ap.add_argument("--budget", type=float, required=True, help="dollars; no call starts that could pass it")
    args = ap.parse_args(argv)

    from statement_qa.api_key import get_api_key
    from statement_qa.vlm_reader import MODEL, chat_vlm_image

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    key = get_api_key("RAJHI_EVAL_OPENROUTER_KEY")
    spent, worst, pages = 0.0, FIRST_CALL_ESTIMATE, []
    for page in range(1, int(ledger["n_pages"]) + 1):
        if spent + worst * 1.5 > args.budget:
            print(f"stopped before page {page}: spent {spent:.4f} + next {worst * 1.5:.4f} > budget {args.budget}")
            break
        stats: dict = {}
        answer = chat_vlm_image(_page_b64(args.pdf, page), PLAIN_PROMPT, max_tokens=6000, stats=stats, api_key=key)
        cost = float(stats.get("cost") or 0.0)
        spent += cost
        worst = max(worst if pages else 0.0, cost)
        expected = [r for r in ledger["rows"] if r["page"] == page]
        returned = rows_of(answer)
        pages.append({"page": page, "cost": round(cost, 6), **compare(expected, returned),
                      "flagged": flagged_rows(expected, returned), "returned_rows": returned})
        print(f"page {page}: rows {len(returned)}/{len(expected)} · cost {cost:.4f}")

    totals = {k: sum(p[k] for p in pages) for k in
              ("rows_expected", "rows_returned", "balances_expected", "balances_matched",
               "amounts_expected", "amounts_matched", "breaks_inside_the_answer", "rows_with_other_fields")}
    record = {"measured_on": date.today().isoformat(), "model": MODEL, "prompt": PLAIN_PROMPT,
              "render_dpi": RENDER_DPI, "statement": ledger["source"], "source_sha256": ledger["source_sha256"],
              "pages_read": len(pages), "pages_total": int(ledger["n_pages"]), "spent": round(spent, 6),
              "budget": args.budget, "totals": totals, "pages": pages}
    # Each run is appended: the same request on the same page need not return the same figures twice.
    runs = json.loads(args.out.read_text(encoding="utf-8"))["runs"] if args.out.exists() else []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"runs": runs + [record]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("totals:", json.dumps(totals), f"· spent {spent:.4f} of {args.budget}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
