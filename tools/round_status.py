#!/usr/bin/env python3
"""حالة جولة قراءة: تقدّم · كلفة · وقت متبقٍّ · جودة الشاهد الثاني.

لماذا: السؤال «فين وصلت الجولة؟» يُسأل كل بضع دقائق، وجوابه أرقام تتغيّر. هذه
الأداة تقرأ مجلد التشغيلة وتطبع الحالة كاملة في شاشة واحدة — بلا كلفة وبلا
استدعاء، لأنها تقرأ الكاش لا النموذج.

    python3 tools/round_status.py data/local_sample/slice_629p_v2
    python3 tools/round_status.py <dir> --watch 60     # تحديث كل دقيقة
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))

from statement_qa.row_audit import column_vs_chain  # noqa: E402
from statement_qa.vlm_reader import chain_derive  # noqa: E402


def dec(v):
    if v is None:
        return None
    try:
        return Decimal(str(v).replace(",", ""))
    except (ArithmeticError, ValueError):
        return None


def snapshot(run: Path, total: int) -> dict:
    files = sorted((run / "results").glob("pg-*.json"),
                   key=lambda p: int(p.stem.split("-")[1]))
    cost = Decimal("0")
    times: list[float] = []
    events: Counter = Counter()
    rows = cols = read_ok = clashes = 0
    prev = Decimal("0.00")
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue                             # ملف قيد الكتابة الآن
        cost += Decimal(str((data.get("usage") or {}).get("cost") or 0))
        ms = data.get("ms_read") or 0
        if ms:
            times.append(ms / 1000)
        if data.get("error"):
            events["أخطاء قراءة"] += 1
            continue
        if data.get("reread"):
            events["إعادة قراءة آلية"] += 1
        if data.get("recovered"):
            events["استدراك مرساة"] += 1
        if data.get("arbitrated_by"):
            events["تحكيم بشري"] += 1
        raw = [{**r, "movement": dec(r.get("movement")), "balance": dec(r.get("balance"))}
               for r in (data.get("raw_rows") or [])]
        der = chain_derive(raw, prev_balance=prev)
        for r in der:
            rows += 1
            if r.get("printed_col"):
                cols += 1
                if r.get("side") and r["printed_col"] == r["side"]:
                    read_ok += 1
        clashes += len(column_vs_chain(der))
        last = next((r["balance"] for r in reversed(der)
                     if r.get("balance") is not None), None)
        if last is not None:
            prev = last
    times.sort()
    med = times[len(times) // 2] if times else 0
    done = len(files)
    return {"done": done, "total": total, "cost": cost, "med": med,
            "rows": rows, "cols": cols, "read_ok": read_ok, "clashes": clashes,
            "events": dict(events),
            "left_s": (total - done) * med,
            "projected": (cost / done * total) if done else Decimal("0")}


def render(s: dict, run: Path) -> str:
    pct = 100 * s["done"] / max(s["total"], 1)
    bar = "█" * int(pct / 4) + "·" * (25 - int(pct / 4))
    lines = [
        f"الجولة: {run.name}",
        f"  [{bar}] {s['done']}/{s['total']} ({pct:.0f}%)",
        f"  الكلفة: ${s['cost']:.4f} · المتوقع للكل: ${s['projected']:.2f}",
        f"  وسيط زمن الصفحة: {s['med']:.1f} ث · المتبقي: "
        f"{s['left_s'] / 3600:.1f} ساعة",
    ]
    if s["cols"]:
        lines.append(
            f"  الشاهد الثاني: العمود مقروء في {s['cols']}/{s['rows']} "
            f"({100 * s['cols'] / s['rows']:.1f}%) · موافقة السلسلة "
            f"{s['read_ok']}/{s['cols']} · خلافات {s['clashes']}")
    if s["events"]:
        lines.append("  أحداث: " + " · ".join(f"{k} {v}" for k, v in s["events"].items()))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", help="مجلد التشغيلة")
    ap.add_argument("--total", type=int, default=629, help="عدد الصفحات الكلي")
    ap.add_argument("--watch", type=int, default=0, help="تحديث كل N ثانية")
    args = ap.parse_args()
    run = Path(args.run)
    if not (run / "results").exists():
        print(f"لا نتائج في {run}", file=sys.stderr)
        return 1
    while True:
        s = snapshot(run, args.total)
        out = render(s, run)
        print("\033[2J\033[H" + out if args.watch else out)
        if not args.watch:
            return 0 if s["done"] < s["total"] else 0
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
