#!/usr/bin/env python3
"""مقارنة جولتَي قراءة: أيّهما يوافق الورق — صفحةً صفحة، لا انطباعاً.

لماذا هكذا
----------
تطابق المجاميع ليس دليلاً: قراءةٌ **مُزاحة** (مبلغ كل صفّ مربوط بالوصف الذي قبله)
تُعطي المجموع نفسه وتخالف الورق. فالمعيار هنا مزدوج:

1. **إغلاق السلسلة** لكل صفّ: `amount[i] == balance[i−1] − balance[i]` — السلسلة
   مطبوعة في الورق ولا يمكن إزاحتها كلها وتبقى مغلقة. نسبة الإغلاق هي الحاكم الأول.
2. **شاهد التذييل المطبوع** لكل صفحة (مدين/دائن/رصيد): كلاهما أم لا.

والقرار صفحةً صفحة: تُتبنّى القراءة الأعلى إغلاقاً **إذا** وافق تذييلها؛ وإلا بقيت
القديمة وخرجت الصفحة إلى قائمة «لا يُحكم عليها» — ولا تُخفيها التقارير.

    python3 tools/compare_rounds.py --old <dir> --new <dir> [--out report.md]
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

TOL = Decimal("0.005")
ZERO = Decimal("0")


def dec(v):
    if v is None:
        return None
    try:
        return Decimal(str(v).replace(",", ""))
    except (ArithmeticError, ValueError):
        return None


def load(run: Path) -> tuple[dict, dict]:
    rep = json.loads((run / "slice_report.json").read_text(encoding="utf-8"))
    arb = {e["page"]: e for e in rep.get("per_page", [])}
    rows = {}
    for f in (run / "results").glob("pg-*.json"):
        try:
            p = int(f.stem.split("-")[1])
            rows[p] = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return arb, rows


def page_stats(page: int, rows: dict, prev: Decimal):
    """إغلاق السلسلة · مجاميع مدين/دائن · رصيد الخروج · عدد الصفوف."""
    data = rows.get(page) or {}
    raw = [{**r, "movement": dec(r.get("movement")), "balance": dec(r.get("balance"))}
           for r in (data.get("raw_rows") or [])]
    der = chain_derive(raw, prev_balance=prev)
    checked = closed = 0
    debits = credits = ZERO
    for r in der:
        d, m = r.get("derived_movement"), r.get("movement")
        if d is not None and m is not None:
            checked += 1
            if abs(d - m) <= TOL:
                closed += 1
        side = r.get("side")
        if d is not None and side == "debit":
            debits += d
        elif d is not None and side == "credit":
            credits += d
    exit_bal = next((r["balance"] for r in reversed(der)
                     if r.get("balance") is not None), None)
    return {"rows": len(raw), "checked": checked, "closed": closed,
            "debits": debits, "credits": credits, "exit": exit_bal,
            "error": bool(data.get("error"))}


def footer_ok(entry: dict | None) -> bool | None:
    """شاهد التذييل: None = لا شاهد (لا يُحكم)."""
    if not entry:
        return None
    if entry.get("error"):
        return False
    det = entry.get("footer_detail")
    if det:
        return all(d.get("ok") for d in det)
    val = str(entry.get("footer") or "")
    return {"ok": True, "mismatch": False}.get(val)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--pages", type=int, default=629)
    args = ap.parse_args()

    old_run, new_run = Path(args.old), Path(args.new)
    old_arb, old_rows = load(old_run)
    new_arb, new_rows = load(new_run)

    prev_o = prev_n = Decimal("0.00")
    buckets: dict[str, list[int]] = {}
    lines = ["| صفحة | صفوف (ق/ج) | إغلاق القديمة | إغلاق الجديدة | تذييل ق/ج | الحكم |",
             "|---|---|---|---|---|---|"]
    tot = {"old_rows": 0, "new_rows": 0}
    for p in range(1, args.pages + 1):
        o = page_stats(p, old_rows, prev_o)
        n = page_stats(p, new_rows, prev_n)
        fo, fn = footer_ok(old_arb.get(p)), footer_ok(new_arb.get(p))
        tot["old_rows"] += o["rows"]
        tot["new_rows"] += n["rows"]

        rate_o = o["closed"] / o["checked"] if o["checked"] else None
        rate_n = n["closed"] / n["checked"] if n["checked"] else None

        if rate_o is None and rate_n is None:
            verdict = "لا صفوف"
        elif n["error"]:
            verdict = "الجديدة أخفقت ⇒ القديمة"
        elif rate_n is not None and (rate_o is None or rate_n > rate_o + 0.001) and fn is not False:
            verdict = "الجديدة أدقّ ✓"
        elif rate_o is not None and (rate_n is None or rate_o > rate_n + 0.001):
            verdict = "القديمة أدقّ"
        elif o["debits"] == n["debits"] and o["credits"] == n["credits"] \
                and o["rows"] == n["rows"]:
            verdict = "متطابقتان"
        else:
            verdict = "فرق بلا حسم ⇒ القديمة"
        buckets.setdefault(verdict.split(" ✓")[0], []).append(p)

        if verdict != "متطابقتان":
            f = lambda x: "—" if x is None else f"{100 * x:.0f}%"      # noqa: E731
            lines.append(
                f"| {p} | {o['rows']}/{n['rows']} | {f(rate_o)} | {f(rate_n)} | "
                f"{fo}/{fn} | {verdict} |")

        if o["exit"] is not None:
            prev_o = o["exit"]
        if n["exit"] is not None:
            prev_n = n["exit"]

    head = [
        f"# مقارنة جولتين — {old_run.name} ↔ {new_run.name}",
        "",
        f"- صفوف القديمة: **{tot['old_rows']}** · صفوف الجديدة: **{tot['new_rows']}** "
        f"(الفرق {tot['new_rows'] - tot['old_rows']:+d})",
    ]
    for k in sorted(buckets, key=lambda k: -len(buckets[k])):
        head.append(f"- {k}: **{len(buckets[k])}** صفحة")
    report = "\n".join(head + ["", "## الصفحات التي تحتاج قراراً", ""] + lines) + "\n"

    print("\n".join(head))
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"\nالتقرير الكامل: {args.out} · صفحات تحتاج قراراً: {len(lines) - 2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
