#!/usr/bin/env python3
"""إعادةُ اشتقاق أحكام فوتر الصفحات من كاشٍ مُجمَّد — بلا نموذج وبلا كلفة.

**لماذا وُجد.** حكمُ صفحةٍ في تقرير قراءةٍ مُجمَّد لا يُعاد إنتاجه إلا بإعادةِ تشغيل، وإعادةُ
التشغيل **ليست بديلًا رخيصًا**: ختمُ القارئ يتحرّك فيُرفض الكاشُ ويُشترى الكشفُ من جديد (قِيس
٢٠٢٦-١٠-٠١: انزياحُ الختم من صيغةٍ إلى صيغةٍ ذاتِ بصمة ⇒ كلُّ صفحةٍ من ص١٩٨ صاعدًا تُقرأ من جديد).
فكلُّ تصحيحٍ يمسّ رقمًا مطبوعًا بعد القراءة (تحكيمٌ بشريّ) يحتاج مسارًا يعيد الحكمَ من الكاش وحدَه.

**وقاعدةُ الثقة ليست إعلانًا بل مقياسًا:** __الأداةُ لا تُصدَّق بنفسها__ — تُقابَل بملفّ التقرير
المُجمَّد على الصفحات التي **لم** تُحكَّم؛ فإن أُعيد إنتاجُ أحكامها، صار حكمُ الصفحات المُحكَّمة
منها صالحًا. وأيُّ فرقٍ **بلا سجلّ تحكيمٍ في الكاش نفسِه** عطبٌ يُسمّى، لا ملاحظةٌ تُمرَّر
(فشلٌ مُغلَق: الخروج بغير صفر).

    python3 tools/rederive_footer_verdicts.py --run data/local_sample/slice_629p_v2
    python3 tools/rederive_footer_verdicts.py --run <dir> --json      # للتسجيل في تقرير

رموزُ الخروج: 0 = كلُّ حكمٍ أُعيد إنتاجُه أو فسرته سجلاتُ التحكيم · 1 = فرقٌ بلا مفسِّر (يُسمّى) ·
2 = تعذّر القياس (لا كاش · لا تقرير).

**وحدُّه:** يقيس **إعادةَ الحكم من الكاش**، لا القارئَ ولا القراءة: صفوفُ الصفحة تُقرأ من الكاش
كما استقرّت (بعد أي استدراكٍ أو إعادةِ قراءةٍ آلية)، ولا يُمَسّ ملفّ. وإن كانت الصفوفُ نفسُها موضعَ
الشكّ فهذه الأداةُ عمياءُ عن ذلك — وهي تقول حدَّها ولا تخفيه.

**وسلوكٌ مقيسٌ يجب أن يُعرَف قبل قراءة الخلاف:** أساسُ الحكم متى توفّرت دلتا الفوتر هو **الدلتا**
(تذييلُ الجار ← تذييلُ الصفحة)، فتحكيمٌ على تذييل صفحةٍ **ينقل أثرَه إلى جارها** — قِيس اصطناعيًّا:
تصحيحُ تذييل ص٢ قلب حكمَ ص٢ **وص٣** معًا. فالتقريرُ المُجمَّد قد يحمل حكمَين متقادمَين بعد تحكيمٍ
واحد، وكلاهما يُفسَّر بسجلّ التحكيم نفسِه (لا بفرقٍ مجهول).
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from statement_qa.footer_oracle import (  # noqa: E402
    FooterReading, check_page_footer, delta_checkable, delta_status,
)
from statement_qa.vlm_reader import chain_derive  # noqa: E402
from tools.scale_slice import partial_first_status, row_from_json  # noqa: E402


def _footer_reading(fd: dict | None) -> FooterReading | None:
    if not fd:
        return None
    return FooterReading(
        debits=Decimal(str(fd["debits"])) if fd.get("debits") else None,
        credits=Decimal(str(fd["credits"])) if fd.get("credits") else None,
        balance=Decimal(str(fd["balance"])) if fd.get("balance") else None,
        raw=fd.get("raw") or {})


def _caches(run: Path) -> list[Path]:
    return sorted((run / "results").glob("pg-*.json"),
                  key=lambda p: int(p.stem.split("-")[1]))


def page_verdicts(run: Path, *, first: int = 1) -> dict[int, dict]:
    """حكمُ كلّ صفحة كما يشتقّه المنتج من الكاش — بنفس الدوالّ ونفس ترتيب الشروط."""
    prev_closing = None
    prev_page_no = None
    prev_footer = None
    cum = {"debits": Decimal("0"), "credits": Decimal("0")}
    cum_broken = False
    out: dict[int, dict] = {}
    for cache in _caches(run):
        pg = int(cache.stem.split("-")[1])
        data = json.loads(cache.read_text(encoding="utf-8"))
        arbitrated = bool(data.get("arbitrated_by"))
        if data.get("error"):
            # قاعدةُ الاستئناف: خطأٌ مخزَّنٌ يُعاد استعمالُه ولا يُعاد شراؤه — والسلسلةُ تنكسر.
            cum_broken = True
            out[pg] = {"status": "unchecked", "basis": "cache-error", "diffs": None,
                       "missing_sheets": None, "arbitrated": arbitrated}
            continue
        rows = chain_derive([row_from_json(r) for r in data.get("raw_rows") or []],
                            prev_balance=prev_closing)
        footer = _footer_reading(data.get("footer"))
        page_no = data.get("page_no")
        gap_missing: list[int] = []
        if (isinstance(page_no, int) and isinstance(prev_page_no, int)
                and page_no > prev_page_no + 1):
            gap_missing = list(range(prev_page_no + 1, page_no))

        chk = check_page_footer(rows, footer, prior=cum, skip=cum_broken)
        pf = partial_first_status(pg, first)
        if pf:
            chk = pf
        # أساسُ التقرير = **دلتا الصفحة** متى توفّرت (تعزل الصفحة عن تلوّثٍ تراكميّ سابق)
        if delta_checkable(prev_footer, footer):
            dchk = delta_status(rows, prev_footer, footer)
            if dchk["status"] != "unchecked":
                chk = {**chk, **dchk, "basis": "delta"}
        elif chk.get("status") == "mismatch":
            # لا دلتا ⇒ الانحرافُ قد يأتي من الجار لا منّا: «غيرُ قابلة للتحقق» أصدقُ من «منزاحة»
            chk = {**chk, "status": "unchecked", "basis": "no-delta"}
        if gap_missing and delta_checkable(prev_footer, footer):
            chk = {**chk, "status": "gap", "basis": "delta",
                   "missing_sheets": gap_missing}
        if chk.get("own"):
            cum["debits"] += chk["own"]["debits"]
            cum["credits"] += chk["own"]["credits"]
        out[pg] = {"status": chk["status"], "basis": chk.get("basis", "cumulative"),
                   "diffs": chk.get("diffs"), "missing_sheets": chk.get("missing_sheets"),
                   "arbitrated": arbitrated}
        prev_footer = footer
        prev_page_no = page_no
        prev_closing = next((r["balance"] for r in reversed(rows)
                             if r["balance"] is not None), prev_closing)
    return out


def _tally(verdicts: dict[int, dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in verdicts.values():
        out[v["status"]] = out.get(v["status"], 0) + 1
    return dict(sorted(out.items()))


def reconcile(run: Path, *, first: int = 1) -> dict:
    """تُقابَل الأحكامُ المُعادُ اشتقاقُها بالتقرير المُجمَّد — والفرقُ بلا تحكيمٍ عطبٌ."""
    report = run / "slice_report.json"
    got = page_verdicts(run, first=first)
    if not report.exists():
        return {"pages": len(got), "frozen": False, "unexplained": {}, "diverged": {},
                "tally": _tally(got), "arbitrations": [], "why": "لا تقريرَ مُجمَّد — أُعيد الاشتقاقُ ولا مقابلة"}
    frozen = {p["page"]: p["footer"] for p in
              json.loads(report.read_text(encoding="utf-8"))["per_page"]}
    diverged = {pg: {"frozen": frozen.get(pg), "recomputed": got[pg]["status"],
                     "arbitrated": got[pg]["arbitrated"]}
                for pg in got if got[pg]["status"] != frozen.get(pg)}
    unexplained = {pg: v for pg, v in diverged.items() if not v["arbitrated"]}
    return {"pages": len(got), "frozen": True,
            "reproduced": len(got) - len(diverged),
            "diverged": diverged, "unexplained": unexplained,
            "tally": _tally(got), "arbitrations": sorted(pg for pg in got if got[pg]["arbitrated"]),
            "frozen_tally": _tally({p["page"]: {"status": p["footer"]} for p in
                                    json.loads(report.read_text(encoding="utf-8"))["per_page"]})}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="إعادةُ اشتقاق أحكام الفوتر من كاشٍ مُجمَّد — بلا نموذج وبلا كلفة.")
    ap.add_argument("--run", required=True, help="مجلّد تشغيلةٍ فيه results/ (و‏slice_report.json للمقابلة)")
    ap.add_argument("--first", type=int, default=1,
                    help="أوّلُ صفحةٍ في التشغيلة (للتشغيلات الجزئية: أولُ صفحةٍ بلا مرجعٍ سابق)")
    ap.add_argument("--json", action="store_true", help="خرجٌ آليّ للتسجيل")
    a = ap.parse_args(argv)

    run = Path(a.run)
    if not (run / "results").exists():
        print(f"⛔ لا كاشَ في {run}/results ⇒ لا قياس (والخروج ٢: تعذّرُ القياس ليس نظافة).",
              file=sys.stderr)
        return 2
    r = reconcile(run, first=a.first)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
    else:
        print(f"صفحاتٌ أُعيد اشتقاقُها: {r['pages']}")
        print(f"  الأعدادُ المُعادُ اشتقاقُها: {r['tally']}")
        if r["frozen"]:
            print(f"  الأعدادُ في التقرير المُجمَّد: {r['frozen_tally']}")
            print(f"  أُعيد إنتاجُ {r['reproduced']}/{r['pages']} حكمًا كما هي")
            print(f"  الصفحاتُ المُحكَّمة في الكاش: {r['arbitrations'] or 'لا شيء'}")
            for pg, v in r["diverged"].items():
                print(f"   · ص{pg}: {v['frozen']} ⇒ {v['recomputed']}"
                      f"{' (تحكيمٌ مسجَّل ✓)' if v['arbitrated'] else ' — **بلا تحكيم**'}")
    if r["unexplained"]:
        print(f"⛔ BLOCK — {len(r['unexplained'])} صفحةً انحرف حكمُها بلا سجلّ تحكيمٍ في الكاش "
              f"(وفرقٌ بلا مفسِّر عطبٌ لا ملاحظة): {sorted(r['unexplained'])}", file=sys.stderr)
        return 1
    print(f"PASS — كلُّ فرقٍ مفسَّرٌ بسجلّ تحكيمٍ في الكاش نفسه ({r['pages']} صفحة).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
