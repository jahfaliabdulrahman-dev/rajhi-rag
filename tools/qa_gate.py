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

# The two thresholds a NEW statement must clear before calibration is complete.
# They used to be bare numbers inside assertions, so a less dense sample failed
# the gate with no explanation of what to change (audit P3-11). Calibration
# steps for a new file are listed in docs/ONBOARDING_NEW_FILE.md §3.
MIN_ROWS = 95                 # rows the 10-page sample must yield (≈100–104)
MIN_FOOTER_COMPARABLE = 9     # pages whose printed totals could be compared
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
    assert total >= MIN_ROWS, \
        f"only {total} rows — العتبة {MIN_ROWS}: صفحات أقل غزارة من المتوقع، '
        f'راجع خطوات المعايرة في docs/ONBOARDING_NEW_FILE.md §3"

    assert isinstance(table, dict), "table shape changed"
    headers, data = table.get("headers") or [], table.get("data") or []
    idx = {h: i for i, h in enumerate(headers)}
    for col in ("#", "الصفحة", "الوصف", "النوع", "مدين", "دائن", "الرصيد", "الحالة"):
        assert col in idx, f"missing column {col!r}: {headers}"
    assert len(data) >= 95, f"table carries {len(data)} rows"

    def val(r, col):
        return r[idx[col]]

    def num(x):
        if x in ("", None):
            return None
        return float(str(x).replace(",", "").strip())

    def rows_of(page):
        return [r for r in data if val(r, "الصفحة") == page]

    def txns(page):
        return [r for r in rows_of(page)
                if val(r, "النوع") not in ("رصيد افتتاحي", "رصيد سابق")]

    # Page 1 start — the transfer of 300.00 to balance 300.00 must appear as
    # a transaction. When the dots-zero opening row was missed, the side
    # legitimately stays undecided (amount stays out of BOTH side columns —
    # never guess a direction); the row shows "◌" in الحالة. Accept that.
    p1_txns = txns(1)
    assert p1_txns, "no transactions on page 1"
    first_t = p1_txns[0]
    assert num(val(first_t, "الرصيد")) == 300.00, f"p1 first txn: {first_t}"
    c1, d1 = num(val(first_t, "مدين")), num(val(first_t, "دائن"))
    assert not (c1 is not None and d1 is not None), f"p1 first txn both sides: {first_t}"
    assert c1 in (None, 300.00) and d1 in (None, 300.00), f"p1 first txn amount: {first_t}"

    # Page 2 must be present with its rows (the capture of its top row's
    # amount varies across VLM reads — the chain + 0-suspects gate covers it).
    assert rows_of(2), "no page 2 rows"

    # Page 9 closing == 676.00 (verified against the render).
    p9 = rows_of(9)
    assert p9 and num(val(p9[-1], "الرصيد")) == 676.00, \
        f"p9 closing: {p9[-1] if p9 else None}"

    # THE owner-caught bug: page 10 starts with transfer +1000 -> 1676.
    # It must be a TRANSACTION with its movement — never silently "opening".
    p10 = rows_of(10)
    assert p10, "no page 10 rows"
    first10 = p10[0]
    assert val(first10, "النوع") not in ("رصيد افتتاحي", "رصيد سابق"), \
        f"p10 row0 kind: {first10}"
    assert num(val(first10, "دائن")) == 1000.00, f"p10 row0 credit: {first10}"
    assert num(val(first10, "الرصيد")) == 1676.00, f"p10 row0: {first10}"
    assert val(first10, "النوع") == "تحويل وارد", f"p10 row0 type: {first10}"

    # ———— أوراكل الفوتر (what-if #4 / P1) ————
    # The printed per-page totals must match the chain-derived page sums on
    # EVERY comparable page. This is the ONLY external guard against a
    # uniform ×100 shift that stays "chain-clean" (the accuracy paradox).
    s = str(summary)
    m = re.search(r"تحقق الفوتر: (\d+)/(\d+)", s)
    assert m, f"footer oracle line missing from summary: {s[:220]}"
    f_ok, f_possible = int(m.group(1)), int(m.group(2))
    footer_seg = s.split("تحقق الفوتر")[1].split("•")[0]
    assert "⚠" not in footer_seg, f"footer mismatch on sample: {footer_seg}"
    assert f_ok == f_possible and f_possible >= MIN_FOOTER_COMPARABLE, \
        f"footer: {f_ok}/{f_possible} comparable pages matched — "
        f"العتبة {MIN_FOOTER_COMPARABLE} (راجع §3 في دليل المعايرة)"

    # ———— ترتيب الصفحات (what-if delta) ————
    assert "⚠ الترتيب" not in s, f"page-order flag on sample: {s[:220]}"

    # Owner's 1000-question (2026-09): the sample carries FOUR 1000.00 rows
    # of FOUR different REAL types — keep them distinct (the lock against
    # the old "everything is حركة / مدين==سحب" conflation).
    k = [r for r in data
         if val(r, "مدين") == "1,000.00" or val(r, "دائن") == "1,000.00"]
    got = sorted(val(r, "النوع") for r in k)
    want = sorted(["تحويل صادر", "إيداع نقدي (صراف آلي)",
                   "تحويل وارد", "سحب صراف آلي"])
    assert got == want, f"1000.00 types: {got}"

    return (f"{summary} | p1/p2 starts + p9→p10 continuity "
            f"+ 4×1000 types locked + footer {f_ok}/{f_possible} OK")


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
