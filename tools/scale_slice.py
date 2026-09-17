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
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))

from statement_qa.era import fingerprint_pages, summarize_ar as era_ar  # noqa: E402
from statement_qa.footer_oracle import (  # noqa: E402
    FooterReading, check_page_footer, delta_checkable, delta_status,
    page_diverged, read_footer, try_page_reread,
)
from statement_qa.verification import format_effects  # noqa: E402
from statement_qa.ordering import (  # noqa: E402
    check_order, check_page_numbers, summarize_ar as order_ar,
    summarize_page_numbers,
)
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


# A ledger holds cost and tokens — nothing else. The old version summed ANY
# numeric key, so a stray `page_no` from the reader's stats landed in the cost
# ledger as a field called «page_no = 3422» (audit P2-2).
_USAGE_KEYS = ("calls", "request_calls", "cost", "prompt_tokens",
               "completion_tokens", "cached_tokens")


def _sum_dicts(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in (b or {}).items():
        if k in _USAGE_KEYS and isinstance(v, (int, float)):
            out[k] = round(out.get(k, 0) + v, 6)
    return out


def partial_first_status(pg: int, first: int) -> dict | None:
    """The verdict for the FIRST page of a partial run: none — and say so (P2-6).

    A window that starts at page 424 has no previous page, so the cumulative
    comparison measures that single page against the whole statement and
    reports «mismatch» — a false alarm that opened every investigation window
    and made a clean window look dirty in the notes.
    """
    if pg == first and first > 1:
        return {"status": "unchecked", "compared": 0,
                "reason": "أول صفحة في تشغيل جزئي — لا جار سابق للدلتا"}
    return None


def _read_cache(cache: Path) -> dict | None:
    """Checkpoint read that treats a damaged file as «unreadable», not a crash.

    An unguarded json.loads turned one interrupted write into a dead run whose
    only recovery was deleting a paid-for page (audit P2-4).
    """
    try:
        return json.loads(cache.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json_atomic(path: Path, obj) -> None:
    """temp file + os.replace: a half-written checkpoint can never be read."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _cache_facts(results_dir: Path) -> dict:
    """Durable facts from the page checkpoints, not from this process (P2-1).

    A replay costs no money and no VLM seconds, so building the report from
    session state made a previously measured run claim «0.0 s/page» and «no
    recoveries» — three fields erased by the very operation advertised as free.
    Recoveries, re-reads and per-page milliseconds live in the checkpoints;
    session elapsed time is reported separately and never mixed in.
    """
    recs, rds, times, arbs = [], [], [], []
    for f in sorted(results_dir.glob("pg-*.json")):
        d = _read_cache(f) or {}
        if d.get("recovered"):
            recs.append({"page": d.get("pg"), "amount": str(d["recovered"])})
        if d.get("reread"):
            rds.append({"page": d.get("pg")})
        for a in (d.get("arbitrated_by") or []):
            arbs.append({"page": d.get("pg"), "field": a.get("field"),
                         "by": a.get("by"), "why": a.get("why")})
        if d.get("ms_read"):
            times.append(int(d["ms_read"]) + int(d.get("ms_footer") or 0))
    times.sort()
    median = (times[len(times) // 2] / 1000) if times else 0.0
    return {"recoveries": recs, "rereads": rds, "arbitrations": arbs,
            "median_page_s": round(median, 2), "timed_pages": len(times)}


def _bump_usage(cache: Path, extra: dict) -> None:
    """Record an OPTIONAL call's usage into the page's cache.

    The printed session counter only sees calls a page's cache carries; failed
    attempts, boundary recoveries and page re-reads are real charges too.
    Persisting them keeps a replay's totals honest (cost fidelity > counter).
    """
    if not cache.exists() or not extra:
        return
    d = _read_cache(cache)
    if d is None:
        return
    d["usage"] = _sum_dicts(d.get("usage") or {}, extra)
    _write_json_atomic(cache, d)


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
    ap.add_argument("--retry-errors", action="store_true",
                    help="إعادة محاولة الصفحات المخزّنة بخطأ — للاستئناف بعد انقطاع مزود/نفاد رصيد")
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
    fail_streak = 0              # consecutive read failures (provider gate)
    recoveries: list[dict] = []  # boundary anchors resolved by verified reread
    page_rereads: list[dict] = []  # pages re-read and accepted by footer delta
    page_nos: list[tuple[int, int | None]] = []  # (scan position, printed page no)
    prev_footer = None
    prev_page_no: int | None = None
    n_rows = n_ok = n_susp = 0
    f_ok = f_bad = f_unchecked = f_absent = f_gap = 0

    for i, png in enumerate(page_pngs):
        pg = args.first + i
        cache = results_dir / f"pg-{pg:03d}.json"
        reread_rejected = False
        anchor_rejected = False
        use_cache = cache.exists() and not args.no_resume
        data = None
        if use_cache:
            data = _read_cache(cache)
            if data is None:   # damaged checkpoint ≠ dead run (audit P2-4)
                print(f"[p{pg}] كاش غير مقروء — إعادة قراءة نظيفة", flush=True)
                use_cache = False
            elif data.get("error"):
                if args.retry_errors:
                    print(f"[p{pg}] إعادة محاولة خطأ سابق: {data['error']}",
                          flush=True)
                    use_cache = False
                else:
                    cum_broken = True
                    window.append(1)
                    window_rows.append(1)
                    per_page.append({"page": pg, "rows": 0, "suspects": None,
                                     "footer": "unchecked",
                                     "error": data["error"],
                                     "origin": "cache"})
                    print(f"[p{pg}] cached FAILED: {data['error']}", flush=True)
                    continue
        if use_cache and data is not None:
            ms_read = data.get("ms_read", 0)
            ms_footer = data.get("ms_footer", 0)
            reread_rejected = bool(data.get("reread_rejected"))
            anchor_rejected = bool(data.get("anchor_rejected"))
            page_no = data.get("page_no")
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
                prev_usage = ((_read_cache(cache) or {}).get("usage") or {})
                _write_json_atomic(cache, {
                    "pg": pg, "error": f"{type(e).__name__}: {e}",
                    "usage": _sum_dicts(prev_usage,
                                        _sum_dicts({"calls": 1}, st_r))})
                print(f"[p{pg}] READ FAILED: {e}", flush=True)
                cum_broken = True
                window.append(1)       # a missing page weighs like a suspect
                window_rows.append(1)
                per_page.append({"page": pg, "rows": 0, "suspects": None,
                                 "footer": "unchecked", "error": str(e),
                                 "origin": "live"})
                fail_streak += 1
                if fail_streak >= 5:
                    stop_reason = ("5 صفحات متتالية أخفقت قراءتها — "
                                   "افحص المزود/الرصيد ثم استأنف بـ --retry-errors")
                    break
                continue
            fail_streak = 0
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
            page_no = st_r.get("page_no")
            _write_json_atomic(cache, {
                "pg": pg, "ms_read": ms_read, "ms_footer": ms_footer,
                "page_no": page_no,
                "raw_rows": [row_to_json(r) for r in raw_rows],
                "footer": ({"debits": str(footer.debits) if footer.debits is not None else None,
                            "credits": str(footer.credits) if footer.credits is not None else None,
                            "balance": str(footer.balance) if footer.balance is not None else None,
                            "raw": footer.raw} if footer else None),
                "usage": usage,
            })
            origin = "live"

        rows = chain_derive(raw_rows, prev_balance=prev_closing)
        # مرساة حدّية غير محسومة؟ استدراك مقيد — يُقبل فقط إذا أغلقت السلسلة.
        if (pg > args.first and rows and rows[0].get("boundary") == "anchor"
                and not anchor_rejected):
            rst: dict = {}
            patched, recovered = recover_anchor(
                raw_rows, prev_closing, str(png), pg, rst)
            if rst:
                usage_total = _sum_dicts(
                    usage_total, _sum_dicts({"calls": 1}, rst))
                _bump_usage(cache, _sum_dicts({"calls": 1}, rst))
            cdata = _read_cache(cache) or {}
            if recovered is not None:
                raw_rows = patched
                rows = chain_derive(raw_rows, prev_balance=prev_closing)
                recoveries.append({"page": pg, "amount": str(recovered)})
                if cache.exists() and not cdata.get("error"):
                    cdata["raw_rows"] = [row_to_json(r) for r in raw_rows]
                    cdata["recovered"] = str(recovered)
                    _write_json_atomic(cache, cdata)
            elif rst and cache.exists() and not cdata.get("error"):
                # attempted and REFUSED: without this, EVERY replay of the
                # slice pays for the same two calls again (audit P2-2).
                cdata["anchor_rejected"] = True
                _write_json_atomic(cache, cdata)
        page_nos.append((pg, page_no))
        gap_missing: list[int] = []
        if (isinstance(page_no, int) and isinstance(prev_page_no, int)
                and page_no > prev_page_no + 1):
            # المسح قفز أوراقاً: المطبوع بينهما غائب ⇒ دلتا الإطار التالية
            # تقيس حركاتها وليست خطأ قراءة في هذه الصفحة.
            gap_missing = list(range(prev_page_no + 1, page_no))

        # تحكيم الصفحة: الانزياح عن الفوتر يُطلق قراءة جديدة واحدة — تُقبل
        # فقط بلا شكوك + مطابقة دلتا الفوتر (معزولة عن أي تلوث سابق).
        if (not reread_rejected and pg > args.first and not gap_missing
                and page_diverged(rows, cum, prev_footer, footer, cum_broken)):
            pst: dict = {}
            fresh_raw, accepted, note = try_page_reread(
                str(png), cum, prev_footer, footer, prev_closing, pst)
            usage_total = _sum_dicts(usage_total, _sum_dicts({"calls": 1}, pst))
            _bump_usage(cache, _sum_dicts({"calls": 1}, pst))
            if accepted and fresh_raw is not None:
                raw_rows = fresh_raw
                rows = chain_derive(raw_rows, prev_balance=prev_closing)
                if (pg > args.first and rows
                        and rows[0].get("boundary") == "anchor"):
                    rst2: dict = {}
                    patched2, rec2 = recover_anchor(
                        raw_rows, prev_closing, str(png), pg, rst2)
                    if rst2:
                        usage_total = _sum_dicts(
                            usage_total, _sum_dicts({"calls": 1}, rst2))
                        _bump_usage(cache, _sum_dicts({"calls": 1}, rst2))
                    if rec2 is not None:
                        raw_rows = patched2
                        rows = chain_derive(raw_rows, prev_balance=prev_closing)
                        recoveries.append({"page": pg, "amount": str(rec2)})
                page_rereads.append({"page": pg, "note": note})
            if cache.exists():
                cdata = _read_cache(cache) or {}
                if not cdata.get("error"):
                    if accepted and fresh_raw is not None:
                        cdata["raw_rows"] = [row_to_json(r) for r in raw_rows]
                        cdata["reread"] = note
                    else:
                        cdata["reread_rejected"] = note
                    _write_json_atomic(cache, cdata)
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
        _partial = partial_first_status(pg, args.first)
        if _partial:
            chk = _partial
        # أساس التقرير = **دلتا الصفحة** متى توفّرت: تعزل الصفحة عن أي تلوث
        # تراكمي سابق، فتبقى الحقيقة ظاهرة بعد أي انقطاع. التراكمي بديل فقط.
        if delta_checkable(prev_footer, footer):
            dchk = delta_status(rows, prev_footer, footer)
            if dchk["status"] != "unchecked":
                chk = {**chk, **dchk, "basis": "delta"}
        elif chk.get("status") == "mismatch":
            # لا دلتا (إطار الجار غير مقروء) ⇒ الانحراف قد يأتي من جارنا لا منا،
            # ولا سبيل لعزل هذه الصفحة: «غير قابلة للتحقق» أصدق من «منزاحة».
            # تُحفظ الفروق كدليل للعين لكن لا تُحتسب إزاحةً على هذه الصفحة.
            chk = {**chk, "status": "unchecked"}
        if gap_missing and delta_checkable(prev_footer, footer):
            # قفزة في الترقيم المطبوع ⇒ الفرق المقيس = حركات الأوراق الغائبة
            # (كمّها الإطار)، لا خلل في قراءة هذه الصفحة.
            chk = {**chk, "status": "gap", "basis": "delta",
                   "missing_sheets": gap_missing}
        if chk.get("own"):
            cum["debits"] += chk["own"]["debits"]
            cum["credits"] += chk["own"]["credits"]
        prev_footer = footer
        prev_page_no = page_no

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
        f_gap += st == "gap"

        per_page.append({
            "page": pg, "rows": len(p_rows), "suspects": p_susp,
            "footer": st, "footer_detail": chk.get("diffs"),
            "paradox": bool(chk.get("is_paradox")),
            "page_no": page_no,
            "missing_sheets": chk.get("missing_sheets"),
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
    # ————— دفتر التكلفة الحقيقي —————
    # مجموع ما سُجّل في كاش كل صفحة (قراءة + فوتر + محاولات + استدراكات + إعادات).
    # العدّاد المطبوع لكل جلسة وحده يُسقط المحاولات والاستدراكات — الدفتر لا.
    ledger = {"calls": 0, "cost": 0.0}
    for f in sorted(results_dir.glob("pg-*.json")):
        try:
            u = (json.loads(f.read_text(encoding="utf-8")).get("usage") or {})
        except Exception:
            continue
        ledger = _sum_dicts(ledger, u)

    _verdict_pages = {c["page"]: c["status"] for c in footer_checks}
    _era_effects = format_effects(
        _verdict_pages,
        sorted({p["page"] for p in per_page if p.get("suspects")}))
    facts = _cache_facts(results_dir)
    report = {
        "slice": {"first": args.first, "count": args.count,
                  "pages_done": len(per_page)},
        "totals": {"rows": n_rows, "clean": n_ok, "suspects": n_susp,
                   "clean_ratio": round(clean_ratio, 4)},
        "footer": {"ok": f_ok, "mismatch": f_bad, "unchecked": f_unchecked,
                   "absent": f_absent, "gap": f_gap},
        "page_numbers": check_page_numbers(page_nos),
        "era": {"overall": era_fp["overall"], "styles": era_fp["styles"],
                "transitions": era_fp["transitions"],
                "outliers": era_fp["outliers"]},
        "order": {"cross": order["cross"], "intra": order["intra"],
                  "coverage": order["coverage"], "boundaries": boundaries},
        "boundary_recoveries": facts["recoveries"],
        "page_rereads": facts["rereads"],
        "arbitrations": facts["arbitrations"],
        "session": {"recoveries": recoveries, "page_rereads": page_rereads,
                    "elapsed_s": elapsed},
        "time": {"elapsed_s": elapsed,
                 "session_elapsed_s": elapsed,
                 "median_page_s": facts["median_page_s"],
                 "timed_pages": facts["timed_pages"],
                 "avg_page_s": round(elapsed / max(1, len(per_page)), 1)},
        "usage": usage_total,
        "usage_ledger": ledger,
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
        f"**التكلفة:** هذه الجلسة ${usage_total.get('cost', 0):.4f} · "
        f"دفتر الصفحات **${ledger.get('cost', 0):.4f}** "
        f"({ledger.get('calls', 0)} استدعاء مسجَّل)",
        "",
        "| المقياس | القيمة |",
        "|---|---|",
        f"| الصفوف | {n_rows} |",
        f"| نظيف السلسلة | {n_ok}  ({clean_ratio:.1%}) |",
        f"| مشبوه | {n_susp} |",
        f"| أوراكل الفوتر | {f_ok} مطابق · {f_bad} غير مطابق · {f_gap} فجوة مسح · {f_absent} بلا إطار · {f_unchecked} غير قابل للتحقق |",
        f"| تغطية التحقق | {f_ok + f_bad} من {len(per_page)} صفحة حُكِمت مقابل إطارها |",
        f"| زمن الصفحة (وسيط مُخزَّن) | {report['time']['median_page_s']} ث على {report['time']['timed_pages']} صفحة |",
        f"| الصيغ | {era_ar(era_fp, _era_effects)} |",
        f"| الترتيب | {order_ar(order, boundaries)} |",
        "",
    ]
    pn_report = report["page_numbers"]
    md.append(f"**الترقيم المطبوع:** {summarize_page_numbers(pn_report)}")
    md.append("")
    if report["boundary_recoveries"]:
        md.append("**استُدركت مراسٍ حدّية (reread مُتحقق):** "
                  + "، ".join(f"ص{r['page']} ({r['amount']})"
                              for r in report["boundary_recoveries"])
                  + " — القيم المُصححة أغلقَت السلسلة إغلاقاً تاماً.")
    if report["page_rereads"]:
        md.append("**أُعيدت قراءة صفحات وتحكيمها بدلتا الفوتر:** "
                  + "، ".join(f"ص{r['page']}" for r in report["page_rereads"])
                  + " — قُبلت قراءاتٌ بلا شكوك تُطابق دلتا الفوتر إطالةً تامة.")
    if report["session"]["recoveries"] or report["session"]["page_rereads"]:
        md.append(f"(هذه الجلسة: {len(report['session']['recoveries'])} استدراك · "
                  f"{len(report['session']['page_rereads'])} إعادة قراءة — "
                  f"الأرقام أعلاه من الكاش وتبقى بعد أي replay.)")
    if report["arbitrations"]:
        md.append("**تحكيم بشري موثَّق (كل رقم يُعاد اشتقاقه من دليله):** "
                  + "، ".join(f"ص{a['page']}/{a['field']}"
                              for a in report["arbitrations"])
                  + " — التفاصيل في `arbitrated_by` داخل كاش الصفحة "
                  + "(by · why · at · old/new).")
    if stop_reason:
        md.append(f"⛔ **توقف حاجز:** {stop_reason}")
    else:
        md.append("✅ **اجتاز السلايس حواجز التوقف.**")
    (out / "slice_report.md").write_text("\n".join(md), encoding="utf-8")

    print(f"\nSLICE DONE: {len(per_page)} pages | clean {n_ok}/{n_rows} "
          f"({clean_ratio:.1%}) | footer {f_ok} ok/{f_bad} bad"
          + (f"/{f_gap} gap" if f_gap else "") + " | "
          f"session ${usage_total.get('cost', 0):.4f} | "
          f"ledger ${ledger.get('cost', 0):.4f} | {elapsed}s"
          + (f" | الترقيم: {summarize_page_numbers(pn_report)}"
             if (pn_report["gaps"] or pn_report["duplicates"]
                 or pn_report["backwards"]) else "")
          + (f" | STOPPED: {stop_reason}" if stop_reason else ""), flush=True)
    sys.exit(2 if stop_reason else 0)


if __name__ == "__main__":
    main()
