#!/usr/bin/env python3
"""مقابلةُ تلقينتَي القارئ (v1 · v2) على صفحاتٍ من **مجموعة الحجز** — لقرار FM-2.

السؤال: أيّ تلقينةٍ تكون الافتراض؟ والقياس هنا لا يعدّ الصفوف فقط، بل يقيس
**معيار القبول عندنا**: هل تُقفل السلسلة؟ وهل يوافق ما قُرئ ما هو مُثبت؟

ولماذا الحجز (page % N == 0): لأن ما يُقاس عليه الفرقُ لا يجوز أن يكون مما
تدرّب عليه القرار — وهي القاعدة نفسها التي بُنيت في التقاط العيّنات.

    python3 tools/compare_prompts.py --run data/local_sample/slice_629p --count 24
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src"), str(PROJ / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from statement_qa.vlm_reader import PROMPTS, chain_derive, read_rows_vlm  # noqa: E402


def _dec(v):
    try:
        return Decimal(str(v)) if v is not None else None
    except Exception:                       # noqa: BLE001 — قيمة غير رقمية تُعلن لا تُخمَّن
        return None


def _page_rows(run: Path, pg: int) -> list[dict]:
    f = run / "results" / f"pg-{pg:03d}.json"
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8")).get("raw_rows") or []


def _prev_balance(run: Path, pg: int) -> Decimal | None:
    """آخر رصيدٍ مُثبت قبل الصفحة — يسير للخلف عند فجوة."""
    for back in range(1, 6):
        rows = _page_rows(run, pg - back)
        if rows:
            return _dec(rows[-1].get("balance"))
    return None


def measure_page(run: Path, pg: int, prompt: str) -> dict:
    img = run / "pages" / f"pg-{pg:03d}.png"
    certified = _page_rows(run, pg)
    stamp = {"page": pg, "rows_certified": len(certified)}
    t0 = time.time()
    try:
        rows = read_rows_vlm(str(img), prompt=prompt)
    except Exception as exc:                # noqa: BLE001
        return stamp | {"error": f"{type(exc).__name__}: {exc}"[:160]}
    stamp["rows_read"] = len(rows)
    stamp["seconds"] = round(time.time() - t0, 1)
    prev = _prev_balance(run, pg)
    derived = chain_derive([{**r} for r in rows], prev_balance=prev)
    verified = [r for r in derived if (r.get("side") or "") in ("debit", "credit")]
    stamp["rows_chain_verified"] = len(verified)
    # مطابقة ما قُرئ بما هو مُثبت: نفس زوج (المبلغ, الرصيد) — لا ترتيبٌ ولا نصّ
    got = {(str(_dec(r.get("movement"))), str(_dec(r.get("balance")))) for r in rows}
    want = {(str(_dec(r.get("movement"))), str(_dec(r.get("balance"))))
            for r in certified}
    stamp["pairs_matching_certified"] = len(got & want)
    stamp["pairs_certified"] = len(want)
    stamp["last_balance_equals_certified"] = (
        bool(rows) and bool(certified)
        and _dec(rows[-1].get("balance")) == _dec(certified[-1].get("balance")))
    return stamp


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--count", type=int, default=24)
    ap.add_argument("--holdout-mod", type=int, default=3)
    ap.add_argument("--set", choices=("holdout", "training"), default="holdout",
                    help=("من أين تُسحَب الصفحات: `holdout` لقياسٍ لا يُنفق مجموعة "
                          "التدريب · و`training` للمقارنة الكاملة **بلا إنفاق الحجز** "
                          "(قرارٌ يُتّخذ على الحجز يُنفقه — فالحجز للنموذج)."))
    ap.add_argument("--out", type=Path, default=PROJ / "docs/evidence")
    args = ap.parse_args()

    run = args.run if args.run.is_absolute() else PROJ / args.run
    pages = sorted(int(p.stem.split("-")[1]) for p in (run / "results").glob("pg-*.json"))
    divisible = [p for p in pages if p % args.holdout_mod == 0]
    pool = divisible if args.set == "holdout" else [p for p in pages if p not in divisible]
    step = max(1, len(pool) // args.count)
    picked = pool[::step][:args.count]

    report = {"measured_at": date.today().isoformat(), "run": str(args.run),
              "sample": {"requested": args.count, "picked": len(picked),
                         "from": (f"{args.set} (page % {args.holdout_mod} "
                                  f"{'==' if args.set == 'holdout' else '!='} 0)"),
                         "pages": picked},
              "prompts": {}}
    for name in ("v1", "v2"):
        per = [measure_page(run, pg, PROMPTS[name]) for pg in picked]
        ok = [p for p in per if "error" not in p]
        report["prompts"][name] = {
            "pages_measured": len(ok), "errors": len(per) - len(ok),
            "rows_read": sum(p.get("rows_read", 0) for p in ok),
            "rows_certified": sum(p.get("rows_certified", 0) for p in ok),
            "rows_chain_verified": sum(p.get("rows_chain_verified", 0) for p in ok),
            "pairs_matching_certified": sum(p.get("pairs_matching_certified", 0) for p in ok),
            "pages_with_last_balance_equal": sum(
                1 for p in ok if p.get("last_balance_equals_certified")),
            "median_seconds": round(statistics.median(
                [p["seconds"] for p in ok if p.get("seconds")]), 1) if ok else None,
            "per_page": per,
        }
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "20260921-fm2-prompt-comparison.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, d in report["prompts"].items():
        print(f"{name}: قرأ {d['rows_read']} من {d['rows_certified']} مُثبت · "
              f"سلسلة {d['rows_chain_verified']} · مطابقة {d['pairs_matching_certified']} · "
              f"آخر رصيد مطابق في {d['pages_with_last_balance_equal']}/{d['pages_measured']} صفحة")
    print(f"\nالملف: {out.relative_to(PROJ)}")


if __name__ == "__main__":
    main()
