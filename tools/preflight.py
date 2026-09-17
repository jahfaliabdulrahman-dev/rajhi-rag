#!/usr/bin/env python3
"""فاحص جاهزية ملف كشف جديد — محلي 100% (بلا أي استدعاء نموذج).

يقيس على عيّنة صفحات:
  1. هندسة الصفحة (المقاس) والسطوع/التباين العام.
  2. وجود سطر الإطار السفلي (المُحكّم المستقل للراجحي) وكثافة حبره وعدد مقاطعه.
  3. معدّل التقاط موضع رقم الصفحة المطبوع (الكاشد البكسلي) — ويقارن بالمرجع.
  4. صف الترويسة (تواريخ الفترة) — وجوده وارتفاعه.

الحكم: «متوافق مبدئياً» يُخوّل الخطوة التالية (عيّنة VLM 10 صفحات)؛
وإلا فالبند الفاشل يُسمّى صراحةً — أي لا نُدخل ملفاً ونحن عميان عنه.

الاستعمال:
  python tools/preflight.py --pdf path/to/new.pdf --count 8
  python tools/preflight.py --pages-dir data/local_sample/slice_629p/pages --first 1 --count 8
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / "src"))
sys.path.insert(0, str(PROJ))

from tools.page_numbers import find_number_candidates  # noqa: E402

# المرجع المقيس على مسحة الراجحي المعتمدة (629 ورقة · 200dpi)
REF = {
    "page_no_x": (250, 340),      # نطاق x لموضع رقم الصفحة
    "page_no_y": (60, 460),       # نطاق y (الترويسة تتحرك بين الأقسام)
    "page_no_hit": 0.70,          # أدنى معدّل التقاط مقبول
    "footer_hit": 0.80,           # أدنى معدّل لوجود سطر الإطار
    "footer_segments": (2, 5),    # عدد مقاطع الأرقام في سطر الإطار
    "mean_bright": (225, 252),    # سطوع الصفحة (249 في المرجع)
}


def _gray(png: Path) -> np.ndarray:
    from PIL import Image

    with Image.open(png).convert("L") as im:
        return np.asarray(im)


def _segments(profile: np.ndarray, thr: float = 3) -> list[tuple[int, int]]:
    """مقاطع الحبر الأفقيّة (ينابيع متجاورة) من مخطط أعمدة."""
    on = profile > thr
    out, start = [], None
    for i, v in enumerate(on):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= 4:          # نتجاهل النقاط المفردة (ضجيج)
                out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(on)))
    return out


def _footer_row(a: np.ndarray) -> tuple[int, np.ndarray] | None:
    """آخر كتلة أسطر في أسفل الصفحة = سطر الإطار (المُحكّم المستقل).

    القاعدة: الإطار آخر سطر مطبوع في الكشف؛ نأخذ **أدنى** كتلة لا أكثفها
    (سطور المعاملات أكثر حبراً وتسبق الإطار).
    """
    h, w = a.shape
    dark = a < 240                      # الخط النقطي باهت (متوسط الصفحة 249)
    rows = dark.sum(axis=1)
    bands: list[tuple[int, int]] = []
    cur = None
    for y in range(int(h * 0.60), h):
        if rows[y] > 25:
            cur = (y, y) if cur is None else (cur[0], y)
        elif cur is not None:
            bands.append(cur)
            cur = None
    if cur is not None:
        bands.append(cur)
    bands = [b for b in bands if b[1] - b[0] >= 6]
    if not bands:
        return None
    # الإطار سطر يمتد عرض الصفحة ومقاطعه كثيرة (نصوص + أرقام)؛ نبحث من الأسفل
    for y0, y1 in reversed(bands[-3:]):
        win = dark[y0:y1 + 1].sum(axis=0)
        segs = [s for s in _segments(win) if s[1] - s[0] >= 6]
        if len(segs) >= 8 and segs and (segs[-1][1] - segs[0][0]) > 0.5 * w:
            return (y0 + y1) // 2, win
    return None


def check_page(png: Path) -> dict:
    a = _gray(png)
    h, w = a.shape
    ink = a < 205
    res: dict = {"file": png.name, "size": [w, h],
                 "mean": round(float(a.mean()), 1),
                 "ink_ratio": round(float(ink.mean()), 4)}
    # 1) رقم الصفحة المطبوع (كاشد)
    cands = find_number_candidates(png)
    if cands:
        x0, y0, x1, y1 = cands[0]
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        res["page_no_detected"] = True
        res["page_no_pos"] = [cx, cy]
        res["page_no_in_ref"] = (REF["page_no_x"][0] <= cx <= REF["page_no_x"][1]
                                 and REF["page_no_y"][0] <= cy <= REF["page_no_y"][1])
    else:
        res["page_no_detected"] = False
    # 2) الإطار السفلي
    fr = _footer_row(a)
    if fr:
        y, win = fr
        segs = _segments(win)
        numeric = [s for s in segs if (s[1] - s[0]) >= 8]
        res["footer_row_y"] = y
        res["footer_segments"] = len(numeric)
        res["footer_present"] = len(numeric) >= REF["footer_segments"][0]
        res["footer_has_numbers"] = len(numeric) >= 2
    else:
        res["footer_present"] = False
        res["footer_segments"] = 0
    # 3) الترويسة (تواريخ الفترة)
    head = a[int(h * 0.03):int(h * 0.20), :] < 205
    res["header_ink_ratio"] = round(float(head.mean()), 4)
    return res


def verdict(rows: list[dict]) -> dict:
    n = len(rows)
    hits = {
        "page_no": sum(1 for r in rows if r.get("page_no_detected")) / n,
        "page_no_in_ref": sum(1 for r in rows
                              if r.get("page_no_in_ref")) / n,
        "footer": sum(1 for r in rows if r.get("footer_present")) / n,
        "header": sum(1 for r in rows if r.get("header_ink_ratio", 0) > 0.002) / n,
    }
    mean = float(np.mean([r["mean"] for r in rows]))
    fails = []
    if hits["footer"] < REF["footer_hit"]:
        fails.append(f"سطر الإطار غير مكشوف على {1 - hits['footer']:.0%} من الصفحات")
    if hits["page_no"] < REF["page_no_hit"]:
        fails.append(f"موضع رقم الصفحة غير مكشوف على {1 - hits['page_no']:.0%}")
    elif hits["page_no_in_ref"] < REF["page_no_hit"]:
        fails.append("موضع رقم الصفحة مكشوف لكن خارج النطاق المرجعي "
                     "(يحتاج معايرة القصاصة)")
    if hits["header"] < 0.6:
        fails.append("ترويسة الفترة غير واضحة (تواريخ بداية/نهاية المعاملات)")
    if not (REF["mean_bright"][0] <= mean <= REF["mean_bright"][1]):
        fails.append(f"سطوع الصفحة {mean:.0f} خارج النطاق المرجعي "
                     f"{REF['mean_bright']}")
    return {"pages": n, "hits": {k: round(v, 3) for k, v in hits.items()},
            "mean_brightness": round(mean, 1), "fails": fails,
            "ready": not fails}


def render(pdf: Path, out_dir: Path, first: int, count: int, dpi: int) -> list[Path]:
    from pdf2image import convert_from_path

    out_dir.mkdir(parents=True, exist_ok=True)
    pngs = []
    for i in range(count):
        png = out_dir / f"pg-{first + i:03d}.png"
        if not png.exists():
            imgs = convert_from_path(str(pdf), dpi=dpi,
                                     first_page=i + 1, last_page=i + 1)
            imgs[0].save(png)
        pngs.append(png)
    return pngs


def main() -> None:
    ap = argparse.ArgumentParser(description="فاحص جاهزية ملف كشف (محلي)")
    ap.add_argument("--pdf", default=None, help="ملف PDF جديد (يُصيّر محلياً)")
    ap.add_argument("--pages-dir", default=None, help="أو مجلد صفحات مُصيَّرة")
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--count", type=int, default=8)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--out", default="data/local_sample/preflight.json")
    args = ap.parse_args()

    if args.pdf:
        pngs = render(PROJ / args.pdf, PROJ / "data/local_sample/preflight_pages",
                      args.first, args.count, args.dpi)
        src = f"pdf:{args.pdf} @ {args.dpi}dpi"
    elif args.pages_dir:
        d = PROJ / args.pages_dir
        pngs = [d / f"pg-{args.first + i:03d}.png" for i in range(args.count)]
        pngs = [p for p in pngs if p.exists()]
        src = f"pages:{args.pages_dir}"
    else:
        ap.error("حدّد --pdf أو --pages-dir")
        return
    if not pngs:
        print("لا صفحات للفحص"); return

    rows = [check_page(p) for p in pngs]
    v = verdict(rows)
    out = PROJ / args.out
    out.write_text(json.dumps({"source": src, "per_page": rows, "verdict": v},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"المصدر: {src}  |  صفحات: {v['pages']}  |  سطوع متوسط: "
          f"{v['mean_brightness']}")
    print("نسب الكشف: " + " · ".join(f"{k}={val:.0%}" for k, val in v["hits"].items()))
    if v["ready"]:
        print("الحكم: ✅ متوافق مبدئياً — الخطوة التالية: عيّنة VLM 10 صفحات")
    else:
        print("الحكم: ⚠ يحتاج معايرة/تحقق قبل أي تشغيل:")
        for f in v["fails"]:
            print(f"   - {f}")
    print(f"التفصيل: {out}")


if __name__ == "__main__":
    main()
