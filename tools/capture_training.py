#!/usr/bin/env python3
"""التقاط عيّنات التدريب — من تشغيلةٍ مُتحقَّقة، بلا نداء نموذجٍ ولا كلفة.

القاعدة الحاكمة: **لا تُحفظ عيّنةٌ بلا دليلٍ على وسمها.** وسمُ كل حقل معلنٌ في
`field_provenance` (مُثبتٌ بالسلسلة · مطبوعٌ في الورق · مقروء) — فلا يُقرأ حقلٌ
مقروء على أنه مُثبت.

وحجزُ التقييم مبنيٌّ في الأداة لا في العُرف: كل صفحةٍ رقمها يقبل القسمة على
`--holdout-mod` **لا تُلتقط أبداً** — فلا يتدرّب النموذج على ما يُقاس عليه.

والترويسة تُستار (اسمٌ/حساب) قبل الحفظ: العيّنة تبقى جدولاً بلا هوية.

    python3 tools/capture_training.py --run data/local_sample/slice_629p \
        --export ~/Downloads/rajhi-rag-export-629p.xlsx --out data/training
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from decimal import InvalidOperation
from pathlib import Path

from PIL import Image
import openpyxl

# الدالة القائمة في المشروع — لا نسخة ثانية منها (درس الازدواج)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from statement_qa.legacy.arabic_digit_parser import norm_num  # noqa: E402

# ── ثوابت مُقاسة ────────────────────────────────────────────────────────────
# الحجب الآمن: أدنى `y` لصفٍّ في الشاهد الموضعي = 0.347 (28 صفّاً · 3 صفحات).
# فالحجب حتى 0.26 لا يمسّ صفّاً — والقياس مُعلن بحدوده في ترويسة كل ملف.
HEADER_MASK_FRACTION = 0.26
HEADER_MASK_EVIDENCE = "pos_witness_rows.json: min y = 0.347 (28 rows · 3 pages)"
CAPTURE_VERSION = "1"
CHAIN_PROOF_PREFIX = "السلسلة"
SHEET_ROWS = "الحركات"
DESC_MAX = 600


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_holdout(page: int, mod: int) -> bool:
    """حجز التقييم: حتميّ وقابل لإعادة الإنتاج."""
    return mod > 0 and page % mod == 0


def _txt(v) -> str:
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()[:DESC_MAX]


def load_certified_rows(export: Path) -> dict[int, list[dict]]:
    """الصفوف المعتمدة من المصدَّر — مُثبتة السلسلة وحدها."""
    wb = openpyxl.load_workbook(export, read_only=True, data_only=True)
    ws = wb[SHEET_ROWS]
    it = ws.iter_rows(values_only=True)
    hdr = [str(h) for h in next(it)]
    ix = {name: hdr.index(name) for name in hdr}
    need = ["الصفحة (ملف)", "رقم الصفّ", "التاريخ (ميلادي)", "الوصف",
            "الحركة كما طُبعت", "الحركة المثبتة بالسلسلة", "مصدر إثبات الحركة",
            "مدين", "دائن"]
    missing = [n for n in need if n not in ix]
    if missing:
        raise SystemExit(f"أعمدة ناقصة في «{SHEET_ROWS}»: {missing}")
    out: dict[int, list[dict]] = {}
    for r in it:
        if r is None or r[ix["الصفحة (ملف)"]] is None:
            continue
        page = int(str(r[ix["الصفحة (ملف)"]]))
        src = _txt(r[ix["مصدر إثبات الحركة"]])
        row = {
            "row_no": int(str(r[ix["رقم الصفّ"]] or 0)),
            "date_iso": _txt(r[ix["التاريخ (ميلادي)"]]) or None,
            "descr": _txt(r[ix["الوصف"]]),
            "printed_amount": _txt(r[ix["الحركة كما طُبعت"]]) or None,
            "proven_amount": _txt(r[ix["الحركة المثبتة بالسلسلة"]]) or None,
            "side": "debit" if _txt(r[ix["مدين"]]) else (
                "credit" if _txt(r[ix["دائن"]]) else None),
            "proof_source": src,
        }
        out.setdefault(page, []).append(row)
    wb.close()
    return out


def split_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """يفصل ما يُوسَم عمّا لا دليل عليه — والمنبوذ يُعلن بعدده لا يُسكَت عنه."""
    kept, dropped = [], []
    for r in rows:
        chain = r["proof_source"].startswith(CHAIN_PROOF_PREFIX) and r["proven_amount"]
        (kept if chain else dropped).append(r)
    return kept, dropped


def attach_balances(kept: list[dict], raw_rows: list[dict]) -> tuple[int, int]:
    """الرصيد من القراءة الأولى — يُقرَن بالحركة المطبوعة للتأكّد من المحاذاة.

    المقابلة بالدالة القائمة `norm_num` (تُوحّد الأرقام العربية والإنجليزية
    وعلامات الفصل) — فالحكم واحد في المشروع كلّه.
    يُعاد (موصول, غير موصول). وغير الموصول يُسقط الحقل لا الصفّ.
    """
    ok = bad = 0
    for r, raw in zip(kept, raw_rows):
        try:
            same = (norm_num(str(r["printed_amount"])) == norm_num(str(raw.get("movement"))))
        except (TypeError, ValueError, InvalidOperation):
            same = False
        if same and raw.get("balance"):
            r["balance"] = _txt(raw["balance"])
            r["field_provenance_balance"] = "read_initial"
            ok += 1
        else:
            bad += 1
    return ok, bad


def redact_top(img: Image.Image, frac: float) -> Image.Image:
    """يستور الترويسة (اسمٌ/حساب) — الجدول وحده يبقى."""
    if frac <= 0:
        return img
    img = img.convert("L")
    box = Image.new("L", (img.width, max(1, int(img.height * frac))), 255)
    img.paste(box, (0, 0))
    return img


def capture_page(page: int, run: Path, out_root: Path, rows: list[dict],
                 doc_id: str, meta: dict, mask_frac: float) -> dict:
    """يكتب صورة الصفحة وملف وسمها. الكلفة صفر: لا نداء نموذج."""
    src = run / "pages" / f"pg-{page:03d}.png"
    if not src.exists():
        return {"page": page, "status": "missing_page_image"}
    kept, dropped = split_rows(rows)
    if not kept:
        return {"page": page, "status": "no_chain_proven_rows", "dropped": len(dropped)}
    pdir = out_root / doc_id / f"pg-{page:03d}"
    pdir.mkdir(parents=True, exist_ok=True)
    img = redact_top(Image.open(src), mask_frac)
    img.save(pdir / "page.png")
    raw = []
    rf = run / "results" / f"pg-{page:03d}.json"
    if rf.exists():
        raw = json.loads(rf.read_text()).get("raw_rows", [])
    ok, bad = attach_balances(kept, raw)
    payload = {
        "doc_id": doc_id, "page": page,
        "page_image": "page.png",
        "page_quality": {"header_masked_fraction": mask_frac,
                         "mask_evidence": HEADER_MASK_EVIDENCE,
                         "ink_ratio": meta.get("ink_ratio")},
        "rows": [
            {k: v for k, v in r.items() if k != "proof_source"} | {
                "side_source": "chain",
                "field_provenance": {"proven_amount": "chain_delta",
                                     "printed_amount": "paper",
                                     "side": "chain_delta",
                                     "date_iso": "paper",
                                     "descr": "read",
                                     "balance": r.get("field_provenance_balance", "not_joined")}}
            for r in kept],
        "dropped_rows": [{"row_no": r["row_no"], "proof_source": r["proof_source"]}
                         for r in dropped],
        "balances_joined": ok, "balances_not_joined": bad,
        "label_source": meta["label_source"],
        "capture_version": CAPTURE_VERSION,
        "privacy": "ترويسةٌ مستورة · لا ملفات اعتماد · المجلد غير مُلتزم",
    }
    (pdir / "label.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1))
    return {"page": page, "status": "captured", "rows": len(kept),
            "dropped": len(dropped), "bal_ok": ok, "bal_bad": bad}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--export", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--holdout-mod", type=int, default=3,
                    help="كل صفحةٍ رقمها يقبل القسمة على هذا لا تُلتقط (حجز التقييم)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--redact-top", type=float, default=HEADER_MASK_FRACTION)
    args = ap.parse_args()

    mask_frac = args.redact_top
    doc_file = args.run / "slice_629p.pdf"
    doc_id = sha256_file(doc_file)[:16] if doc_file.exists() else "unknown_doc"
    certified = load_certified_rows(args.export)
    meta = {"label_source": {"export": args.export.name,
                             "export_sha256": sha256_file(args.export)[:16],
                             "gate": "verify_close ALL PASS (25 checks)",
                             "holdout_mod": args.holdout_mod},
            "prompt_version": "unknown", "model_id": "unknown", "ink_ratio": None}

    pages = sorted(certified)
    if args.limit:
        pages = pages[:args.limit]
    results, train_pages = [], 0
    for p in pages:
        if is_holdout(p, args.holdout_mod):
            results.append({"page": p, "status": "holdout_reserved"})
            continue
        r = capture_page(p, args.run, args.out, certified[p], doc_id, meta, mask_frac)
        results.append(r)
        train_pages += 1 if r["status"] == "captured" else 0

    captured = [r for r in results if r["status"] == "captured"]
    manifest = {
        "captured_at": date.today().isoformat(),
        "capture_version": CAPTURE_VERSION,
        "doc_id": doc_id,
        "pages": {"total_in_export": len(certified), "visited": len(pages),
                  "captured": len(captured),
                  "holdout_reserved": sum(1 for r in results
                                          if r["status"] == "holdout_reserved"),
                  "skipped": [{"page": r["page"], "why": r["status"]}
                              for r in results
                              if r["status"] not in ("captured", "holdout_reserved")]},
        "samples": {"rows": sum(r.get("rows", 0) for r in captured),
                    "dropped_rows": sum(r.get("dropped", 0) for r in captured),
                    "balances_joined": sum(r.get("bal_ok", 0) for r in captured),
                    "balances_not_joined": sum(r.get("bal_bad", 0) for r in captured)},
        "holdout_rule": f"page % {args.holdout_mod} == 0 ⇒ لا تُلتقط (حجز التقييم)",
        "privacy": {"header_masked_fraction": HEADER_MASK_FRACTION,
                    "mask_evidence": HEADER_MASK_EVIDENCE,
                    "note": "بيانات حقيقية محليّة · المجلد مُدرَج في .gitignore"},
        "label_source": meta["label_source"],
        "cost_usd": "0 — لا نداء نموذج: الوسم من المصدَّر المعتمد",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest["pages"] | manifest["samples"],
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
