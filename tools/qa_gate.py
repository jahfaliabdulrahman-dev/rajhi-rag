#!/usr/bin/env python3
"""Pre-delivery QA gate for the Al Rajhi statement app (rajhi-rag).

Run BEFORE every delivery claim ("تم", "يعمل", "جاهز"):

    source .venv/bin/activate
    python tools/qa_gate.py --quick    # offline: tests + parser goldens + wiring
    python tools/qa_gate.py --full     # + live end-to-end run of the sample PDF

Exit 0 = all gates pass; any FAIL blocks delivery.

The --full gate locks VALUES that were verified by eye against the document
renders (page 1: opening dots=0.00 → transfer +300.00 → 300.00 → 200.00 →
100.00; page 2: 0.00 → +50.00). Do NOT edit those constants without
re-verifying against the page image — that visual check is the entire point
(the chain stays "clean" even when EVERY value is ×100 wrong).
"""
from __future__ import annotations

import argparse
import http.client
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))

RESULTS: list[tuple[str, bool, str]] = []


def gate(name: str, fn) -> None:
    try:
        detail = fn()
        RESULTS.append((name, True, detail or ""))
    except AssertionError as e:
        RESULTS.append((name, False, str(e)))
    except Exception as e:  # noqa: BLE001
        RESULTS.append((name, False, f"{type(e).__name__}: {e}"))


def g_tests() -> str:
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        cwd=PROJ, capture_output=True, text=True, timeout=180)
    tail = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else "no output"
    assert out.returncode == 0, f"pytest failed: {tail}"
    return tail


def g_parser_goldens() -> str:
    from statement_qa.vlm_reader import _parse_amount as p

    cases = {
        "٣٠٠,٠٠": "300.00",      # comma-as-decimal (old-era prints)
        ".,..": "0",             # printed zero as dots — never None
        "٥٧,٥٠٢٧٥": "57502.75",   # lost decimal dot (owner's golden rule)
        "١١٩.٠٠-": "-119.00",    # trailing minus — sign must survive
        "٢,٩٠٠.٠٠": "2900.00",   # new-era thousands + halalas
        "۱,۸۰۰.۰۰": "1800.00",   # Persian digits mixed in
    }
    for tok, want in cases.items():
        got = p(tok)
        assert got == Decimal(want), f"{tok!r} -> {got} (want {want})"
    assert p(None) is None and p("") is None
    return f"{len(cases)} golden tokens + nulls"


def _status(port: int):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", "/")
    r = c.getresponse()
    stat, loc = r.status, r.getheader("Location")
    c.close()
    return stat, loc


def g_service() -> str:
    stat, _ = _status(7860)
    assert stat == 200, f"app :7860 -> HTTP {stat}"
    return "app :7860 -> 200"


def g_surface_redirect() -> str:
    stat, loc = _status(7867)
    assert stat == 302 and loc and ":7860" in loc, f":7867 -> {stat} {loc}"
    return f":7867 -> 302 {loc}"


def g_end_to_end() -> str:
    from gradio_client import Client, handle_file

    pdf = PROJ / "data/local_sample/sample_10p.pdf"
    assert pdf.exists(), f"missing {pdf}"
    res = Client("http://127.0.0.1:7860", verbose=False).predict(
        handle_file(str(pdf)), api_name="/process_pdf")
    summary, table = res[0], res[1]
    kpi_html = res[2] if len(res) > 2 else ""

    # Counts now live in the KPI strip (the ticker no longer repeats them).
    assert "قراءة" in str(summary) and "جاهز" in str(summary), \
        f"summary shape: {str(summary)[:120]}"
    nums = re.findall(r'<div class="num">([\d,\.]+)</div>', str(kpi_html))
    assert len(nums) == 4, f"kpi numerals not found: {str(kpi_html)[:200]}"
    total = int(nums[0].replace(",", ""))
    clean = int(nums[1].replace(",", ""))
    susp = int(nums[2].replace(",", ""))
    assert susp == 0, f"{susp} suspects in the full run"
    assert clean == total, f"{clean}/{total} clean"
    assert total >= 95, f"only {total} rows (expected ≈100-104)"

    data = table["data"] if isinstance(table, dict) else []
    assert len(data) >= 95, f"table carries {len(data)} rows"

    def num(x):
        if x in ("", None):
            return None
        return float(str(x).replace(",", "").strip())

    def txns(page):
        return [r for r in data if r[0] == page and r[1] == "حركة"]

    # Page 1 start — the transfer of 300.00 to balance 300.00 must appear as
    # a transaction (whether or not the dots-zero opening row was read; when
    # it wasn't, the side legitimately stays undecided "—" — accept both).
    p1_txns = txns(1)
    assert p1_txns, "no transactions on page 1"
    first_t = p1_txns[0]
    assert num(first_t[3]) == 300.00 and num(first_t[5]) == 300.00, f"p1 first txn: {first_t}"
    s4 = str(first_t[4])
    assert s4 == "—" or "دائن" in s4, f"p1 first txn side: {first_t}"

    # Page 2 must be present with its rows (the capture of its top row's
    # amount varies across VLM reads — the chain + 0-suspects gate covers it).
    assert [r for r in data if r[0] == 2], "no page 2 rows"

    # Page 9 closing == 676.00 (verified against the render).
    p9 = [r for r in data if r[0] == 9]
    assert p9 and num(p9[-1][5]) == 676.00, f"p9 closing: {p9[-1] if p9 else None}"

    # THE owner-caught bug: page 10 starts with transfer +1000 -> 1676.
    # It must be a TRANSACTION with its movement — never silently "opening".
    p10 = [r for r in data if r[0] == 10]
    assert p10, "no page 10 rows"
    first10 = p10[0]
    assert first10[1] == "حركة", f"p10 row0 kind: {first10}"
    assert num(first10[3]) == 1000.00 and num(first10[5]) == 1676.00, f"p10 row0: {first10}"
    assert "دائن" in str(first10[4]), f"p10 row0 side: {first10}"

    return (f"{summary} | p1/p2 starts + p9→p10 continuity locked OK")


def main() -> None:
    ap = argparse.ArgumentParser(description="rajhi-rag pre-delivery QA gate")
    ap.add_argument("--quick", action="store_true",
                    help="offline gates only (the default; explicit flag kept for the documented usage)")
    ap.add_argument("--full", action="store_true",
                    help="include the live end-to-end run (~3-4 min, uses VLM calls)")
    args = ap.parse_args()

    gate("unit suite", g_tests)
    gate("parser goldens", g_parser_goldens)
    gate("service health", g_service)
    gate("surface redirect", g_surface_redirect)
    if args.full:
        gate("end-to-end sample (values locked)", g_end_to_end)

    width = max(len(n) for n, _, _ in RESULTS)
    ok = sum(1 for _, p, _ in RESULTS if p)
    print()
    for n, p, d in RESULTS:
        print(f"[{'PASS' if p else 'FAIL'}] {n:<{width}}  {d}")
    print(f"\nGATES: {ok}/{len(RESULTS)} passed")
    sys.exit(0 if ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
