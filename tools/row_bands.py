#!/usr/bin/env python3
"""حدودُ الصفوف والتكملات لكشفٍ ممسوح — محلّيٌّ بالكامل، بلا OCR ولا نموذج ولا كلفة.

يُصيّر كلَّ صفحة ويطبّق `statement_qa.row_bands` عليها، ثم يربط تكملةَ أعلى كلّ صفحةٍ بآخر صفٍّ
في سابقتها. **يطبع أعدادًا فقط** (نوعُ الصفحة · عددُ الصفوف · ذواتُ التاريخ · التكملة) — لا نصَّ
ولا مبلغ ولا اسم.

    python3 tools/row_bands.py --pdf <statement.pdf>
    python3 tools/row_bands.py --pdf <statement.pdf> --out data/local_sample/bands

وبـ`--out` يكتب: `bands.json` (إحداثياتٌ فقط، منسوبةٌ إلى الملف ببصمته لا بمساره) · `overlay-NNN.png`
للمراجعة بالعين · `stitched-NNN.png` لكلّ حركةٍ انقسم وصفُها بين صفحتين. **وهذه صورٌ من الكشف
الحقيقي** ⇒ فالمجلّدُ داخل المستودع مرفوضٌ إلا تحت `data/local_sample/` (مُتجاهَلٌ في git).

رمزُ الخروج: 0 تمّ · 2 مُدخلٌ مرفوض (dpi أقلّ من الحدّ · مجلّدٌ يُتتبَّع).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))
from statement_qa.row_bands import (  # noqa: E402
    MIN_DPI, analyze_page, link_pages, overlay, stitch,
)

SAFE_OUT = PROJ / "data" / "local_sample"


def out_allowed(out: Path) -> bool:
    """مجلّدُ الإخراج خارجَ المستودع، أو تحت `data/local_sample/` — لا غير."""
    out = out.expanduser().resolve()
    if not out.is_relative_to(PROJ):
        return True
    return out.is_relative_to(SAFE_OUT)


def _pages(pdf: Path, dpi: int):
    import fitz
    import numpy as np

    with fitz.open(pdf) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
            yield np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.stride)[:, :pix.width].copy()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--dpi", type=int, default=MIN_DPI)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.dpi < MIN_DPI:
        print(f"مرفوض: --dpi {args.dpi} أقلّ من {MIN_DPI} — الأرقامُ الرقيقة تختفي.")
        return 2
    if args.out is not None and not out_allowed(args.out):
        print("مرفوض: --out داخل المستودع — الصورُ من كشفٍ حقيقي؛ "
              "استعمل data/local_sample/ أو مجلّدًا خارج المستودع.")
        return 2
    pdf = args.pdf.expanduser().resolve()
    if not pdf.exists():
        print("مرفوض: الملفّ غير موجود.")
        return 2

    grays = list(_pages(pdf, args.dpi))
    pages = [analyze_page(g, args.dpi) for g in grays]
    links = link_pages(pages)
    by_page = {lk["page"]: lk for lk in links}
    # بلا قراءةِ تذييلٍ لا ترتيبَ حقيقيًّا ولا تجاورَ مؤكَّدًا (ordering.footer_order/adjacency):
    # فالربطُ هنا بترتيب الملف، وكلُّه «غيرُ مؤكَّد» — والتطبيقُ يربط بالترتيب الحقيقي.
    print("(الربطُ بترتيب الملف وغيرُ مؤكَّد — يصحّ إن كانت صفحاتُه متتالية في الكشف)")
    for i, p in enumerate(pages):
        dated = sum(b.dated for b in p.bands)
        credit = sum(b.credit_ink for b in p.bands if b.dated)
        lk = by_page.get(i)
        cont = ("لا" if lk is None else
                "صاحبُها خارج الدفعة" if lk.get("owner_missing") else
                f"تُكمل آخرَ صفٍّ في الصفحة {lk['continues'][0] + 1}")
        flag = f" · ⚠ مراسٍ بلا تاريخ: {len(p.suspects())}" if p.suspects() else ""
        print(f"صفحة {i + 1}: نوع={p.kind} · صفوف={len(p.bands)} (بتاريخ {dated} · "
              f"دائن {credit}) · تكملة أعلى الصفحة: {cont}{flag}")

    if args.out is not None:
        out = args.out.expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)
        from PIL import Image

        for i, (g, p) in enumerate(zip(grays, pages), start=1):
            overlay(g, p).save(out / f"overlay-{i:03d}.png")
        for lk in links:
            if "continues" in lk:
                prev, row = lk["continues"]
                nxt = lk["page"]
                stitch(Image.fromarray(grays[prev]), pages[prev].bands[row],
                       Image.fromarray(grays[nxt]), pages[nxt].orphan
                       ).save(out / f"stitched-{nxt + 1:03d}.png")
        doc = {"source_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
               "dpi": args.dpi, "pages": [p.to_dict() for p in pages], "links": links}
        (out / "bands.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                                        encoding="utf-8")
        print(f"كُتب: bands.json و{len(pages)} صورة مراجعة في المجلّد المختار.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
