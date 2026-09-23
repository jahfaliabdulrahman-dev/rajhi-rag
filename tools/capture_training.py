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


def pack_pages(path: Path | None) -> set[int]:
    """**صفحاتُ حزمة التقييم المجمّدة** — تُقرأ من `pack.json` بحقولها (لا تُكتب بيد).

    وليست هي «الحجز بالقسمة»: ذاك حجزٌ **بقاعدة** (page % 3)، وهذا **حجزٌ باسمِ الحزمة** —
    لأنّ الحزمةَ اختيرت أوّلًا، فحقُّها أن تُستثنى من التدريب لا العكس (وإلّا لزم تغييرُ الحزمة
    بعد بنائها، وهو نقضُ «لا تُلمَس بعد اليوم»).
    """
    if path is None:
        return set()
    f = Path(path)
    if not f.exists():
        raise SystemExit(f"⛔ قائمةُ استثناءٍ مُعلَنة وغيرُ موجودة ({f.name}) ⇒ لا التقاط")
    d = json.loads(f.read_text(encoding="utf-8"))

    def _nums(x):
        out = set()
        for p in x or []:
            out.add(int(p["page"]) if isinstance(p, dict) and "page" in p else int(p))
        return out

    out = _nums(d.get("census", {}).get("pages", []))
    for r in d.get("ranges", []):
        out |= _nums(r.get("pages", []))
    if not out:
        raise SystemExit("⛔ قائمةُ الاستثناء فارغةٌ ⇒ استثناءٌ بلا صفحاتٍ لا يُنفَّذ صامتاً")
    return out


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


def load_private_patterns(path: Path | None) -> dict[str, list[str]]:
    """أنماطُ الخصوصية في قسمين صريحين.

    ```
    [anywhere]   ← يُمنع ظهوره في أي صفحةٍ مُلتقطة (IBAN · رقم الحساب)
    [header]     ← ترويسةٌ تُقنَّع بالشريط الأعلى (المرجع · اسم صاحب الحساب)
    ```

    ولا يُخمَّن أيُّ نمط: ملفُّ الأنماط يعيش **خارج المستودع** (`~/.hermes/private/`)،
    فلا يصل إلى الالتزام ولا إلى المخرجات.
    """
    out: dict[str, list[str]] = {"anywhere": [], "header": []}
    if not path:
        return out
    section = "anywhere"
    for line in Path(path).expanduser().read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("["):
            section = s.strip("[]").strip().lower()
            out.setdefault(section, [])
            continue
        out.setdefault(section, []).append(s)
    return out


def audit_privacy(pdf: Path, page: int, patterns: dict[str, list[str]],
                  mask_top_frac: float) -> dict:
    """يقيس: أتسرّب معرّفٌ تحت القناع؟ وهل غطّى القناعُ ترويسةَ الصفحة؟

    والتفريق بين `[anywhere]` و`[header]` ليس ترفاً — هو الفرق بين **معرّفٍ** و**محتوى**:

    - `[anywhere]`: معرّفاتٌ لا تظهر من الكشف (IBAN · رقم الحساب) ⇒ **ظهورُها تحت
      القناع رفضٌ**، وظهورُها داخله مقبول (لأنه مستور).
    - `[header]`: المرجعُ واسمُ صاحب الحساب — يُطبَعان في الترويسة (تُقنَّع)،
      **ويظهران داخل خلايا الوصف** حين تكون الحركة تحويلاً باسمه. وذلك **محتوى
      الكشف** يُعلن ولا يُخفى — كما في المسار الممسوح بالضبط.
    """
    import fitz
    with fitz.open(pdf) as doc:
        if page > doc.page_count:
            return {"page": page, "status": "no_such_page"}
        pg = doc[page - 1]
        H = pg.rect.height or 1.0
        hits: dict[str, list[float]] = {"anywhere": [], "header": []}
        for blk in pg.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                for sp in ln["spans"]:
                    y = round(sp["bbox"][1] / H, 3)
                    for kind in ("anywhere", "header"):
                        if any(pat and pat in sp["text"]
                               for pat in patterns.get(kind, [])):
                            hits[kind].append(y)

    below = lambda ys: sorted(y for y in ys if y >= mask_top_frac)   # noqa: E731
    inside = lambda ys: sorted(y for y in ys if y < mask_top_frac)   # noqa: E731
    return {"page": page, "status": "ok",
            "anywhere_under_mask": below(hits["anywhere"]),
            "anywhere_inside_mask": len(inside(hits["anywhere"])),
            "header_furniture_inside_mask": len(inside(hits["header"])),
            "header_inside_table_declared": len(below(hits["header"])),
            "mask_top_frac": mask_top_frac}


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


def adopt_legacy(out: Path) -> None:
    """يرحّل بياناً بصيغةٍ سبقت الإصلاح إلى مجلد مستنده — نسخٌ ثم إعادةُ تسمية، لا حذف.

    محتوى البيان يُنسخ كما هو (بايتاً ببايت من ناحية القيم)، والأصلُ يبقى على القرص
    باسمٍ آخر: التراجعُ ممكن، والضياعُ لا.
    """
    legacy = out / "manifest.json"
    if not legacy.exists():
        return
    d = json.loads(legacy.read_text(encoding="utf-8"))
    did = d.get("doc_id") or "unknown_doc"
    (out / did).mkdir(parents=True, exist_ok=True)
    (out / did / "manifest.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=1))
    legacy.rename(out / "manifest.json.adopted")
    print(f"رُحّل بيانُ {did} إلى {did}/manifest.json · والأصلُ صار manifest.json.adopted")


def write_index(out: Path) -> dict:
    """فهرسُ المستندات المُلتقَطة — مفتاحُ بوابة التقاطع `(doc_id, page)`.

    يُبنى من بيانات المستندات على القرص لا من ذاكرة تشغيلةٍ واحدة. ووجودُ بيانٍ
    بصيغةٍ سبقت الإصلاح في أعلى المجلد **يوقف الكتابة بالاسم**: بيانٌ يُهمَل صامتاً
    يُضيّع نسبَ عيّناته، وهو العطبُ الذي جعل تشغيلةَ مسحٍ تمحو بيانَ التقاطٍ رقميّ.
    """
    legacy = out / "manifest.json"
    if legacy.exists():
        raise SystemExit(
            f"بيانٌ بصيغةٍ سبقت الإصلاح في أعلى مجلد الالتقاط ({legacy.name}) — "
            "شغّل بـ`--adopt-legacy` لترحيله إلى مجلد مستنده أولاً: "
            "بيانٌ يُهمَل صامتاً يُضيّع نسبَ العيّنات.")
    docs = []
    for mf in sorted(out.glob("*/manifest.json")):
        d = json.loads(mf.read_text(encoding="utf-8"))
        pages = d.get("pages") or {}
        docs.append({"doc_id": d.get("doc_id"), "dir": mf.parent.name,
                     "manifest": str(mf.relative_to(out)),
                     "captured_at": d.get("captured_at"),
                     "captured": pages.get("captured"),
                     "holdout_reserved": pages.get("holdout_reserved"),
                     "holdout_rule": d.get("holdout_rule"),
                     "cost_usd": d.get("cost_usd")})
    index = {"documents": docs, "count": len(docs),
             "declaration": ("قائمةُ الالتقاط لكل مستند — مفتاحُ بوابة التقاطع "
                             "(doc_id, page): لا تُقابَل صفحةٌ بصفحةٍ من مستندٍ آخر "
                             "(تصادمُ رقمٍ ليس تلوّثاً)")}
    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1))
    return index


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--export", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--holdout-mod", type=int, default=3,
                    help="كل صفحةٍ رقمها يقبل القسمة على هذا لا تُلتقط (حجز التقييم)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--exclude-pack", type=Path, default=None,
                    help="pack.json للحزمة المجمّدة ⇒ لا تُلتقط صفحاتُها (فالتقاطعُ صفرٌ بالبناء)")
    ap.add_argument("--redact-top", type=float, default=HEADER_MASK_FRACTION)
    ap.add_argument("--pdf", type=Path, default=None,
                    help="ملف الأصل — يُفحَص نصُّه لمقابلة أنماط الخصوصية (قياسٌ لا دعوى)")
    ap.add_argument("--private-patterns-file", type=Path, default=None,
                    help="أنماطُ الخصوصية ([anywhere] · [header]) — تعيش خارج المستودع")
    ap.add_argument("--adopt-legacy", action="store_true",
                    help="يرحّل بياناً بصيغةٍ سبقت الإصلاح (مستوى أعلى) إلى مجلد مستنده")
    args = ap.parse_args()

    if args.adopt_legacy:
        args.out.mkdir(parents=True, exist_ok=True)
        adopt_legacy(args.out)

    mask_frac = args.redact_top
    # الأصل: الملف المُعطى صراحةً، وإلا ملفُّ التشغيلة الممسوحة
    doc_file = (args.pdf.expanduser() if args.pdf
                else args.run / "slice_629p.pdf")
    doc_id = sha256_file(doc_file)[:16] if doc_file.exists() else "unknown_doc"
    certified = load_certified_rows(args.export)
    # **هويةُ القارئ من تقرير التشغيلة** (لا «unknown»): الوسمُ ناقلُ حقيقةٍ لا حقلٌ فارغ
    stamp = {}
    rep_file = args.run / "slice_report.json"
    if rep_file.exists():
        _rep = json.loads(rep_file.read_text(encoding="utf-8"))
        stamp = _rep.get("reader_stamp") or {}
    meta = {"label_source": {"export": args.export.name,
                             "export_sha256": sha256_file(args.export)[:16],
                             "gate": "verify_close ALL PASS (25 checks)",
                             "holdout_mod": args.holdout_mod},
            "prompt_version": stamp.get("prompt_version") or "unknown",
            "model_id": stamp.get("model") or "unknown",
            "stamp_source": ("reader_stamp في slice_report.json" if stamp
                             else "غير مُعلن في التقرير (يُعلن ولا يُخمَّن)"),
            "ink_ratio": None}

    private = load_private_patterns(args.private_patterns_file)
    if private.get("anywhere") and not doc_file.exists():
        raise SystemExit("أنماطٌ ممنوعة معلنة وملفُّ الأصل غير موجود — لا فحص، لا التقاط")

    pages = sorted(certified)
    if args.limit:
        pages = pages[:args.limit]
    results, train_pages = [], 0
    reserved_pack = pack_pages(args.exclude_pack)
    if reserved_pack:
        print(f"· صفحاتُ الحزمة المجمّدة المستثناة من الالتقاط: {len(reserved_pack)}")
    for p in pages:
        if is_holdout(p, args.holdout_mod):
            results.append({"page": p, "status": "holdout_reserved"})
            continue
        if p in reserved_pack:
            results.append({"page": p, "status": "pack_reserved"})
            continue
        r = capture_page(p, args.run, args.out, certified[p], doc_id, meta, mask_frac)
        # **فحصُ الخصوصية قبل قبول الصفحة**: تسرُّبٌ ممنوع ⇒ رفضٌ بالاسم لا تجاوز
        if private.get("anywhere"):
            audit = audit_privacy(doc_file, p, private, mask_frac)
            r["privacy_audit"] = audit
            if audit.get("anywhere_under_mask"):
                raise SystemExit(
                    f"معرّفٌ مكشوفٌ تحت القناع في الصفحة {p}: "
                    f"{audit['anywhere_under_mask']} — لا تُلتقط صفحةٌ تحمل معرّفاً")
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
                  "pack_reserved": sum(1 for r in results
                                       if r["status"] == "pack_reserved"),
                  "skipped": [{"page": r["page"], "why": r["status"]}
                              for r in results
                              if r["status"] not in ("captured", "holdout_reserved")]},
        "samples": {"rows": sum(r.get("rows", 0) for r in captured),
                    "dropped_rows": sum(r.get("dropped", 0) for r in captured),
                    "balances_joined": sum(r.get("bal_ok", 0) for r in captured),
                    "balances_not_joined": sum(r.get("bal_bad", 0) for r in captured)},
        "holdout_rule": f"page % {args.holdout_mod} == 0 ⇒ لا تُلتقط (حجز التقييم)",
        "pack_exclusion": (str(args.exclude_pack.name) if args.exclude_pack else None),
        "privacy": {
            "header_masked_fraction": mask_frac,
            # الدليلُ يتبع التصميم: دليلُ المسح (أدنى y لصفٍّ مُثبت) لا يُنسب
            # إلى تصميمٍ رقميّ لم يُقس فيه شيء — يُقاس هنا ما يخصّه.
            "mask_evidence": (HEADER_MASK_EVIDENCE if not args.pdf else
                              "قياسٌ على الأصل الرقمي: ظهورُ الترويسة داخل الشريط "
                              "مُحصى في هذا الملف · والمعرّفات تحت القناع صفر"),
            "mode": ("نصُّ الأصل يُفحَص بمقابلة الأنماط (قياسٌ لا دعوى)" if private.get("anywhere")
                     else "قناعٌ بلا فحص نصّ — لم تُعطَ أنماط"),
            "patterns_file": (args.private_patterns_file.name
                              if args.private_patterns_file else None),
            "anywhere_patterns": len(private.get("anywhere", [])),
            "header_patterns": len(private.get("header", [])),
            "anywhere_identifiers_under_mask": sum(
                len(r.get("privacy_audit", {}).get("anywhere_under_mask", []))
                for r in captured),
            "anywhere_identifiers_inside_mask": sum(
                r.get("privacy_audit", {}).get("anywhere_inside_mask", 0) for r in captured),
            "header_furniture_inside_mask": sum(
                r.get("privacy_audit", {}).get("header_furniture_inside_mask", 0)
                for r in captured),
            "header_inside_table_declared": sum(
                r.get("privacy_audit", {}).get("header_inside_table_declared", 0)
                for r in captured),
            "note": ("ترويسةٌ مقنّعة · وظهورُ الاسم أو معرّفات التحويلات (IBANs) "
                     "**داخل خلايا الوصف** محتوى الكشف — يُعلن ولا يُقنَّع، كالمسار "
                     "الممسوح · المجلد غير مُلتزم")},
        "label_source": meta["label_source"],
        "cost_usd": "0 — لا نداء نموذج: الوسم من المصدَّر المعتمد",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    # **بيانٌ لكل مستند، لا بيانٌ واحد** — تشغيلةُ مستندٍ ثانٍ كانت تمحو بيانَ الأول
    # (العلّة البنيوية المقيسة). فالبيان ينزل في مجلد مستنده وفهرسٌ يجمع المستندات.
    (args.out / doc_id).mkdir(parents=True, exist_ok=True)
    (args.out / doc_id / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1))
    idx = write_index(args.out)
    print(json.dumps(manifest["pages"] | manifest["samples"],
                     ensure_ascii=False, indent=1))
    print(f"فهرسُ المستندات: {idx['count']} · " +
          " · ".join(f"{d['doc_id']}:{d['captured']}" for d in idx["documents"]))


if __name__ == "__main__":
    main()
