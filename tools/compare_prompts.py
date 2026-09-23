#!/usr/bin/env python3
"""مقابلةُ تلقينتَي القارئ (v1 · v2) على صفحاتٍ من **مجموعة الحجز** — لقرار FM-2.

السؤال: أيّ تلقينةٍ تكون الافتراض؟ والقياس هنا لا يعدّ الصفوف فقط، بل يقيس
**معيار القبول عندنا**: هل تُقفل السلسلة؟ وهل يوافق ما قُرئ ما هو مُثبت؟

ولماذا الحجز (page % N == 0): لأن ما يُقاس عليه الفرقُ لا يجوز أن يكون مما
تدرّب عليه القرار — وهي القاعدة نفسها التي بُنيت في التقاط العيّنات.

    python3 tools/compare_prompts.py --run data/local_sample/slice_629p --count 24
"""

from __future__ import annotations

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.pack_io import pack_facts as _pack_facts, pack_path as _pack_path  # noqa: E402

import argparse
import json
import statistics
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    stats: dict = {}
    try:
        rows = read_rows_vlm(str(img), prompt=prompt, stats=stats)
    except Exception as exc:                # noqa: BLE001
        return stamp | {"cost_usd": float(stats.get("cost") or 0.0),
                        "error": f"{type(exc).__name__}: {exc}"[:160]}
    # **الكلفة المقيسة من الاستعمال لا من عدّادٍ في رأسنا** (درس «تكلفة فعلية لا عدّاد»)
    stamp["cost_usd"] = float(stats.get("cost") or 0.0)
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
    ap.add_argument("--workers", type=int, default=6,
                    help="نداءاتٌ متوازية — والكلفة تُجمَع من الاستعمال المقيس")
    ap.add_argument("--prompts", default="v1,v2",
                    help=("أذرعُ المقابلة. وذراعٌ واحد = مقابلةٌ مع **المرجع المُثبت** "
                          "(صفوف الكوربوس نفسها) ⇒ نصفُ الكلفة ونفسُ بيانات القرار، "
                          "بشرط إعلان أن الذراع الثاني مقروءٌ سابقاً لا الآن."))
    ap.add_argument("--budget", type=float, default=11.0,
                    help="سقفُ الميزانية بالدولار: يُتوقّف عند بلوغه **ويُعلن التغطية**")
    ap.add_argument("--set", choices=("holdout", "training"), default="holdout",
                    help=("من أين تُسحَب الصفحات: `holdout` لقياسٍ لا يُنفق مجموعة "
                          "التدريب · و`training` للمقارنة الكاملة **بلا إنفاق الحجز** "
                          "(قرارٌ يُتّخذ على الحجز يُنفقه — فالحجز للنموذج)."))
    ap.add_argument("--out", type=Path, default=PROJ / "docs" / "evidence")
    ap.add_argument("--out-name", default="20260921-fm2-prompt-comparison.json",
                    help="اسمُ ملف النتيجة — فيُكتب كلُّ ذراعٍ في ملفّه ولا يُبطل ما قبله")
    args = ap.parse_args()

    run = args.run if args.run.is_absolute() else PROJ / args.run
    pages = sorted(int(p.stem.split("-")[1]) for p in (run / "results").glob("pg-*.json"))
    divisible = [p for p in pages if p % args.holdout_mod == 0]
    pool = divisible if args.set == "holdout" else [p for p in pages if p not in divisible]
    # **الحزمةُ المجمّدة لا تُنفَق في أيّ ضبط** (مراجعة ٤٥ · R45-3): هذه الأداةُ نفسُها هي التي
    # سحبت عيّنةَ FM-2 فسبّبت SPEC-1 — فصارت تسأل الحزمةَ أوّلًا، وتُعلن ما استثنته، وتقف إن عمِيت.
    _facts = _pack_facts(_pack_path())
    _before = len(pool)
    pool = [p for p in pool if p not in _facts["pages"]]
    print(f"استثناءُ الحزمة: {_before - len(pool)} صفحةً من {_before} · "
          f"(حزمةٌ معلَنة: {_facts['file']} · {len(_facts['pages'])} صفحة)")
    if not pool:
        raise SystemExit("⛔ لا صفحاتَ خارج الحزمة ⇒ لا ضبطَ بلا إنفاقها (فشلٌ مُغلَق)")
    step = max(1, len(pool) // args.count)
    picked = pool[::step][:args.count]

    arms = [a.strip() for a in args.prompts.split(",") if a.strip()]
    bad = [a for a in arms if a not in PROMPTS]
    if bad:
        raise SystemExit(f"تلقينات غير معروفة: {bad} — المتاح: {sorted(PROMPTS)}")
    tasks = [(name, pg) for name in arms for pg in picked]
    results: dict[str, list[dict]] = {name: [] for name in arms}
    spent = 0.0
    stopped_by_budget = False
    lock = threading.Lock()
    # ⚠️ الاسم `pool` محجوزٌ لمجموعة الصفحات — فلا يُعاد استعماله للمنفِّذ
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {}
        for name, pg in tasks:
            with lock:
                if spent >= args.budget:
                    stopped_by_budget = True
                    break
            futures[executor.submit(measure_page, run, pg, PROMPTS[name])] = (name, pg)
        for fut in as_completed(futures):
            name, pg = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:        # noqa: BLE001
                res = {"page": pg, "error": f"{type(exc).__name__}: {exc}"[:160],
                       "cost_usd": 0.0}
            with lock:
                spent += float(res.get("cost_usd") or 0.0)
                results[name].append(res)

    # **نسبُ المرجع يُسجَّل وقتَ القياس** (مأخذ المدقّق · الجولة ٢٢): بدونه صار
    # المشتقُّ يقرأ تشغيلةً مُتجاهَلة، فلم يبقَ دالّةً لملفَّي الذراعين — ولا تُعاد
    # نتيجتُه في بيئةٍ نظيفة (CI أو worktree بلا بيانات).
    _rep = run / "slice_report.json"
    provenance = {"reader": None, "legacy_unstamped_pages": None, "declaration": None,
                  "source": "غير مُعلن في تقرير التشغيلة"}
    if _rep.exists():
        cp = (json.loads(_rep.read_text(encoding="utf-8")).get("corpus_provenance") or {})
        provenance = {"reader": cp.get("reader") or None,
                      "legacy_unstamped_pages": cp.get("legacy_unstamped_pages"),
                      "declaration": cp.get("declaration"),
                      "source": "slice_report.json → corpus_provenance (وقت القياس)"}

    report = {"measured_at": date.today().isoformat(), "run": str(args.run),
              "corpus_provenance": provenance,
              "sample": {"requested": args.count, "picked": len(picked),
                         "from": (f"{args.set} (page % {args.holdout_mod} "
                                  f"{'==' if args.set == 'holdout' else '!='} 0)"),
                         "pool": len(pool), "pages": picked},
              "spend_usd": round(spent, 4), "budget_usd": args.budget,
              "stopped_by_budget": stopped_by_budget,
              "workers": args.workers,
              "prompts": {}}
    if len(arms) == 1:
        report["baseline"] = ("صفوف الكوربوس نفسها (قراءة سابقة) — يُعلن أنه مرجعٌ "
                              "مسجَّل لا قراءةٌ جديدة، فلا يكشف انزياحاً زمنياً للنموذج")
    for name in arms:
        per = sorted(results[name], key=lambda r: r["page"])
        ok = [p for p in per if "error" not in p]
        report["prompts"][name] = {
            "pages_measured": len(ok), "errors": len(per) - len(ok),
            "rows_read": sum(p.get("rows_read", 0) for p in ok),
            "rows_certified": sum(p.get("rows_certified", 0) for p in ok),
            "rows_chain_verified": sum(p.get("rows_chain_verified", 0) for p in ok),
            "pairs_matching_certified": sum(p.get("pairs_matching_certified", 0) for p in ok),
            "pages_with_last_balance_equal": sum(
                1 for p in ok if p.get("last_balance_equals_certified")),
            "pages_exact_against_certified": sum(
                1 for p in ok
                if p.get("pairs_matching_certified") == p.get("pairs_certified")
                and p.get("last_balance_equals_certified")),
            "cost_usd": round(sum(float(p.get("cost_usd") or 0.0) for p in per), 4),
            "median_seconds": round(statistics.median(
                [p["seconds"] for p in ok if p.get("seconds")]), 1) if ok else None,
            "p95_seconds": (sorted(p["seconds"] for p in ok if p.get("seconds"))
                            [int(0.95 * (len(ok) - 1))] if ok else None),
            "per_page": per,
        }
    args.out.mkdir(parents=True, exist_ok=True)
    out = (args.out / args.out_name).resolve()
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, d in report["prompts"].items():
        print(f"{name}: {d['pages_measured']} صفحة · قرأ {d['rows_read']}/{d['rows_certified']} · "
              f"مطابقة {d['pairs_matching_certified']} · صفحاتٌ مُقفلة {d['pages_with_last_balance_equal']} · "
              f"مطابقةٌ تامة {d['pages_exact_against_certified']} · ${d['cost_usd']}")
    print(f"\nالمصروف: ${report['spend_usd']} من سقف ${args.budget} · "
          f"توقّف بالسقف: {stopped_by_budget} · العيّنة: {len(picked)} من {len(pool)}")
    # ⚠️ الطبعُ لا يُسقط تشغيلةً مدفوعة: كان `relative_to` على مسارٍ **نسبيّ**
    # ⇒ `ValueError` **بعد** أن كُتب الملف، فيُقرأ الخروجُ فشلاً والقياسُ تامّ.
    try:
        shown = out.relative_to(PROJ)
    except ValueError:
        shown = out
    print(f"الملف: {shown}")


if __name__ == "__main__":
    main()
