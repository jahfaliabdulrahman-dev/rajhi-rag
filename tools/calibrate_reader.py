#!/usr/bin/env python3
"""Measure a SECOND reader on the same ten pages — the fallback, actually tested.

The risk register listed provider dependency as high, mitigated by «a measured
tesseract fallback». The measurement said otherwise: tesseract is not wired into
the reading path at all and scores 0% on these digit crops, so the project had no
fallback — only a sentence claiming one (audit §1, P2-8).

The candidate that needs no new architecture is a different model behind the
same transport (`OPENROUTER_MODEL_VLM`). This tool asks the only question worth
asking about it: **on the ten golden pages, does it reproduce the certified
values?** It reads cold (never the cache), compares row by row against the
certified checkpoints, and prints per-page agreement.

    .venv/bin/python tools/calibrate_reader.py --model qwen/qwen3-vl-235b-a22b-instruct

Cost: ≈$0.15 for ten pages. Nothing is written anywhere: a calibration is a
measurement, not a migration.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))

DEFAULT_SOURCE = PROJ / "data" / "local_sample" / "sample_10p.pdf"
CERTIFIED = PROJ / "data" / "local_sample" / "slice_629p" / "results"


def _certified_rows(page: int) -> list[dict]:
    path = CERTIFIED / f"pg-{page:03d}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("raw_rows") or []


def _norm(token) -> str | None:
    """Printed token -> plain decimal string, for a value-only comparison."""
    from statement_qa.legacy.arabic_digit_parser import norm_num

    if token in (None, ""):
        return None
    value = norm_num(token)
    return None if value is None else f"{Decimal(str(value)):.2f}"


def _pair(rows: list[dict]) -> list[tuple[str | None, str | None]]:
    return [(_norm(r.get("movement")), _norm(r.get("balance"))) for r in rows]


def _score(got: list[tuple], want: list[tuple]) -> tuple[int, int, int]:
    """(ordered hits, multiset hits, expected).

    Two numbers, because one is not enough: a reader that transcribes correctly
    but splits or merges a row shifts every later index, and positional
    comparison then reports 0/12 for a page that lost nothing. The multiset
    view asks the question that matters — were these numbers read, whatever
    order they came in.
    """
    from collections import Counter

    ordered = sum(1 for i, w in enumerate(want)
                  if i < len(got) and got[i] == w)
    cg, cw = Counter(got), Counter(want)
    multiset = sum(min(cg[k], v) for k, v in cw.items())
    return ordered, multiset, len(want)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True)
    ap.add_argument("--source", default=str(DEFAULT_SOURCE))
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--dump", type=int, default=0,
                    help="اطبع أول N صفاً من الطرفين للمقارنة البصرية")
    args = ap.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"لا مصدر: {source}")
        return 2

    import tempfile

    from pdf2image import convert_from_path
    from statement_qa import vlm_reader

    vlm_reader.MODEL = args.model          # same transport, different brain
    images = convert_from_path(str(source), dpi=args.dpi)
    # read_rows_vlm takes a path (the reader opens the PNG itself)
    tmpdir = Path(tempfile.mkdtemp(prefix="calib_"))
    print(f"[calibrate] model={args.model} · pages={len(images)} · "
          f"المقارنة مع الكوربوس المعتمد\n")

    total_hits = total_rows = 0
    per_page = []
    for i, img in enumerate(images, start=1):
        page = args.first + i - 1
        stats: dict = {}
        png = tmpdir / f"pg-{page:03d}.png"
        img.save(png)
        try:
            raw = vlm_reader.read_rows_vlm(str(png), stats=stats)
        except Exception as exc:  # noqa: BLE001
            per_page.append((page, None, None, f"{type(exc).__name__}: {exc}"))
            continue
        got = _pair([{"movement": r.get("movement"),
                      "balance": r.get("balance")} for r in raw])
        want = _pair(_certified_rows(page))
        hits, multi, n = _score(got, want)
        total_hits += multi
        total_rows += n
        per_page.append((page, multi, n, f"{len(got)} صفاً مقروءاً"))
        print(f"  ص{page}: مطابقة بالقيمة {multi}/{n} · "
              f"بالترتيب {hits}/{n} · الصفوف المقروءة {len(got)} · "
              f"cost=${stats.get('cost', 0):.4f}")
        if args.dump:
            print("    المعتمد :", want[:args.dump])
            print("    المقروء :", got[:args.dump])

    print()
    for page, hits, n, note in per_page:
        if hits is None:
            print(f"  ✗ ص{page}: فشل القراءة — {note}")
    if total_rows:
        pct = total_hits / total_rows
        print(f"الخلاصة: {total_hits}/{total_rows} صفاً مطابقاً للمعتمد "
              f"({pct:.1%}) على {len([p for p in per_page if p[1] is not None])} صفحة")
        print("\nالحكم: " + ("القارئ البديل صالح كتحصين — أعد القياس شهرياً "
                             "لرصد تدهور النموذج."
                             if pct >= 0.98 else
                             "لا يُعلن كبديل: الفرق يعني تغيير الأرقام، "
                             "فالتحصين ليس جاهزاً."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
