#!/usr/bin/env python
"""Read the PRINTED page number stamped on each page (owner finding).

Every sheet carries its own printed number on the header row (same row as the
«بداية ونهاية معاملات الصفحة» date range, left of centre, dot-matrix Arabic-
Indic digits). The pipeline indexed pages by POSITION in the scan; where a
sheet is missing or misplaced, position ≠ printed number — and the footer
cumulative (verified cumulative-to-date) then jumps by the movements of every
skipped sheet, which shows up as an unexplainable per-page delta.

Method (validated on real renders):
  1. LOCAL detector — find compact dark blobs in the header band (free, no
     model): the dot-matrix glyphs are faint, so threshold ~205 and a
     row-profile heuristic isolate the number box (verified: index 422 ->
     box (254,279)-(291,295) = printed ٤٢١).
  2. VLM on the TIGHT detected crop only (a few KB). Wide/upscaled-window
     crops make the model downscale and lose the faint glyphs; tesseract
     cannot read the dot-matrix font at all (measured).

Output: JSON mapping position -> printed number, plus gaps / duplicates.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from io import BytesIO
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / "src"))

from statement_qa.vlm_reader import chat_vlm_image  # noqa: E402

XLIM = (120, 720)      # excludes the corner "1" mark (x≈30-60) and the date box (x≈900+)
YLIM = (35, 450)       # the header row shifts ~150px between sections
THR = 205              # faint dot-matrix ink (page mean ≈ 249)
UPSCALE = 8
PAD = 10

PROMPT = ("هذه قصاصة من أعلى صفحة كشف حساب مصرفي، فيها **رقم الصفحة المطبوع**.\n"
          "أعد رقم الصفحة فقط، بالأرقام كما هي مطبوعة، دون أي كلام آخر.")

_INDIC = {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}
_PERSIAN = {ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")}


def to_ascii_digits(s: str) -> str:
    return s.translate(_INDIC).translate(_PERSIAN)


def find_number_candidates(png: Path, xlim=XLIM, ylim=YLIM, thr=THR):
    """Compact isolated blobs in the header band — the printed page number."""
    from PIL import Image

    with Image.open(png).convert("L") as im:
        a = np.asarray(im)[ylim[0]:ylim[1], xlim[0]:xlim[1]]
    dark = a < thr
    rows = dark.sum(axis=1)
    cand, cur = [], None
    for y, c in enumerate(rows):
        if 1 <= c <= 80:                       # thin row (a number), not body text
            cur = [y, y] if cur is None else [cur[0], y]
        else:
            if cur and 12 <= cur[1] - cur[0] <= 70:
                cand.append(tuple(cur))
            cur = None
    if cur and 12 <= cur[1] - cur[0] <= 70:
        cand.append(tuple(cur))
    out = []
    for y0, y1 in cand:
        band = dark[y0:y1 + 1]
        xs = np.where(band.sum(axis=0) > 0)[0]
        if len(xs) == 0:
            continue
        w, h = int(xs[-1] - xs[0]), y1 - y0
        if 18 <= w <= 130 and 12 <= h <= 70 and 0.8 <= w / max(1, h) <= 6.0:
            out.append((xlim[0] + int(xs[0]), ylim[0] + y0,
                        xlim[0] + int(xs[-1]), ylim[0] + y1))
    return out


def _crop_png(png: Path, box, upscale: int = UPSCALE) -> bytes:
    from PIL import Image
    from PIL.Image import Resampling

    with Image.open(png).convert("L") as im:
        part = im.crop(box)
        if upscale > 1:
            part = part.resize((part.width * upscale, part.height * upscale),
                               Resampling.LANCZOS)
        buf = BytesIO()
        part.save(buf, format="PNG")
    return buf.getvalue()


def _read(png: Path, box, stats: dict | None) -> int | None:
    from PIL import Image

    with Image.open(png) as im:
        w, h = im.size
    x0 = max(0, box[0] - PAD); y0 = max(0, box[1] - PAD)
    x1 = min(w, box[2] + PAD); y1 = min(h, box[3] + PAD)
    b64 = base64.b64encode(_crop_png(png, (x0, y0, x1, y1))).decode()

    def parse(content: str | None):
        if not content:
            return None
        digits = "".join(ch for ch in to_ascii_digits(str(content))
                         if ch.isdigit())
        return int(digits) if digits else None

    return chat_vlm_image(b64, PROMPT, max_tokens=40, stats=stats, parse=parse)


def read_page_no(png: Path, stats: dict | None = None) -> int | None:
    """Detector first (tight crop), then a static loose fallback."""
    for box in find_number_candidates(png)[:2]:
        num = _read(png, box, stats)
        if num is not None and 1 <= num <= 2000:
            return num
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="read printed page numbers")
    ap.add_argument("--pages-dir", default="data/local_sample/slice_629p/pages")
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--out", default="data/local_sample/page_numbers.json")
    ap.add_argument("--max-cost", type=float, default=0.6)
    args = ap.parse_args()

    pages = PROJ / args.pages_dir
    out = PROJ / args.out
    mapping: dict[str, int | None] = {}
    if out.exists():
        mapping = json.loads(out.read_text(encoding="utf-8"))
    cost = 0.0
    t0 = time.time()
    for i in range(args.first, args.first + args.count):
        png = pages / f"pg-{i:03d}.png"
        if not png.exists():
            print(f"[{i}] no render", flush=True)
            continue
        st: dict = {}
        try:
            num = read_page_no(png, stats=st)
        except Exception as e:  # a probe must never kill the sweep
            print(f"[{i}] FAILED: {e}", flush=True)
            num = None
        cost += float(st.get("cost", 0.0) or 0.0)
        mapping[str(i)] = num
        print(f"[{i}] printed={num}  (cum ${cost:.4f})", flush=True)
        out.write_text(json.dumps(mapping, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        if cost >= args.max_cost:
            print(f"STOPPED: budget ${args.max_cost} reached", flush=True)
            break

    seq = sorted(((int(k), v) for k, v in mapping.items() if v is not None))
    misses = [int(k) for k, v in mapping.items() if v is None]
    print(f"\nقراءات صالحة: {len(seq)}/{len(mapping)} في "
          f"{round(time.time() - t0, 1)}ث بتكلفة ${cost:.4f}")
    if misses:
        print(f"بلا قراءة ({len(misses)}): {misses}")
    seen: dict[int, list[int]] = {}
    for pos, num in seq:
        seen.setdefault(num, []).append(pos)
    dup = {n: ps for n, ps in seen.items() if len(ps) > 1}
    if dup:
        print(f"أرقام مطبوعة مكررة: {dup}")
    print("قفزات في الترقيم المطبوع (فجوة = صفحات ناقصة في موضعها):")
    for (p1, n1), (p2, n2) in zip(seq, seq[1:]):
        if n2 != n1 + 1:
            kind = "فجوة" if n2 > n1 + 1 else "تكرار/رجوع"
            print(f"   موقع {p1} (#{n1}) -> موقع {p2} (#{n2})  فرق {n2 - n1:+d}  [{kind}]")
    print(f"map -> {out}")


if __name__ == "__main__":
    main()
