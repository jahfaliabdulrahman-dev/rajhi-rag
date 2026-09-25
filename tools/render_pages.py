#!/usr/bin/env python3
"""يُصيّر صفحات PDF إلى صورٍ بنفس تسمية التشغيلات (`pages/pg-NNN.png`).

لماذا أداةٌ مستقلّة: مسارٌ رقميّ (نصّ) ومسارٌ ممسوح (صور) يفترقان في **مصدر
الصورة** لا في بنية التشغيلة. فبينما ينتج الماسح صوراً من جهازه، يُنتج المسار
الرقمي صوراً من الملف نفسه — والتسمية والترقيم يجب أن يكونا **واحداً**، لأن ما
بعدها (الالتقاط · الحجز · الحراسة) لا يعرف من أين جاءت الصورة.

    python3 tools/render_pages.py --pdf data/local_sample/digital/app_statement.pdf \
        --out data/local_sample/digital/run/pages --dpi 200

ويُعلن في `pages_rendered.json`: الملفَ وبصمتَه (sha256) والدقّة والعدد — فالصورة
المُشتقّة تُنسب إلى أصلها ببصمة لا بمسار.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--digest-out", type=Path, default=None,
                    help="شهادة التصيير (افتراضياً: <out>/../pages_rendered.json)")
    args = ap.parse_args()

    import fitz  # PyMuPDF — التصيير يحتاج محرّكَ الصفحة لا محرّك النصّ فقط

    pdf = args.pdf.expanduser().resolve()
    if not pdf.exists():
        raise SystemExit(f"لا ملف: {pdf}")
    out = args.out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    digest_before = sha256(pdf)
    pages: list[dict] = []
    with fitz.open(pdf) as doc:
        for i, page in enumerate(doc, start=1):
            # نفس مقاس الماسح التقريبي عند 200dpi (A4 ≈ 1654×2339)
            pix = page.get_pixmap(dpi=args.dpi)
            target = out / f"pg-{i:03d}.png"
            pix.save(str(target))
            pages.append({"page": i, "file": target.name,
                          "bytes": target.stat().st_size,
                          "sha256": sha256(target)[:16]})
            print(f"  صفحة {i:>3}: {target.name} ({target.stat().st_size:,} بايت)")

    # الملف لم يُعدَّل أثناء التصيير: بصمةٌ قبل وبعد — وإلا فالصور لا تُنسب إليه
    assert sha256(pdf) == digest_before, "الملف تغيّر أثناء التصيير — لا تُنسب الصور إليه"

    digest = {"pdf": pdf.name, "pdf_sha256": digest_before, "dpi": args.dpi,
              "pages": len(pages), "page_files": pages,
              "declaration": "صورٌ مُشتقّة من الملف نفسه ببصمةٍ مُثبتة قبل التصيير وبعده"}
    path = args.digest_out or (out.parent / "pages_rendered.json")
    path.write_text(json.dumps(digest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[render-pages] {len(pages)} صفحة عند {args.dpi}dpi · "
          f"sha256={digest_before[:16]}… · {path}")


if __name__ == "__main__":
    main()
