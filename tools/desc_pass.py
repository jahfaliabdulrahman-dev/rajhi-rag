#!/usr/bin/env python3
"""البيانُ من عمود البيان لتشغيلةٍ كبيرة — ملفٌّ جانبيٌّ لكلّ صفحة، والكاشُ لا يُمسّ.

قراءةُ الصفحة كاملةً (`tools/scale_slice.py`) تبقى مصدرَ الأرقام والتواريخ كما هي؛ هذه الأداةُ تقرأ
**البيانَ وحده** (`statement_qa.desc_reader`: صورةُ عمود البيان مكدّسةً بخاناتٍ مرقّمة، استدعاءٌ واحدٌ
لكلّ صفحة) وتكتبه في `results/desc/pg-NNN.json`. ثم يأخذه التصديرُ بعلَمٍ صريح:

    python3 tools/desc_pass.py --run data/local_sample/slice_629p --max-cost 6
    python3 tools/to_xlsx.py --run data/local_sample/slice_629p --out كشف.xlsx --desc-column

- **الترتيبُ الحقيقي** من الإجماليات التراكمية (`ordering.footer_order`)، والتكملةُ تُلصق بالصفّ الأخير
  **فقط** حين يُثبت الحسابُ أن التاليةَ هي الورقةُ التالية فعلًا (`ordering.adjacency` = `adjacent`).
- **لا يُدفع** لصفحةٍ لا يطابق عددُ صفوفها في الحبر عددَها في الكاش (تُسمّى)، ولا لصفحةٍ بلا صفوف.
- **يُستأنف**: ملفٌّ جانبيٌّ بختم القارئ نفسه يُتخطّى؛ وبختمٍ آخر (تلقينةٌ تغيّرت) يُعاد — لا يُخلط.
- **سقفُ كلفة**، ويطبع أعدادًا فقط (لا نصَّ ولا مبلغ). والمجلّدُ داخل المستودع مرفوضٌ إلا تحت
  `data/local_sample/` (الصورُ من كشفٍ حقيقي).

رمزُ الخروج: 0 تمّ · 2 مُدخلٌ مرفوض.
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
for _p in (str(PROJ / "src"), str(PROJ / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from row_bands import out_allowed  # noqa: E402
from scale_slice import row_from_json  # noqa: E402
from statement_qa.desc_reader import (  # noqa: E402
    DESC_PROMPT, continuation_for, read_page_descriptions, sidecar_path,
)
from statement_qa.footer_oracle import page_totals  # noqa: E402
from statement_qa.ordering import adjacency, footer_order  # noqa: E402
from statement_qa.vlm_reader import chain_derive, reader_stamp  # noqa: E402


def _dec(v):
    try:
        return Decimal(str(v)) if v not in (None, "") else None
    except Exception:  # noqa: BLE001
        return None


def plan(results: Path) -> tuple[list[int], dict, dict[int, list[dict]]]:
    """(الترتيبُ الحقيقي، حالةُ كلّ جارَين، صفوفُ كلّ صفحةٍ الخام) — من الكاش وحده، بلا كلفة."""
    raw: dict[int, list[dict]] = {}
    footers: dict[int, tuple | None] = {}
    printed: dict[int, int] = {}
    for f in sorted(results.glob("pg-*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pg = int(d.get("pg") or 0)
        raw[pg] = d.get("raw_rows") or []
        ft = d.get("footer") or {}
        footers[pg] = (_dec(ft.get("debits")), _dec(ft.get("credits"))) if ft else None
        if isinstance(d.get("page_no"), int):
            printed[pg] = d["page_no"]
    order = footer_order(footers)["order"]
    own, prev = {}, None
    for pg in order:
        rows = chain_derive([row_from_json(r) for r in raw[pg]], prev_balance=prev)
        t = page_totals(rows)
        own[pg] = (t["debits"], t["credits"])
        if t["balance"] is not None:
            prev = t["balance"]
    return order, adjacency(order, footers, own, printed), raw


def _movers(rows: list[dict]) -> int:
    return sum(1 for r in rows if r.get("balance") not in (None, ""))


def run_pass(run: Path, *, only: set[int] | None = None, max_cost: float = 6.0,
             dpi: int = 200, reader=read_page_descriptions) -> dict:
    """يكتب الملفّاتِ الجانبية ويعيد تقريرَ أعداد. `reader` يُحقن في الاختبار بدل النموذج."""
    import numpy as np
    from PIL import Image

    from statement_qa.row_bands import analyze_page

    results, pages_dir = run / "results", run / "pages"
    order, pairs, raw = plan(results)
    stamp = reader_stamp(DESC_PROMPT)
    rep = {"written": [], "stitched": 0, "cached": 0, "stale": 0, "failed": [],
           "unaligned": [], "no_image": [], "stopped_at": None, "cost": 0.0}

    def load(pg):
        img = Image.open(pages_dir / f"pg-{pg:03d}.png").convert("RGB")
        return img, analyze_page(np.asarray(img.convert("L")), dpi)

    for i, pg in enumerate(order):
        if (only and pg not in only) or not _movers(raw[pg]):
            continue
        side = sidecar_path(results, pg)
        if side.exists():
            try:
                old = json.loads(side.read_text(encoding="utf-8")).get("stamp")
            except (OSError, ValueError):
                old = None
            if old == stamp:
                rep["cached"] += 1
                continue
            rep["stale"] += 1                  # تلقينةٌ أخرى: يُعاد، لا يُخلط
        if rep["cost"] >= max_cost:
            rep["stopped_at"] = pg
            break
        if not (pages_dir / f"pg-{pg:03d}.png").exists():
            rep["no_image"].append(pg)
            continue
        img, pb = load(pg)
        if len(pb.bands) != _movers(raw[pg]):
            rep["unaligned"].append(pg)        # لا يُدفع لصفحةٍ لا يُضمن دمجُها
            continue
        nxt = order[i + 1] if i + 1 < len(order) else None
        cont = None
        if nxt and pairs.get((pg, nxt)) == "adjacent" and (pages_dir / f"pg-{nxt:03d}.png").exists():
            nimg, npb = load(nxt)
            cont = continuation_for(pb, npb, nimg)
        st: dict = {}
        try:
            descs = reader(img, pb, cont, st)
        except Exception:  # noqa: BLE001
            rep["failed"].append(pg)
            continue
        finally:
            rep["cost"] = round(rep["cost"] + float(st.get("cost") or 0), 6)
        side.parent.mkdir(parents=True, exist_ok=True)
        side.write_text(json.dumps({"pg": pg, "descs": descs, "stitched": cont is not None,
                                    "stamp": stamp, "cost": st.get("cost")},
                                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        rep["written"].append(pg)
        rep["stitched"] += int(cont is not None)
    return rep


def _pages(spec: str | None) -> set[int] | None:
    if not spec:
        return None
    out: set[int] = set()
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out.update(range(int(a), int(b or a) + 1))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True, type=Path, help="مجلد التشغيل (results/ و pages/)")
    ap.add_argument("--pages", default=None, help="مثل 1-50,120 (الافتراضي: كلّها)")
    ap.add_argument("--max-cost", type=float, default=6.0, help="سقفُ الكلفة بالدولار")
    args = ap.parse_args()
    run = args.run.expanduser().resolve()
    if not out_allowed(run):
        print("مرفوض: التشغيلةُ داخل المستودع خارج data/local_sample/ — الملفّاتُ الجانبية من كشفٍ حقيقي.")
        return 2
    if not (run / "results").is_dir():
        print("مرفوض: لا results/ في التشغيلة.")
        return 2
    rep = run_pass(run, only=_pages(args.pages), max_cost=args.max_cost)
    print(f"كُتب: {len(rep['written'])} صفحة (تكملاتٌ ملصوقة: {rep['stitched']}) · مخزّنةٌ سلفًا: "
          f"{rep['cached']} · أُعيدت لتغيّر التلقينة: {rep['stale']} · الكلفة: ${rep['cost']:.4f}")
    for key, label in (("failed", "تعذّرت قراءتُها"), ("unaligned", "عددُ صفوفها لا يطابق"),
                       ("no_image", "بلا صورة")):
        if rep[key]:
            print(f"  ⚠ {label}: {len(rep[key])} — {rep[key][:12]}")
    if rep["stopped_at"]:
        print(f"  ⛔ توقّف عند سقف الكلفة قبل الصفحة {rep['stopped_at']} — أعد التشغيل للاستئناف.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
