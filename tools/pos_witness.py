#!/usr/bin/env python3
"""الشاهد الموضعي عند الطلب: عمود المبلغ من هندسة الورق، وإثباته بالحبر.

يُشغَّل على الصفحات التي رفعت راية (خلاف عمود↔سلسلة · صفّ لم يُثبت · تذييل مخالف)
لا على الكشف كله: الكلفة تُقاس بالحاجة (مقيس: $0.0067 للصفحة).

    python3 tools/pos_witness.py --pages-dir <dir> --pages 621,198 --out out.json

والمخرَج لكل صفحة: عدد الصفوف · إطارات ثبتها السنّ على حبر · توافق الهندسة مع
السلسلة · الخلافات بأرقامها · الكلفة. ولا يحكم الشاهد وحده: يقترح، والسلسلة تحكم.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
from PIL import Image

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / "src"))
from tools.spend import at_or_over  # noqa: E402 — **السقفُ بالسنتات** (مراجعة ٥٢ · R52-4 · F7)

from statement_qa.pos_witness import (INK_MIN, INK_THRESHOLD, PROMPT,  # noqa: E402
                                      assign_column, compare_with_chain,
                                      parse_lines, snap_point)
from statement_qa.vlm_reader import chat_vlm_image  # noqa: E402

MAX_TOKENS = 4000        # رموز تفكير النموذج تستهلك السقف: 1500 قطع الجواب (مقيس)


def make_ink(arr: np.ndarray):
    def ink(x0: int, y0: int, x1: int, y1: int) -> float:
        part = arr[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
        return float((part < INK_THRESHOLD).mean()) if part.size else 0.0
    return ink


def witness_page(png: Path, max_tokens: int = MAX_TOKENS,
                 prev_balance: float | None = None) -> dict:
    stats: dict = {}
    raw = chat_vlm_image(base64.b64encode(png.read_bytes()).decode(), PROMPT,
                         max_tokens=max_tokens, stats=stats)
    cols, rows = parse_lines(str(raw))
    arr = np.asarray(Image.open(png).convert("L"))
    height, width = arr.shape
    ink = make_ink(arr)
    on_ink = 0
    for row in rows:
        cx, cy = int(row["x"] * width), int(row["y"] * height)
        row["ink_claim"] = ink(cx - 60, cy - 13, cx + 60, cy + 13)
        sx, sy, after = snap_point(arr, cx, cy, ink)
        row["snapped"] = [sx, sy]
        row["shift_px"] = abs(sx - cx)
        row["ink_snapped"] = after
        row["column"] = assign_column(row["x"], cols)
        if after >= INK_MIN:
            on_ink += 1
    verdict = compare_with_chain(rows, cols, prev_balance)
    return {"page": int(png.stem.split("-")[1]), "cols": cols, "rows": rows,
            "on_ink": on_ink, "ink_min": INK_MIN, **verdict,
            "cost": float(Decimal(str(stats.get("cost") or 0))),
            "tokens": [stats.get("prompt_tokens"), stats.get("completion_tokens")]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages-dir", required=True)
    ap.add_argument("--pages", required=True, help="أرقام صفحات مفصولة بفواصل")
    ap.add_argument("--out", default="data/local_sample/pos_witness.json")
    ap.add_argument("--max-cost", type=float, default=0.30)
    # رصيد الصفحة السابقة: بدون تمريره يُستثنى **أوّل صفّ من كل صفحة** من شاهد
    # السلسلة (٦٢٩ صفّاً). ولا يُخمَّن: يُمرَّر صراحةً من رصيد الصفحة السابقة كما
    # طُبع في الملف، ويُعلن في المخرَج أيّ صفوفٍ قُوبلت.
    ap.add_argument("--prev-balance", type=float, default=None)
    args = ap.parse_args()

    pages = [int(p) for p in args.pages.replace(" ", "").split(",") if p]
    out: dict = {}
    total = 0.0
    for page in pages:
        png = Path(args.pages_dir) / f"pg-{page:03d}.png"
        if not png.exists():
            print(f"ص{page}: لا صورة", flush=True)
            continue
        try:
            res = witness_page(png, prev_balance=args.prev_balance)
        except Exception as exc:                              # noqa: BLE001
            print(f"ص{page}: عطل — {str(exc)[:70]}", flush=True)
            continue
        total += res["cost"]
        out[str(page)] = res
        print(f"ص{page}: صفوف {len(res['rows'])} · على حبر {res['on_ink']}/{len(res['rows'])}"
              f" · توافق {res['agree']} · خلاف {res['clash']} · غير محسوم {res['undetermined']}"
              f" · ${res['cost']:.4f} (تراكمي ${total:.4f})", flush=True)
        for clash in res["clashes"]:
            print(f"     خلاف صف{clash['row']}: السلسلة {clash['chain']} · "
                  f"الهندسة {clash['geometry']} · {clash['amount']}", flush=True)
        if at_or_over(total, args.max_cost):
            print(f"توقّف: بلغ السقف ${args.max_cost}", flush=True)
            break
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    print(f"المجموع: ${total:.4f} · المخرَج: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
