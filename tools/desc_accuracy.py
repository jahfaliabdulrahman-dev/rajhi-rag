#!/usr/bin/env python3
"""مقياسُ دقّة البيان — كيف قيس أن عمودَ البيان يُصلح ما تُخطئه قراءةُ الصفحة، ليُعاد لا ليُصدَّق.

ثلاثةُ أوامر على تشغيلةٍ فيها `results/` (قراءةُ الصفحة المخزّنة) و`pages/`:

    python3 tools/desc_accuracy.py reference --run <run> --pages 40-49,150-159 \\
        --out data/local_sample/desc_accuracy/reference.json --max-cost 2     # مدفوع
    python3 tools/desc_accuracy.py column    --run <run> --pages ... \\
        --out data/local_sample/desc_accuracy/column.json --max-cost 1        # مدفوع
    python3 tools/desc_accuracy.py compare   --run <run> --pages ... \\
        --reference ... --column ... --counts-out docs/evidence/desc_accuracy.json

- `reference`: **قصاصةٌ لكلّ صفّ** (استدعاءٌ لكلّ صفّ، والصفُّ الأخير ملصوقٌ بتكملته) — المرجعُ الذي
  حُسمت خلافاتُه بالنظر في الصور. **أرقامُه لا تُعتمد** (الصفرُ النقطيّ يُشبه الفاصلة في القصاصة المنفردة).
- `column`: **عمودُ البيان مكدّسًا** — بوحدة التطبيق نفسها (`statement_qa.desc_reader`).
- `compare`: مجّاني، بلا تبعيّات، ويكتب **أعدادًا فقط** (لا نصَّ ولا مبلغ): لكلّ صفحةٍ مقارنةُ الكلمات
  (العمود ⇄ المرجع، والصفحة ⇄ المرجع)، والصفُّ الأوّل بعد تكملة، والتكملةُ نفسُها، وانزياحُ البيان.

الملفّاتُ الوسيطة (`reference`/`column`) نصٌّ حقيقي ⇒ مرفوضةٌ داخل المستودع إلا تحت `data/local_sample/`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
for _p in (str(PROJ / "src"), str(PROJ / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# تلقينةُ المرجع (قصاصةٌ لكلّ صفّ) — حقولُ FRONTIER_PROMPT_V2 وقواعدُه لصفٍّ واحد، ومعها ترتيبُ الأعمدة
# (الصفُّ المنفرد بلا رأسٍ مطبوع) وحالةُ الصفّ الملصوق. محفوظةٌ هنا ليُعاد القياسُ بها حرفيًّا.
ROW_PROMPT = """أنت ناسخ أرقام دقيق لمستند مصرفي سعودي قديم. الصورة **صفّ حركةٍ واحد** مقصوصٌ من صفحة كشف حساب.
وقد تكون الصورة جزأين بينهما خطٌّ رمادي رفيع: الجزءُ السفلي تكملةُ بيانِ الصفّ نفسه من أعلى الصفحة التالية — فهو من البيان وليس صفًّا آخر.
ترتيبُ الأعمدة في هذا الكشف من اليسار: الرصيد (أقصى اليسار)، ثم عمود الدائن، ثم عمود المدين ملاصقًا للبيان، ثم البيان والتاريخ في اليمين.
أعد JSON كائنًا واحدًا فقط بلا أي تعليق:
{"greg": "التاريخ الميلادي إن ظهر وإلا null", "desc": "البيان كاملًا بكل أسطره",
 "col": "debit" أو "credit" أو null — العمود المطبوع الذي فيه المبلغ، لا تخمّنه من الإشارة",
 "amount": "المبلغ تماماً كما هو مطبوع — انسخ أرقامه حرفياً بلا أي تحويل ولا حذف أصفار ولا إضافة فواصل",
 "balance": "الرصيد تماماً كما هو مطبوع إن وُجد وإلا null"}.
قواعد صارمة: (1) انسخ سلاسل الأرقام حرفياً مهما بدت غريبة، (2) لا تختلق أي رقم — null للباهت،
(3) لا تكتب التاريخ في خانة المبلغ أبداً، (4) JSON فقط."""


# ————————————————————— المقارنة (مجّانية، بلا تبعيّات) —————————————————————

def words(text) -> Counter:
    """كلماتُ البيان بلا ترتيبٍ ولا أرقامٍ ولا تشكيل — واللاتينيُّ والعربيُّ يُفصلان (وإلا «IBOUOAعبد» كلمةٌ واحدة)."""
    t = re.sub(r"[ً-ْـ]", "", str(text or ""))
    t = re.sub(r"[إأآ]", "ا", t).replace("ى", "ي").replace("ة", "ه")
    return Counter(w.lower() for w in re.findall(r"[A-Za-z]{2,}|[ء-ي]{2,}", t))


def relation(x: Counter, y: Counter) -> str:
    if x == y:
        return "same"
    if not (x - y) or not (y - x):
        return "one_side_extra"
    return "small" if sum((x - y).values()) + sum((y - x).values()) <= 2 else "big"


def _sim(x: Counter, y: Counter) -> float:
    total = sum((x | y).values())
    return sum((x & y).values()) / total if total else 1.0


def _movers(run: Path, pg: int) -> list[dict]:
    data = json.loads((run / "results" / f"pg-{pg:03d}.json").read_text(encoding="utf-8"))
    return [r for r in data.get("raw_rows") or [] if r.get("balance") not in (None, "")]


def compare(run: Path, pages: list[int], reference: dict, column: dict) -> dict:
    """أعدادٌ لكلّ صفحة ومجاميعُها — لا نصّ. `reference`/`column` بصيغة الأمرين أعلاه."""
    ref, col = reference.get("rows") or {}, column.get("pages") or {}
    page_rows = {pg: _movers(run, pg) for pg in pages}
    ref_desc = {k: (v.get("row") or {}).get("desc") for k, v in ref.items() if v.get("row")}
    per_page: dict[str, dict] = {}
    for pg in pages:
        rows, cdescs = page_rows[pg], (col.get(str(pg)) or {}).get("descs") or {}
        c_vs_r, p_vs_r = Counter(), Counter()
        for i, a in enumerate(rows):
            r = ref_desc.get(f"{pg}:{i}")
            if r is None:
                continue
            c_vs_r[relation(words(cdescs.get(str(i + 1))), words(r))] += 1
            p_vs_r[relation(words(a.get("desc")), words(r))] += 1
        entry = {"rows": len(rows), "column_rows": len(cdescs),
                 "column_vs_reference": dict(c_vs_r), "page_read_vs_reference": dict(p_vs_r)}
        # انزياحٌ في قراءة الصفحة: صفّان متتاليان على الأقلّ يُشبه كلٌّ منهما مرجعَ جاره أكثرَ من مرجعه
        run_len = best = 0
        for i, a in enumerate(rows):
            wa, own = words(a.get("desc")), ref_desc.get(f"{pg}:{i}")
            if own is None:
                run_len = 0
                continue
            near = max([_sim(wa, words(ref_desc.get(f"{pg}:{j}"))) for j in (i - 1, i + 1)
                        if 0 <= j < len(rows) and f"{pg}:{j}" in ref_desc] or [0.0])
            run_len = run_len + 1 if near > _sim(wa, words(own)) + 0.3 else 0
            best = max(best, run_len)
        entry["page_read_shift"] = best >= 2
        per_page[str(pg)] = entry
    # التكملة: ما زاد به صفُّ المرجع الأخيرُ الملصوق على صفّ قراءة الصفحة الأخير = نصُّ التكملة نفسُه
    for pg in pages:
        prev = pg - 1
        if prev not in page_rows or not page_rows[prev]:
            continue
        last = len(page_rows[prev]) - 1
        rrec = ref.get(f"{prev}:{last}") or {}
        if not rrec.get("row") or not rrec.get("stitched"):
            continue
        cont = words(rrec["row"].get("desc")) - words(page_rows[prev][last].get("desc"))
        first_ref = ref_desc.get(f"{pg}:0")
        c_first = (col.get(str(pg)) or {}).get("descs", {}).get("1")
        c_last = (col.get(str(prev)) or {}).get("descs", {}).get(str(last + 1))
        per_page[str(pg)]["after_continuation"] = {
            # معزولةٌ = صفُّ قراءة الصفحة الأخيرُ ناقصٌ منها بالبناء (قُطع البيانُ عند حدّ الصفحة)
            "continuation_isolated": bool(cont),
            "page_read_pasted_into_first_row": bool(cont) and not (cont - words(page_rows[pg][0].get("desc"))),
            "column_carried_on_previous": bool(cont) and not (cont - words(c_last)),
            "column_first_row_same_as_reference": first_ref is not None and words(c_first) == words(first_ref),
            "page_read_first_row_same_as_reference": first_ref is not None
            and words(page_rows[pg][0].get("desc")) == words(first_ref),
        }
    return {"pages": pages, "per_page": per_page, "totals": _totals(per_page)}


def _totals(per_page: dict) -> dict:
    tot: dict = {"rows_with_reference": 0, "column_vs_reference": Counter(),
                 "page_read_vs_reference": Counter(), "page_read_shift_pages": [],
                 "after_continuation": Counter()}
    for pg, e in per_page.items():
        tot["column_vs_reference"].update(e["column_vs_reference"])
        tot["page_read_vs_reference"].update(e["page_read_vs_reference"])
        tot["rows_with_reference"] += sum(e["column_vs_reference"].values())
        if e["page_read_shift"]:
            tot["page_read_shift_pages"].append(int(pg))
        for k, v in (e.get("after_continuation") or {}).items():
            tot["after_continuation"][k] += int(v)
        if e.get("after_continuation"):
            tot["after_continuation"]["pages"] += 1
    return {k: (dict(v) if isinstance(v, Counter) else v) for k, v in tot.items()}


# ————————————————————— القراءتان المدفوعتان —————————————————————

def _load(run: Path, pg: int):
    import numpy as np
    from PIL import Image

    from statement_qa.row_bands import analyze_page

    img = Image.open(run / "pages" / f"pg-{pg:03d}.png").convert("RGB")
    return img, analyze_page(np.asarray(img.convert("L")), 200)


def _continuation(run: Path, pg: int, pb):
    """التكملةُ من الصفحة التالية في الملف (صفحاتُ العيّنة متتالية — والتطبيقُ يشترط التجاورَ المُثبت)."""
    from statement_qa.desc_reader import continuation_for

    if not (run / "pages" / f"pg-{pg + 1:03d}.png").exists():
        return None
    nimg, npb = _load(run, pg + 1)
    return continuation_for(pb, npb, nimg)


def _save(out: Path, data: dict) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def run_reference(run: Path, pages: list[int], out: Path, max_cost: float) -> dict:
    import base64
    import io

    from statement_qa.row_bands import stitch
    from statement_qa.vlm_reader import MODEL, _extract_json, _rows_from_content, chat_vlm_image

    def parse_one(content):
        data = _extract_json(content)
        rows = _rows_from_content(json.dumps([data] if isinstance(data, dict) and "rows" not in data
                                             else data, ensure_ascii=False))
        if len(rows) != 1:
            raise ValueError(f"expected one row, got {len(rows)}")
        return rows[0]

    done = json.loads(out.read_text(encoding="utf-8")) if out.exists() else \
        {"model": MODEL, "prompt": ROW_PROMPT, "rows": {}, "cost": 0.0, "calls": 0}
    for pg in pages:
        img, pb = _load(run, pg)
        cont = _continuation(run, pg, pb)
        for i, band in enumerate(pb.bands):
            key = f"{pg}:{i}"
            if key in done["rows"] and not done["rows"][key]["error"]:
                continue
            if done["cost"] >= max_cost:
                _save(out, done)
                return done
            last = i == len(pb.bands) - 1
            crop = (stitch(img, band, cont[0], cont[1]) if last and cont
                    else img.crop((0, band.top, img.width, band.bottom + 1)))
            buf = io.BytesIO()
            crop.save(buf, format="PNG")
            st: dict = {}
            try:
                row, err = chat_vlm_image(base64.b64encode(buf.getvalue()).decode(), ROW_PROMPT,
                                          max_tokens=800, stats=st, parse=parse_one), None
            except Exception as e:  # noqa: BLE001
                row, err = None, type(e).__name__
            done["calls"] += int(st.get("request_calls") or 1)
            done["cost"] = round(done["cost"] + float(st.get("cost") or 0), 6)
            done["rows"][key] = {"stitched": bool(last and cont), "error": err,
                                 "row": None if row is None else {"desc": row.get("desc")}}
            _save(out, done)
    return done


def run_column(run: Path, pages: list[int], out: Path, max_cost: float) -> dict:
    from statement_qa.desc_reader import DESC_PROMPT, read_page_descriptions
    from statement_qa.vlm_reader import MODEL

    done = json.loads(out.read_text(encoding="utf-8")) if out.exists() else \
        {"model": MODEL, "prompt": DESC_PROMPT, "pages": {}, "cost": 0.0, "calls": 0}
    for pg in pages:
        if str(pg) in done["pages"] and not done["pages"][str(pg)]["error"]:
            continue
        if done["cost"] >= max_cost:
            break
        img, pb = _load(run, pg)
        cont = _continuation(run, pg, pb)
        st: dict = {}
        try:
            descs, err = read_page_descriptions(img, pb, cont, st), None
        except Exception as e:  # noqa: BLE001
            descs, err = [], type(e).__name__
        done["calls"] += int(st.get("request_calls") or 1)
        done["cost"] = round(done["cost"] + float(st.get("cost") or 0), 6)
        done["pages"][str(pg)] = {"n": len(pb.bands), "stitched_last": cont is not None, "error": err,
                                  "descs": {str(i + 1): d for i, d in enumerate(descs)}}
        _save(out, done)
    return done


def _pages(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out.extend(range(int(a), int(b or a) + 1))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=("reference", "column", "compare"))
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--pages", required=True, help="مثل 5-9,200-204")
    ap.add_argument("--out", type=Path, help="reference/column: ملفُّ الناتج (نصٌّ حقيقي)")
    ap.add_argument("--max-cost", type=float, default=1.0)
    ap.add_argument("--reference", type=Path)
    ap.add_argument("--column", type=Path)
    ap.add_argument("--counts-out", type=Path, help="compare: ملفُّ الأعداد (يُلتزم)")
    args = ap.parse_args()
    run, pages = args.run.expanduser().resolve(), _pages(args.pages)
    if args.command in ("reference", "column"):
        from row_bands import out_allowed

        if not args.out or not out_allowed(args.out):
            print("مرفوض: --out مطلوب، وداخل المستودع لا يُكتب نصٌّ حقيقيٌّ إلا تحت data/local_sample/.")
            return 2
        done = (run_reference if args.command == "reference" else run_column)(
            run, pages, args.out.expanduser().resolve(), args.max_cost)
        print(f"{args.command}: الكلفة ${done['cost']:.4f} · الاستدعاءات {done['calls']}")
        return 0
    if not (args.reference and args.column):
        print("مرفوض: compare يحتاج --reference و--column.")
        return 2
    counts = compare(run, pages, json.loads(args.reference.read_text(encoding="utf-8")),
                     json.loads(args.column.read_text(encoding="utf-8")))
    t = counts["totals"]
    print(f"صفوفٌ لها مرجع: {t['rows_with_reference']} · العمود⇄المرجع: {t['column_vs_reference']} · "
          f"الصفحة⇄المرجع: {t['page_read_vs_reference']} · انزياحُ قراءة الصفحة: {t['page_read_shift_pages']}")
    if args.counts_out:
        _save(args.counts_out, counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
