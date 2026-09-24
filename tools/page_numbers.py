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
OUTPUT NOTE (measured 2026-09-16): the VLM path reads this field on a MINORITY
of pages (a 30-page probe: 12 valid, the rest truncated to 1-2 digits or empty;
tesseract: 0%). The reliable path is the local detector + a tiled montage read
by a strong vision model (verified 37/37 on the pages the detector found).
Use `--montage-out DIR` to emit review sheets instead of trusting the VLM.
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
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / "src"))
from tools.spend import at_or_over  # noqa: E402 — **السقفُ بالسنتات** (مراجعة ٥٢ · R52-4 · F7)

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


def _ink_crop(png: Path, size: tuple[int, int] = (140, 52)):
    """Detector box -> normalized ink-only crop (bright pixels = ink)."""
    from PIL import Image

    cands = find_number_candidates(png)
    if not cands:
        return None
    x0, y0, x1, y1 = cands[0]
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    with Image.open(png).convert("L") as im:
        t = im.crop((max(0, cx - 60), max(0, cy - 25),
                     min(im.width, cx + 60), min(im.height, cy + 25)))
    a = 255.0 - np.asarray(t.resize(size, Image.Resampling.LANCZOS),
                           dtype=np.float32)
    return np.clip(a - np.percentile(a, 80), 0, None)


def scan_duplicates(pages_dir: Path, first: int, count: int,
                    max_candidates: int = 12) -> dict:
    """Mechanical duplicate hunt — a repeated printed number means repeated ink.

    Two sheets that carry the SAME printed number produce near-identical crops
    (distance ≈ 0); consecutive sheets differ by one digit and sit far higher.
    This is the deterministic test for "a sheet was duplicated/inserted", and
    it needs no VLM call. Distance = mean |A−B| over the union ink mask,
    minimized over ±2px shifts, normalized by the ink mean.

    Returns {'n', 'adjacent': [(d, a, b)...] lowest first, 'candidates': [...]}.
    """
    crops = {}
    for i in range(first, first + count):
        png = pages_dir / f"pg-{i:03d}.png"
        if not png.exists():
            continue
        c = _ink_crop(png)
        if c is not None:
            crops[i] = c
    idx = sorted(crops)
    if len(idx) < 2:
        return {"n": len(idx), "adjacent": [], "candidates": []}
    from PIL import Image

    mask = np.stack([crops[i] for i in idx]).max(axis=0) > 0

    def dist(a: int, b: int) -> float:
        A, B = crops[a], crops[b]
        best = float("inf")
        for dy in (-2, -1, 0, 1, 2):
            for dx in (-2, -1, 0, 1, 2):
                Bb = np.roll(np.roll(B, dy, axis=0), dx, axis=1)
                v = float(np.abs(A - Bb)[mask].mean() / (A[mask].mean() + 1e-6))
                best = min(best, v)
        return best

    adjacent = sorted((dist(a, b), a, b) for a, b in zip(idx, idx[1:]))
    # coarse pre-filter on a small version, then refine the best candidates
    small = np.stack([np.asarray(
        Image.fromarray(crops[i].astype(np.uint8)).resize((36, 14)),
        dtype=np.float32) for i in idx])
    rough = []
    for s in range(len(idx)):
        d = np.abs(small[s][None, :, :] - small).mean(axis=(1, 2))
        for m in range(s + 1, len(idx)):
            rough.append((float(d[m]), idx[s], idx[m]))
    rough.sort()
    out, seen = [], set()
    for _, a, b in rough:
        if b == a + 1 or (a, b) in seen:
            continue
        seen.add((a, b))
        out.append((dist(a, b), a, b))
        if len(out) >= max_candidates * 4:
            break
    out.sort()
    return {"n": len(idx), "adjacent": adjacent[:max_candidates],
            "candidates": out[:max_candidates]}


def build_montage(pages_dir: Path, indices: list[int], out: Path,
                  tiles_per_sheet: int = 12) -> list[Path]:
    """Detector crops tiled with their PDF index — the reliable review path."""
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    tiles: list[tuple[int, "Image.Image"]] = []
    for i in indices:
        png = pages_dir / f"pg-{i:03d}.png"
        if not png.exists():
            continue
        cands = find_number_candidates(png)
        if not cands:
            continue
        x0, y0, x1, y1 = cands[0]
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        with Image.open(png).convert("L") as im:
            t = im.crop((max(0, cx - 60), max(0, cy - 25),
                         min(im.width, cx + 60), min(im.height, cy + 25)))
        tiles.append((i, t.resize((t.width * 3, t.height * 3),
                                  Image.Resampling.LANCZOS)))
    sheets: list[Path] = []
    for s in range(0, len(tiles), tiles_per_sheet):
        ch = tiles[s:s + tiles_per_sheet]
        cols = 4
        rows = (len(ch) + cols - 1) // cols
        tw = max(c.width for _, c in ch)
        th = max(c.height for _, c in ch)
        canvas = Image.new("L", (cols * (tw + 16) + 16,
                                 rows * (th + 34) + 16), 255)
        d = ImageDraw.Draw(canvas)
        for m, (i, c) in enumerate(ch):
            r, col = divmod(m, cols)
            x = 16 + col * (tw + 16)
            y = 16 + r * (th + 34)
            d.text((x + 4, y + 2), f"i{i}", fill=0, font=font)
            canvas.paste(c, (x, y + 30))
        p = out / f"sheet_{s // tiles_per_sheet:02d}.png"
        canvas.save(p)
        sheets.append(p)
    return sheets


def main() -> None:
    ap = argparse.ArgumentParser(description="read printed page numbers")
    ap.add_argument("--pages-dir", default="data/local_sample/slice_629p/pages")
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--out", default="data/local_sample/page_numbers.json")
    ap.add_argument("--max-cost", type=float, default=0.6)
    ap.add_argument("--montage-out", default=None,
                    help="أخرج أوراق مونتاج (كاشف + ترويسة الفهرسة) للمراجعة — "
                         "المسار الموثوق؛ لا يستدعي النموذج")
    ap.add_argument("--tiles-per-sheet", type=int, default=12,
                    help="عدد القصاصات في ورقة المونتاج (12 افتراضياً، 24 للمسح الكامل)")
    ap.add_argument("--dup-scan", action="store_true",
                    help="مسح ميكانيكي للبحث عن ورقة مكررة (تشابه الحبر) — بلا API")
    args = ap.parse_args()

    pages = PROJ / args.pages_dir
    out = PROJ / args.out
    if args.dup_scan:
        res = scan_duplicates(pages, args.first, args.count)
        print(f"قصاصات مقروءة ميكانيكياً: {res['n']}")
        print("أدنى 6 فروق بين متجاورين (التطابق التام ≈ صفر):")
        for d, a, b in res["adjacent"][:6]:
            print(f"  {a}→{b}: {d:.3f}")
        print("أدنى 8 مرشحين للتكرار عن بُعد:")
        for d, a, b in res["candidates"][:8]:
            print(f"  {a} ↔ {b}: {d:.3f}  (بُعد {b - a})")
        verdict = ("لا ورقة مكررة" if not res["candidates"]
                   or res["candidates"][0][0] > 0.15 else "مرشح تكرار — تحقق بصرياً")
        print(f"الحكم الميكانيكي: {verdict} "
              f"(أدنى مسافة {res['candidates'][0][0]:.3f} vs عتبة 0.150)")
        Path(PROJ / "data/local_sample/page_numbers_dup_scan.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        return
    if args.montage_out:
        mdir = PROJ / args.montage_out
        mdir.mkdir(parents=True, exist_ok=True)
        sheets = build_montage(
            pages, list(range(args.first, args.first + args.count)), mdir,
            tiles_per_sheet=args.tiles_per_sheet)
        for p in sheets:
            print(p)
        return
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
        if at_or_over(cost, args.max_cost):
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
