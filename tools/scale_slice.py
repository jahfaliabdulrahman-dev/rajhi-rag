#!/usr/bin/env python3
"""Scale slice — the disciplined expansion instrument (what-if P2).

The sample was the 10 prettiest pages; a wider claim needs a measured slice.
Policy (from the workshop): 30–50 → 150 → full — never a leap. This tool:

1. extracts a CONSECUTIVE page range from the local full statement
   (local-only file; outputs stay under data/local_sample/, gitignored),
2. reads it page by page with the REAL pipeline (frozen FRONTIER read +
   footer oracle + chain + era + order) — same code paths as the app,
3. measures per page: rows · suspects · footer verdict · era style · wall
   time · USD cost (OpenRouter usage),
4. STOP-GATES (barriers, not warnings):
      ×100 paradox on any page            → STOP immediately
      suspect ratio in the last N pages   → STOP when above 20%
      cost budget exceeded                → STOP
5. CHECKPOINTS every page (results/pg-XXX.json) — a rerun resumes without
   re-calling the VLM (cost honesty), recomputing deterministic parts.

Reports: <out>/slice_report.json + slice_report.md (Arabic).

Usage:
    ./venv/bin/python tools/scale_slice.py --first 1 --count 30
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))

from statement_qa.era import fingerprint_pages, summarize_ar as era_ar  # noqa: E402
from statement_qa.footer_oracle import (  # noqa: E402
    FooterReading, check_page_footer, read_footer,
)
from statement_qa.ordering import check_order, summarize_ar as order_ar  # noqa: E402
from statement_qa.vlm_reader import (  # noqa: E402
    chain_derive, read_rows_vlm, recover_anchor,
)

DEFAULT_SOURCE = None  # resolved at startup: --source, else a LOCAL pointer file


def _resolve_source(arg: str | None) -> str:
    """--source wins; else the gitignored local pointer
    (data/local_sample/.slice_source) — the real filename never enters git."""
    if arg:
        return str(Path(arg).expanduser())
    local = PROJ / "data" / "local_sample" / ".slice_source"
    if local.exists():
        return str(Path(local.read_text(encoding="utf-8").strip()).expanduser())
    raise SystemExit(
        "حدّد مصدر الكشف: --source <path>  (أو اكتب المسار في "
        "data/local_sample/.slice_source)")


# ————— tiny JSON codec for Decimal-bearing rows —————

def row_to_json(r: dict) -> dict:
    out = {}
    for k, v in r.items():
        out[k] = str(v) if isinstance(v, Decimal) else v
    return out


def row_from_json(d: dict) -> dict:
    def dec(x):
        if x is None or isinstance(x, Decimal):
            return x
        try:
            return Decimal(str(x))
        except Exception:
            return None
    return {**d,
            "movement": dec(d.get("movement")),
            "balance": dec(d.get("balance"))}


def _sum_dicts(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, (int, float)):
            out[k] = round(out.get(k, 0) + v, 6)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="measured scale slice")
    ap.add_argument("--source", default=None,
                    help="local full statement PDF (or .slice_source pointer)")
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--out", default=None)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--max-cost", type=float, default=3.0,
                    help="USD budget cap (usage.cost)")
    ap.add_argument("--stop-window", type=int, default=5)
    ap.add_argument("--stop-suspect-ratio", type=float, default=0.2)
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args()

    out = Path(args.out) if args.out else (
        PROJ / "data" / "local_sample" / f"slice_{args.count}p")
    pages_dir = out / "pages"
    results_dir = out / "results"
    pages_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    source = _resolve_source(args.source)
    t_start = time.time()

    # ————— 1. extract + render —————
    from pypdf import PdfReader, PdfWriter

    pdf_path = out / f"slice_{args.count}p.pdf"
    if not pdf_path.exists():
        src = PdfReader(source)
        writer = PdfWriter()
        last = min(args.first - 1 + args.count, len(src.pages))
        for i in range(args.first - 1, last):
            writer.add_page(src.pages[i])
        with open(pdf_path, "wb") as fh:
            writer.write(fh)
        print(f"[extract] pages {args.first}..{last} -> {pdf_path.name}",
              flush=True)

    from pdf2image import convert_from_path

    page_pngs: list[Path] = []
    for i in range(args.count):
        png = pages_dir / f"pg-{args.first + i:03d}.png"
        if not png.exists():
            imgs = convert_from_path(str(pdf_path), dpi=args.dpi,
                                     first_page=i + 1, last_page=i + 1)
            imgs[0].save(png)
        page_pngs.append(png)

    # ————— 2. per-page read (checkpointed) —————
    usage_total = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                   "cost": 0.0}
    stop_reason = None
    per_page = []

    prev_closing = None
    cum = {"debits": Decimal("0"), "credits": Decimal("0")}
    cum_broken = False
    era_pages: dict[int, list] = {}
    page_dates: dict[int, list] = {}
    boundaries = {"txn": 0, "carry": 0, "anchor": 0}
    window: list[int] = []       # suspect count per page (stop-gate)
    window_rows: list[int] = []  # read row count per page (stop-gate)
    recoveries: list[dict] = []  # boundary anchors resolved by verified reread
    n_rows = n_ok = n_susp = 0
    f_ok = f_bad = f_unchecked = f_absent = 0

    for i, png in enumerate(page_pngs):
        pg = args.first + i
        cache = results_dir / f"pg-{pg:03d}.json"
        if cache.exists() and not args.no_resume:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("error"):
                cum_broken = True
                window.append(1)
                window_rows.append(1)
                per_page.append({"page": pg, "rows": 0, "suspects": None,
                                 "footer": "unchecked", "error": data["error"],
                                 "origin": "cache"})
                print(f"[p{pg}] cached FAILED: {data['error']}", flush=True)
                continue
            ms_read = data.get("ms_read", 0)
            ms_footer = data.get("ms_footer", 0)
            raw_rows = [row_from_json(r) for r in data["raw_rows"]]
            footer = None
            if data.get("footer"):
                fd = data["footer"]
                footer = FooterReading(
                    debits=Decimal(fd["debits"]) if fd.get("debits") else None,
                    credits=Decimal(fd["credits"]) if fd.get("credits") else None,
                    balance=Decimal(fd["balance"]) if fd.get("balance") else None,
                    raw=fd.get("raw") or {})
            usage_total = _sum_dicts(usage_total, data.get("usage") or {})
            origin = "cache"
        else:
            st_r, st_f = {}, {}
            t0 = time.time()
            try:
                raw_rows = read_rows_vlm(str(png), stats=st_r)
            except Exception as e:  # page failed — honest, keeps going
                cache.write_text(json.dumps(
                    {"pg": pg, "error": f"{type(e).__name__}: {e}"},
                    ensure_ascii=False), encoding="utf-8")
                print(f"[p{pg}] READ FAILED: {e}", flush=True)
                cum_broken = True
                window.append(1)       # a missing page weighs like a suspect
                window_rows.append(1)
                per_page.append({"page": pg, "rows": 0, "suspects": None,
                                 "footer": "unchecked", "error": str(e),
                                 "origin": "live"})
                continue
            ms_read = int((time.time() - t0) * 1000)
            t0 = time.time()
            try:
                footer = read_footer(str(png), stats=st_f)
            except Exception:
                footer = None
            ms_footer = int((time.time() - t0) * 1000)
            usage = _sum_dicts({"calls": 1}, st_r)
            usage = _sum_dicts(usage, st_f or {})
            usage_total = _sum_dicts(usage_total, usage)
            cache.write_text(json.dumps({
                "pg": pg, "ms_read": ms_read, "ms_footer": ms_footer,
                "raw_rows": [row_to_json(r) for r in raw_rows],
                "footer": ({"debits": str(footer.debits) if footer.debits is not None else None,
                            "credits": str(footer.credits) if footer.credits is not None else None,
                            "balance": str(footer.balance) if footer.balance is not None else None,
                            "raw": footer.raw} if footer else None),
                "usage": usage,
            }, ensure_ascii=False), encoding="utf-8")
            origin = "live"

        rows = chain_derive(raw_rows, prev_balance=prev_closing)
        # مرساة حدّية غير محسومة؟ استدراك مقيد — يُقبل فقط إذا أغلقت السلسلة.
        if pg > args.first and rows and rows[0].get("boundary") == "anchor":
            rst: dict = {}
            patched, recovered = recover_anchor(
                raw_rows, prev_closing, str(png), pg, rst)
            if rst:
                usage_total = _sum_dicts(
                    usage_total, _sum_dicts({"calls": 1}, rst))
            if recovered is not None:
                raw_rows = patched
                rows = chain_derive(raw_rows, prev_balance=prev_closing)
                recoveries.append({"page": pg, "amount": str(recovered)})
                if cache.exists():  # لا تُعِد القراءة عند الاستئناف القادم
                    data = json.loads(cache.read_text(encoding="utf-8"))
                    if not data.get("error"):
                        data["raw_rows"] = [row_to_json(r) for r in raw_rows]
                        data["recovered"] = str(recovered)
                        cache.write_text(json.dumps(data, ensure_ascii=False),
                                         encoding="utf-8")
        prev_closing = next((r["balance"] for r in reversed(rows)
                             if r["balance"] is not None), prev_closing)
        if pg > args.first and rows:
            b = rows[0].get("boundary")
            if b in boundaries:
                boundaries[b] += 1
        era_pages[pg] = [t for r in rows
                         for t in (r.get("raw_movement"), r.get("raw_balance"))
                         if t]
        page_dates[pg] = [r.get("date") for r in rows]

        chk = check_page_footer(rows, footer, prior=cum, skip=cum_broken)
        if chk.get("own"):
            cum["debits"] += chk["own"]["debits"]
            cum["credits"] += chk["own"]["credits"]

        p_rows = [r for r in rows if r["balance"] is not None]
        p_susp = sum(1 for r in p_rows if not r["ok"])
        n_rows += len(p_rows)
        n_ok += len(p_rows) - p_susp
        n_susp += p_susp
        window.append(p_susp)
        window_rows.append(len(p_rows))
        window = window[-args.stop_window:]
        window_rows = window_rows[-args.stop_window:]

        st = chk["status"]
        f_ok += st == "ok"
        f_bad += st == "mismatch"
        f_unchecked += st == "unchecked"
        f_absent += st == "absent"

        per_page.append({
            "page": pg, "rows": len(p_rows), "suspects": p_susp,
            "footer": st, "footer_detail": chk.get("diffs"),
            "paradox": bool(chk.get("is_paradox")),
            "ms_read": ms_read, "ms_footer": ms_footer, "origin": origin,
        })
        print(f"[p{pg}] rows={len(p_rows)} suspects={p_susp} "
              f"footer={st}{' PARADOX' if chk.get('is_paradox') else ''} "
              f"({origin}, {ms_read + ms_footer}ms, "
              f"cum ${usage_total.get('cost', 0):.4f})", flush=True)

        # ————— stop-gates —————
        if chk.get("is_paradox"):
            stop_reason = f"زيغ ×100 على صفحة {pg} — تحقق يدوي فوري"
            break
        if len(window) == args.stop_window and sum(window_rows) > 0:
            ratio = sum(window) / sum(window_rows)
            if ratio > args.stop_suspect_ratio:
                stop_reason = (f"نسبة الشكوك في آخر {args.stop_window} صفحات "
                               f"{ratio:.0%} > {args.stop_suspect_ratio:.0%}")
                break
        if usage_total.get("cost", 0.0) >= args.max_cost:
            stop_reason = f"تجاوز سقف الميزانية ${args.max_cost}"
            break

    # ————— 3. report —————
    era_fp = fingerprint_pages(era_pages)
    order = check_order(page_dates)
    elapsed = round(time.time() - t_start, 1)
    clean_ratio = (n_ok / n_rows) if n_rows else 0.0
    report = {
        "slice": {"first": args.first, "count": args.count,
                  "pages_done": len(per_page)},
        "totals": {"rows": n_rows, "clean": n_ok, "suspects": n_susp,
                   "clean_ratio": round(clean_ratio, 4)},
        "footer": {"ok": f_ok, "mismatch": f_bad, "unchecked": f_unchecked,
                   "absent": f_absent},
        "era": {"overall": era_fp["overall"], "styles": era_fp["styles"],
                "transitions": era_fp["transitions"],
                "outliers": era_fp["outliers"]},
        "order": {"cross": order["cross"], "intra": order["intra"],
                  "coverage": order["coverage"], "boundaries": boundaries},
        "boundary_recoveries": recoveries,
        "time": {"elapsed_s": elapsed,
                 "avg_page_s": round(elapsed / max(1, len(per_page)), 1)},
        "usage": usage_total,
        "stop_reason": stop_reason,
        "per_page": per_page,
    }
    (out / "slice_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        f"# تقرير سلايس {args.count} صفحة (صفحات {args.first}–{args.first + args.count - 1})",
        "",
        f"**أُنجز:** {len(per_page)} صفحة في {elapsed} ث "
        f"(≈{report['time']['avg_page_s']} ث/صفحة) · "
        f"**التكلفة الفعلية:** ${usage_total.get('cost', 0):.4f}",
        "",
        "| المقياس | القيمة |",
        "|---|---|",
        f"| الصفوف | {n_rows} |",
        f"| نظيف السلسلة | {n_ok}  ({clean_ratio:.1%}) |",
        f"| مشبوه | {n_susp} |",
        f"| أوراكل الفوتر | {f_ok} مطابق · {f_bad} غير مطابق · {f_unchecked} غير قابل للتحقق · {f_absent} غير مقروء |",
        f"| الصيغ | {era_ar(era_fp)} |",
        f"| الترتيب | {order_ar(order, boundaries)} |",
        "",
    ]
    if recoveries:
        md.append("**استُدركت مراسٍ حدّية (reread مُتحقق):** "
                  + "، ".join(f"ص{r['page']} ({r['amount']})" for r in recoveries)
                  + " — القيم المُصححة أغلقَت السلسلة إغلاقاً تاماً.")
    if stop_reason:
        md.append(f"⛔ **توقف حاجز:** {stop_reason}")
    else:
        md.append("✅ **اجتاز السلايس حواجز التوقف.**")
    (out / "slice_report.md").write_text("\n".join(md), encoding="utf-8")

    print(f"\nSLICE DONE: {len(per_page)} pages | clean {n_ok}/{n_rows} "
          f"({clean_ratio:.1%}) | footer {f_ok} ok/{f_bad} bad | "
          f"${usage_total.get('cost', 0):.4f} | {elapsed}s"
          + (f" | STOPPED: {stop_reason}" if stop_reason else ""), flush=True)
    sys.exit(2 if stop_reason else 0)


if __name__ == "__main__":
    main()
