"""تصديقٌ مدفوع — **شاهدٌ خارجيّ** على التذييل المطبوع (لا على قراءتنا).

الغرضُ من الحكم لا من الرغبة: الخطةُ تقول «حقيقةُ الحزمة مُصدَّقة رياضياً لا بشرياً ... ينتهي
بشاهدٍ خارجي» (`handoff/sulaiman/20260922-004133…` §٥/١) — وهذه الأداةُ تُنتج ذلك الشاهد:

    صفحةٌ من كوربوس الحزمة → صورةٌ (200dpi) → **قارئٌ آخر** (`footer_oracle.read_footer` —
    عرفُ المشروع نفسه) → ثلاثةُ أرقامٍ مطبوعة → تُقابَل بثلاثة أرقامنا المقروءة.

**وقاعدتان لا تُخالفان:**
1. **المحليُّ أساسٌ والسحابيُّ تصديق** — لا يُسمح لهذه الأداة أن تُنتج قراءةً تُدخل في المخرجات؛
   تُنتج **مقارنةً** فقط، والقراءةُ المحفوظة تبقى التي في `results/pg-*.json`.
2. **سقفُ صرفٍ صريحٌ قبل التشغيل** (`--max-usd`) — والكلفةُ **المقيسةُ** من `usage` في استجابة
   المزوّد لا من عدّادٍ عندنا، والتوقّفُ عند بلوغ السقف لا بعده.

    python3 tools/oracle_confirm.py --sample 12 --max-usd 1.50
    python3 tools/oracle_confirm.py --pages 2,3,4 --max-usd 0.50 --dry-run

المخرَج: `docs/evidence/oracle-confirmation-<doc_id>.json` — جدولٌ لكل صفحة (المطبوع · المعلوم ·
الحكم) + الاتفاقُ الكلّي + الكلفةُ الحقيقية + الأمرُ الذي أنتج كلَّ رقم.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CORPUS_PDF = PROJ / "data/local_sample/slice_629p/slice_629p.pdf"
RUN = PROJ / "data/local_sample/slice_629p"
CAPTURE = PROJ / "data/training/3e2d360a665c88aa"
PACK = PROJ / "data/eval_pack/pack.json"
# **الشهادةُ تحتوي تذييلاتٍ مطبوعةً لصفحات كشفٍ مصرفيّ** ⇒ لا يجوز أن تُدفَع إلى مستودعٍ عامّ.
# فالمخرَجُ الافتراضي داخل `data/eval_pack/` المُهمَل في `.gitignore`، ويُرفض غيره.
DEFAULT_OUT_DIR = PROJ / "data/eval_pack"
ORACLE_OUT_NAME = "oracle-confirmation"
FIELDS = ("debits", "credits", "balance")


def _dec(v) -> Decimal | None:
    """نصٌّ مطبوعٌ (عربيُّ الأرقام أو بفواصل) ⇒ Decimal بلا تخمين. لا يعرف ⇒ None."""
    if v is None:
        return None
    try:
        from statement_qa.legacy.arabic_digit_parser import norm_num
        out = norm_num(str(v))
    except Exception:
        out = str(v)
    if out in (None, ""):
        return None
    try:
        return Decimal(str(out))
    except (InvalidOperation, ValueError):
        return None


def assert_not_published(path: Path) -> None:
    """يرفض كتابةَ شهادةٍ في مسارٍ يتتبّعُه git — **وبياناتُ الكشف لا تُدفع إلى مستودعٍ عامّ**.

    والفحصُ ليس رأياً: يُسأل `git check-ignore` نفسُه (نفسُ المحرّك الذي يحكم الإهمال)،
    وخارج المستودع لا شأنَ له. وحارسٌ لا يُجرَّب سقوطُه ليس حارساً
    (`tests/test_oracle_confirm.py::test_the_oracle_refuses_to_write_where_git_would_publish_it`).
    """
    import subprocess
    p = path if path.is_absolute() else (Path.cwd() / path)
    if PROJ not in p.parents and p != PROJ:
        return                      # خارج المستودع: لا دفعَ ولا شأن
    if subprocess.run(["git", "-C", str(PROJ), "check-ignore", "-q", str(p)],
                      capture_output=True).returncode == 0:
        return                      # مُهمَلٌ في .gitignore ✓
    raise SystemExit(
        f"⛔ رفضٌ بالاسم: {p.relative_to(PROJ)} **ليس مُهمَلاً** في المستودع — والشهادةُ تحمل "
        f"أرقامَ تذييلات صفحةٍ مصرفية. اكتبها في مسارٍ مُهمَل (مثل data/eval_pack/) أو أضِف "
        f"المسارَ إلى .gitignore، ولا تدفع بياناتِ كشفٍ إلى مستودع.")


def compare_footers(parsed: dict, oracle: dict) -> dict:
    """يقابل ثلاثةَ أرقامٍ مطبوعة بثلاثةٍ مقروءة — **ويُعلن ما لا يُقابَل**.

    والحالاتُ أربعٌ لا اثنتان: اتفاقٌ تام · اختلافٌ مسمّى · «غيرُ مقروء» (قارئٌ آخر لم يقرأ)
    · «غائب» (لا تذييلَ مطبوعاً في الصفحة). ولا يُحسب «غيرُ مقروء» اتفاقاً بحال —
    لأن عدَّ ما لا يُثبت نجاحاً هو الصنفُ الذي نطارده.
    """
    cells, agree, differs, unread, absent = [], 0, [], 0, 0
    for f in FIELDS:
        raw_mine, raw_theirs = parsed.get(f), (oracle or {}).get(f)
        mine, theirs = _dec(raw_mine), _dec(raw_theirs)
        if mine is None and theirs is None:
            verdict = "غائب"
            absent += 1
        elif theirs is None:
            verdict = "غيرُ مقروء"
            unread += 1
        elif mine is None:
            verdict = "عندنا غيرُ مقروء"
            unread += 1
        elif mine == theirs:
            verdict = "مطابق"
            agree += 1
        else:
            verdict = "مختلف"
            differs.append(f)
        # ويُحفظ **المطبوعُ كما طُبع** لا كما صار Decimalاً: الشهادةُ يشهد بها نصُّها،
        # و«7421.8» بدل «1655.84» تغييرٌ لا يلزم — والقيمةُ المُطبَّعةُ في حقلٍ مستقلّ.
        cells.append({"field": f, "ours": raw_mine, "oracle": raw_theirs,
                      "ours_value": str(mine) if mine is not None else None,
                      "oracle_value": str(theirs) if theirs is not None else None,
                      "verdict": verdict})
    compared = agree + len(differs)
    return {"cells": cells, "agree": agree, "differ": differs, "compared": compared,
            "unread": unread, "absent": absent,
            "verdict": ("مطابق" if compared and not differs else
                        ("مختلف" if differs else ("غيرُ مقروء" if unread else "غائب")))}



def wilson(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    """مجالُ ويلسون 95٪ — لأن الحالةَ الحرجةَ عندنا `p̂ = 1` والتقريبُ الطبيعيّ ينهار عندها:

    `p̂ ± z√(p̂(1−p̂)/n)` عند p̂ = 1 يعطي **مجالاً بعرض صفر** — أي «دقّةٌ مطلقة» وهو كذبٌ رياضي
    (احتمالُ ملاحظةِ اتفاقٍ تامٍّ على n=1 سلبي لا يعني صفرَ خطأ في المجتمع). وويلسون يُغطّي
    الحدَّ فيعطي حدّاً أدنى حقيقياً.
    """
    if n <= 0:
        return (0.0, 1.0)
    ph = k / n
    d = 1 + z * z / n
    centre = (ph + z * z / (2 * n)) / d
    half = (z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def rule_of_three(n: int) -> float:
    """قاعدة الثلاثة: صفرُ حالاتٍ سلبية في n ⇒ 95٪ أن معدّلَها < 3/n.

    وهي الصياغةُ الصحيحةُ لِـ«صفرُ اختلافات» — و«دقّةٌ 100٪» ليست صياغةً بل وهم.
    """
    return 3.0 / n if n else float("nan")


def cmd_summary(evidence_path: Path) -> int:
    ev = json.loads(evidence_path.read_text(encoding="utf-8"))
    graded = [r for r in ev["pages"] if r.get("compared") is not None]
    cells = sum(r["compared"] for r in graded)
    agree = sum(r["agree"] for r in graded)
    pages = len(graded)
    pages_ok = sum(1 for r in graded if r["verdict"] == "مطابق")
    fail_cells = cells - agree
    lo, hi = wilson(agree, cells)
    print(f"═══ الملخّصُ الإحصائي — {ev['doc_id']} · الكلفةُ الحقيقية ${ev['cost_usd_actual']:.4f} ═══")
    print(f"  الوحدةُ الأولى (خليّةٌ مطبوعة): {cells} مقارنةً · اتفاق {agree} · اختلاف {fail_cells}")
    print(f"    ⇒ wilson 95%: [{lo:.6f}, {hi:.6f}]")
    if fail_cells:
        print(f"    ⇒ معدّلُ الخطأ  {fail_cells / cells:.5f}  (wilson: [{1 - hi:.6f}, {1 - lo:.6f}])")
    else:
        print(f"    ⇒ صفرُ اختلافاتٍ في {cells} ⇒ **قاعدة الثلاثة: معدّلُ الخطأ < {rule_of_three(cells):.5f} "
              f"({rule_of_three(cells) * 1000:.2f} في الألف) بثقة 95٪** — وليست «دقّة 100٪»")
    print(f"  الوحدةُ الثانية (صفحةٌ كاملة): {pages_ok}/{pages} مطابقةً تماماً · "
          f"غيرُ مقروءة {sum(1 for r in graded if r['verdict'] == 'غيرُ مقروء')} · "
          f"غائبة {sum(1 for r in graded if r['verdict'] == 'غائب')}")
    if pages:
        lo2, hi2 = wilson(pages_ok, pages)
        print(f"    ⇒ wilson 95% (صفحةً صفحة): [{lo2:.6f}, {hi2:.6f}]"
              + (f" · قاعدة الثلاثة < {rule_of_three(pages):.5f}" if pages_ok == pages else ""))
    differ = [r["page"] for r in graded if r["verdict"] == "مختلف"]
    print(f"  الصفحاتُ المختلفة: {differ or 'لا شيء'}")
    print("\n  ⚠ حدُّ الصدق: التصديقُ على **التذييل المطبوع** (٣ خلايا/صفحة) لا على الصفوف فرادى —"
          "\n     فخطأان متعاكسان داخل صفحةٍ تُغطّيهما بوّابةُ الإطار (Σ − المطبوع = 0) ولا يكشفهما القراءة."
          "\n     والوحداتُ متجمّعةٌ (صفحاتٌ داخل كشوف) ⇒ المجالُ أضيقُ من الحقيقة؛ يُعلن ولا يُجمَّل.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="تصديقٌ مدفوعٌ بشاهدٍ خارجيّ على التذييل المطبوع")
    ap.add_argument("--pack", type=Path, default=PACK)
    ap.add_argument("--pdf", type=Path, default=CORPUS_PDF)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--sample", type=int, default=0, help="عددُ صفحاتٍ من الإحصاء (بالترتيب)")
    ap.add_argument("--all-corpus", action="store_true",
                    help="الكوربوسُ كلُّه (629 صفحة) — تصديقٌ كامل لا عيّنة")
    ap.add_argument("--pages", default="", help="صفحاتٌ صريحة: 2,3,4 (تتجاوز --sample)")
    ap.add_argument("--max-usd", type=float, default=0.0, help="سقفُ صرفٍ صريح — إلزاميّ للصرف")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true", help="يُجهّز الصورَ والصفحاتِ بلا نداءِ نموذج")
    ap.add_argument("--summary", type=Path, default=None,
                    help="يقرأ شهادةً مكتوبةً ويطبع المجالاتِ الإحصائية (بلا نداءِ نموذج)")
    args = ap.parse_args(argv)

    if args.summary:
        return cmd_summary(args.summary)

    pack = json.loads(args.pack.read_text(encoding="utf-8"))
    census = [int(x["page"]) for x in pack["census"]["pages"]]
    if args.all_corpus:
        import pymupdf as _f
        with _f.open(args.pdf) as _d:
            pages = list(range(1, len(_d) + 1))
    else:
        pages = ([int(x) for x in args.pages.split(",") if x.strip()] if args.pages.strip()
                 else census[:args.sample] if args.sample else census)
    doc = pack["identity"]
    out_path = args.out or (DEFAULT_OUT_DIR / f"{ORACLE_OUT_NAME}-{doc}.json")
    assert_not_published(out_path)

    print("═══ تصديقٌ بشاهدٍ خارجيّ — التذييلُ المطبوع يُقابَل بقارئٍ آخر ═══")
    print(f"  المستند: {doc} · الصفحات: {len(pages)} · السقف: ${args.max_usd:.2f}"
          f"{' · **بلا صرف** (dry-run)' if args.dry_run else ''}")
    print(f"  المصدر: {args.pdf.relative_to(PROJ)} · {args.dpi}dpi")

    import pymupdf  # PyMuPDF: التصييرُ يحتاج محرّك الصفحة
    from statement_qa.footer_oracle import read_footer

    ledger: dict = {"pages": 0, "request_calls": 0, "cost_usd": 0.0, "models": []}
    spent = 0.0
    rows, tmp = [], Path(tempfile.mkdtemp(prefix="oracle-"))
    try:
        with pymupdf.open(args.pdf) as doc_pdf:
            for n in pages:
                parsed = json.loads((RUN / "results" / f"pg-{n:03d}.json").read_text(encoding="utf-8")).get("footer") or {}
                png = tmp / f"pg-{n:03d}.png"
                doc_pdf[n - 1].get_pixmap(dpi=args.dpi).save(str(png))
                if args.dry_run:
                    rows.append({"page": n, "png_bytes": png.stat().st_size, "verdict": "بلا نداء"})
                    continue
                if args.max_usd and ledger["cost_usd"] >= args.max_usd:
                    print(f"  ⛔ بلغ السقف (${ledger['cost_usd']:.4f} ≥ ${args.max_usd:.2f}) — توقّف")
                    break
                read = read_footer(str(png), stats=ledger)
                # `chat_vlm_image` يُحدّث stats بـ`usage` الخام ⇒ اسمُ الحقل `cost` لا `cost_usd`،
                # وكلُّ نداءٍ يطمس سابقه ⇒ **فالتراكمُ عندنا: نجمع كلفةَ كل نداء**.
                # (والفرقُ عن سابقه كان عطباً: تراكمٌ ينقص — كشفته الأرقامُ لا قراءةُ الكود.)
                per_call = float(ledger.get("cost") or 0.0)
                if per_call < 0:
                    raise SystemExit(f"⛔ كلفةٌ سالبة من المزوّد ({per_call}) — أتوقّف")
                prev_spent = spent
                spent += per_call
                if spent + 1e-9 < prev_spent:
                    raise SystemExit("⛔ التراكمُ نقص — حارسُ السقف معطوبٌ بالتعريف، أتوقّف")
                ledger["cost_usd"] = round(spent, 6)
                ledger["cost_last_call"] = round(per_call, 6)
                oracle = {"debits": getattr(read, "debits", None), "credits": getattr(read, "credits", None),
                          "balance": getattr(read, "balance", None)} if read else {}
                cmp_ = compare_footers(parsed, {k: (str(v) if v is not None else None) for k, v in oracle.items()})
                ledger["pages"] = int(ledger.get("pages") or 0) + 1
                if ledger.get("model"):
                    ledger["models"] = sorted(set(ledger.get("models") or []) | {ledger["model"]})
                rows.append({"page": n, "png_bytes": png.stat().st_size,
                             "ours": {f: parsed.get(f) for f in FIELDS},
                             "oracle": {k: (str(v) if v is not None else None) for k, v in oracle.items()},
                             **cmp_})
                mark = {"مطابق": "✓", "مختلف": "✗", "غيرُ مقروء": "?", "غائب": "—"}[cmp_["verdict"]]
                extra = f" ← مختلف: {','.join(cmp_['differ'])}" if cmp_["differ"] else ""
                print(f"  [{mark}] ص{n:>3} · مطابق {cmp_['agree']}/3 · غائب {cmp_['absent']}{extra}"
                      f" · كلفةٌ تراكمية ${ledger['cost_usd']:.4f}")
    finally:
        for f in tmp.glob("*.png"):
            f.unlink()
        tmp.rmdir()

    graded = [r for r in rows if r.get("compared") is not None]
    agg = {
        "pages": len(graded), "cells_compared": sum(r["compared"] for r in graded),
        "cells_agree": sum(r["agree"] for r in graded),
        "pages_matching": sum(1 for r in graded if r["verdict"] == "مطابق"),
        "pages_differing": [r["page"] for r in graded if r["verdict"] == "مختلف"],
        "pages_unread": [r["page"] for r in graded if r["verdict"] in ("غيرُ مقروء", "غائب")],
        "reading_pages_unread": sum(1 for r in graded if r["verdict"] == "غيرُ مقروء"),
    }
    if agg["cells_compared"]:
        agg["agreement_rate"] = round(agg["cells_agree"] / agg["cells_compared"], 6)
    evidence = {
        "what": "تصديقٌ خارجيّ: تذييلُ كل صفحةٍ مطبوعاً بقارئٍ آخر يُقابَل بقراءتنا",
        "doc_id": doc, "pdf": str(args.pdf.relative_to(PROJ)), "dpi": args.dpi,
        "command": ("python3 tools/oracle_confirm.py " + " ".join(argv if argv is not None else sys.argv[1:])),
        "cost_usd_actual": round(float(ledger.get("cost_usd") or 0.0), 6),
        "usage": {k: v for k, v in ledger.items() if k not in ("cost_usd", "models")},
        "cost_source": "usage.cost من استجابة المزوّد، مُتراكَمٌ عبر النداءات (لا عدّادٌ من عندنا)",
        "max_usd_cap": args.max_usd, "dry_run": bool(args.dry_run),
        "aggregate": agg, "pages": rows,
        "rule": "المحليُّ أساسٌ والسحابيُّ تصديق — ولا قراءةَ منه تدخل المخرجات",
        "unread_is_not_agreement": "«غيرُ مقروء» لا يُحسب اتفاقاً ولا اختلافاً — يُعلن ويُعدّ",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print("\n── الحصيلة:")
    print(f"  صفحاتٌ طُوبقت: {agg['pages']} · خلايا: {agg['cells_compared']} · اتفاق: {agg['cells_agree']}"
          f" ({100 * agg.get('agreement_rate', 0):.1f}%)")
    print(f"  صفحاتٌ مطابقةٌ تماماً: {agg['pages_matching']} · مختلفة: {agg['pages_differing'] or 'لا شيء'}"
          f" · غيرُ مقروءة: {agg['reading_pages_unread']}")
    print(f"  **الكلفةُ الحقيقية (من usage المزوّد): ${evidence['cost_usd_actual']:.6f}**"
          f" · نداءات: {ledger.get('request_calls')}")
    try:
        shown = out_path.relative_to(PROJ)
    except ValueError:
        shown = out_path
    print(f"  الشهادة: {shown}")
    if not evidence["cost_usd_actual"]:
        print(f"  ℹ الكلفةُ صفرٌ فعلياً (usage المزوّد: {json.dumps(ledger, ensure_ascii=False)[:220]})")
    return 0 if not agg["pages_differing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
