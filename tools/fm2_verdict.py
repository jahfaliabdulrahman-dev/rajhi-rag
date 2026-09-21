#!/usr/bin/env python3
"""مشتقُّ حكم FM-2 وصنفِ «القراءة الزائدة» — **ملفٌّ له كاتب**.

سؤالان يُجابان من قياسٍ مدفوعٍ سابق، بصفر نداء:

1. **أيُّ التلقينتين؟** v1 وv2 على نفس صفحات التدريب، صفحةً بصفحة.
2. **ما صنفُ «القراءة الزائدة»؟** صفوفٌ يُعيدها القارئ ولا تُصدّقها السلسلة.

ولماذا وُجدت هذه الأداة: الملفُّ الذي برّر صرف $9.64 كُتب **بيد** في جلسةٍ سابقة،
وتغيّر فيه اسمُ مقياسٍ بمعناه (`exact` = 386 في ملف الذراع و383 في الحكم) ⇒
**اسمٌ واحد، رقمان، ولا كاتبَ يفصل**. فصار المشتقُّ هنا: كلُّ رقمٍ يُحسَب من ملفَّي
الذراعين، وكلُّ معيارٍ **معلنٌ في الملف نفسه**، وكلُّ قائمةٍ **كاملة** (كانت مقصوصةً
إلى 14 من 21 فتُوجّه التتبّع إلى ثلثي الدليل).

    python3 tools/fm2_verdict.py --a docs/evidence/20260921-fm2-v1-arm.json \
        --b docs/evidence/20260921-fm2-v2-arm.json \
        --out docs/evidence --overread docs/evidence/20260921-fm2-overread.json
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _per_page(arm: dict) -> dict[int, dict]:
    (name, payload), = arm["prompts"].items()
    return {int(p["page"]): p for p in payload["per_page"]}


def _row(p: dict) -> dict:
    """حقولُ المقارنة، ومعاييرُها **معلنة هنا** لا في الرأس.

    - `exact`: كلُّ الأزواج مطابقة **و** آخرُ رصيدٍ موافق (المعيار الأشدّ).
    - `overread`: صفوفٌ أعادها القارئ ولم تُصدّقها السلسلة (`read − chain_verified`)
      — وهي بعينها التي تُسقطها البوّابةُ عند التسليم، فالأثر على المخرج صفر.
    """
    return {"page": p["page"],
            "rows_read": p.get("rows_read", 0),
            "rows_certified": p.get("rows_certified", 0),
            "rows_chain_verified": p.get("rows_chain_verified", 0),
            "pairs_matching": p.get("pairs_matching_certified", 0),
            "pairs_certified": p.get("pairs_certified", 0),
            "closed": bool(p.get("last_balance_equals_certified")),
            "exact": (p.get("pairs_matching_certified") == p.get("pairs_certified")
                      and bool(p.get("last_balance_equals_certified"))),
            "seconds": p.get("seconds"),
            "cost_usd": float(p.get("cost_usd") or 0.0),
            "overread": max(0, p.get("rows_read", 0)
                            - p.get("rows_chain_verified", 0)),
            "error": p.get("error")}


def _provenance(run: Path) -> dict:
    """نسبُ المرجع من **تقرير التشغيلة** لا من رواية.

    والقياس الذي فرضه (2026-09-21): `corpus_provenance.reader = None` و`629 صفحةً
    بلا ختم` في كوربوس المسح ⇒ فالادّعاء بأن «v2 كتب المرجع» **لا سندَ له**، ولا
    يجوز أن يُقال عكسُه أيضاً. فيُعلن **مجهولاً**.
    """
    rep = run / "slice_report.json"
    if not rep.exists():
        return {"reader": None, "source": f"لا تقريرَ في {run} — النسبُ مجهول",
                "legacy_unstamped_pages": None, "declaration": None}
    d = json.loads(rep.read_text(encoding="utf-8"))
    cp = d.get("corpus_provenance") or {}
    return {"reader": (cp.get("reader") or None),
            "source": "slice_report.json → corpus_provenance",
            "legacy_unstamped_pages": cp.get("legacy_unstamped_pages"),
            "declaration": cp.get("declaration")}


def bias_sentence(prov: dict) -> str:
    """الجملةُ تُبنى من النسب — «مجهول» نتيجةٌ مشروعة، والتخمينُ ليس كذلك."""
    reader = prov.get("reader")
    if not reader:
        legacy = prov.get("legacy_unstamped_pages")
        extra = (f" و{legacy} صفحةً بلا ختم" if isinstance(legacy, int) and legacy else "")
        return ("⚠️ **نسبُ المرجع مجهول**: `corpus_provenance.reader = None`" + extra +
                " ⇒ لا يُقال «منحازٌ إلى b» ولا «محايد» — **الاتجاهُ غير محدَّد**. "
                "وما يصمد مستقلّاً عن النسب: الذراعان طابقا المرجع في **نفس** عدد "
                "الأزواج، وهذا لا يتوقّف على من كتبه.")
    model = reader.get("model")
    pv = reader.get("prompt_version")
    # ⚠️ لا تُقارَن الأذرعُ بالقارئ من هذه الملفات: ملفّاتُ الذراعين لا تسجّل النموذج،
    # فالقول «هو ذراع b نفسه» سيكون **تخميناً آخر** — ويُعلن المعلومُ فقط.
    return (f"⚠️ المرجعُ من قارئٍ معلن: `{model}/{pv}` — والقرارُ يُقرأ على ضوء ذلك، "
            "ولا تُقارَن الأذرعُ به من هذه الملفات (لا تسجّل النموذج).")


def build(a_path: Path, b_path: Path, run: Path | None = None) -> tuple[dict, dict]:
    a_arm, b_arm = _load(a_path), _load(b_path)
    prov = _provenance(run or PROJ / "data" / "local_sample" / "slice_629p")
    a, b = _per_page(a_arm), _per_page(b_arm)
    pages = sorted(set(a) | set(b))
    clean = [p for p in pages if not a[p].get("error") and not b[p].get("error")]

    def tot(d, key):
        return sum(d[p].get(key, 0) for p in clean)

    def secs(d, key):
        vals = sorted(x["seconds"] for x in (d[p] for p in clean) if x.get("seconds"))
        return vals

    def side(d, name):
        s = secs(d, None)
        return {"rows_read": tot(d, "rows_read"),
                "rows_certified": tot(d, "rows_certified"),
                "rows_chain_verified": tot(d, "rows_chain_verified"),
                "pairs_matching": tot(d, "pairs_matching_certified"),
                "overread": sum(_row(d[p])["overread"] for p in clean),
                "closed": sum(1 for p in clean if d[p].get("last_balance_equals_certified")),
                "exact": sum(1 for p in clean if _row(d[p])["exact"]),
                "median_s": round(statistics.median(s), 1) if s else None,
                "p95_s": (s[int(0.95 * (len(s) - 1))] if s else None),
                "errors": sum(1 for p in pages if d[p].get("error"))}

    wins = {"a": 0, "b": 0, "tie": 0}
    for p in clean:
        ka = (a[p].get("pairs_matching_certified", 0), bool(a[p].get("last_balance_equals_certified")))
        kb = (b[p].get("pairs_matching_certified", 0), bool(b[p].get("last_balance_equals_certified")))
        wins["a" if ka > kb else "b" if kb > ka else "tie"] += 1

    diff = [b[p].get("pairs_matching_certified", 0) - a[p].get("pairs_matching_certified", 0)
            for p in clean]
    sa, sb = side(a, "a"), side(b, "b")
    # ما صُرف على صفحاتٍ لم تدخل العدّ (غلبةُ ذراعٍ في صفحة): يُقاس، لأن قول
    # «لم يُصرف على صفحة خارج العدّ» كان غير دقيق — والقياس يُخرجه.
    error_spend = round(sum(_row(a[p])["cost_usd"] + _row(b[p])["cost_usd"]
                            for p in pages
                            if a[p].get("error") or b[p].get("error")), 4)
    verdict = {
        "derived_by": "tools/fm2_verdict.py — كلُّ رقمٍ هنا محسوبٌ من ملفَّي الذراعين",
        "arms": {"a": a_path.name, "b": b_path.name},
        "criteria": {
            "exact": "كل الأزواج مطابقة **و** آخر رصيد مطابق (الأشدّ)",
            "closed": "آخر رصيد مطابق = إقفال السلسلة",
            "overread": "rows_read − rows_chain_verified (صفوفٌ لا تُصدّقها السلسلة)",
        },
        # ⚠️ **كانت هذه الجملة مكتوبةً بيد** — وهي الجملةُ الوحيدة غير المشتقّة في ملفٍّ
        # مشتقّ، فكانت **هي الخطأ**: قالت «المرجع كتبته v2» والكوربوس يقول
        # `corpus_provenance.reader = None` و`629 صفحةً بلا ختم`. والمأخذُ من المدقّق
        # (مالكُ الادّعاء أصلاً) ومنه أيضاً الحكم: **يُشتقّ، ويقول «مجهول» حين يُجهَل.**
        "reference_provenance": prov,
        "reference_bias": bias_sentence(prov),
        "pages": {"paired": len(pages), "clean_in_both": len(clean),
                  "errors_a": sa["errors"], "errors_b": sb["errors"]},
        "a": sa, "b": sb,
        "paired_difference_pairs": {
            "mean": round(statistics.mean(diff), 3), "median": statistics.median(diff),
            "pages_b_ahead": sum(1 for d in diff if d > 0),
            "pages_a_ahead": sum(1 for d in diff if d < 0),
            "pages_tied": sum(1 for d in diff if d == 0)},
        "page_level_wins": wins,
        # **كاملتان لا مقصوصتان** (كانت 14 من 21 فتُوجّه التتبّع إلى ثلثي الدليل)
        "pages_where_a_lost": [p for p in clean
                               if a[p].get("pairs_matching_certified", 0)
                               < b[p].get("pairs_matching_certified", 0)],
        "pages_where_b_lost": [p for p in clean
                               if b[p].get("pairs_matching_certified", 0)
                               < a[p].get("pairs_matching_certified", 0)],
        "spend_usd": round(a_arm["spend_usd"] + b_arm["spend_usd"], 4),
        "spend_on_pages_outside_the_count_usd": error_spend,
        "budget_usd_charged": 13.0,
    }
    overread = {
        "derived_by": "tools/fm2_verdict.py",
        "class": ("صفوفٌ يُعيدها القارئ ولا تُصدّقها السلسلة — تُسقطها البوّابة عند "
                  "التسليم، فالأثر على المخرج صفر، والكلفةُ رموزٌ مدفوعة"),
        "totals": {k: {"a": sa[k], "b": sb[k]} for k in
                   ("rows_read", "rows_chain_verified", "pairs_matching", "overread")},
        "per_page": [{"page": p, "a_overread": _row(a[p])["overread"],
                      "b_overread": _row(b[p])["overread"],
                      "certified": a[p].get("rows_certified", 0)}
                     for p in clean if _row(a[p])["overread"] or _row(b[p])["overread"]],
        "pages_with_any_overread": sum(1 for p in clean
                                       if _row(a[p])["overread"] or _row(b[p])["overread"]),
        # **تسميةُ الصنف من البيانات**: أكبرُ مساهمٍ يُسمّى بعدّاده، ويُقاس معه
        # شرطُ الأثر: هل صدّقت السلسلةُ ما زاد؟ (`chain=0` ⇒ لا يصل إلى المخرج).
        "named_cause": [{"page": p,
                         "a_overread": _row(a[p])["overread"],
                         "b_overread": _row(b[p])["overread"],
                         "a_chain_verified": a[p].get("rows_chain_verified", 0),
                         "certified": a[p].get("rows_certified", 0)}
                        for p in sorted(clean,
                                        key=lambda p: -(  _row(a[p])["overread"]
                                                        + _row(b[p])["overread"]))[:3]],
        "artefact_impact": ("صفرٌ بالبناء: الصفوفُ التي لا تُصدّقها السلسلة تُسقطها البوّابة "
                            "عند التسليم (`proof_source`) — فيُقاس الأثرُ في المخرج لا في "
                            "الرجاء، والكلفةُ المتبقّية رموزٌ مدفوعة."),
        "declared_unknown": ("نصوصُ الصفوف الزائدة لا تُعرَف من الكاش: الذراعان يحفظان "
                             "**عدّاً** لا صفوفاً. معرفتُها تحتاج قراءةً مدفوعة، ولا "
                             "تُصرف بلا سؤال المالك."),
    }
    return verdict, overread


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--a", type=Path, required=True)
    ap.add_argument("--b", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=PROJ / "docs" / "evidence")
    ap.add_argument("--name", default="20260921-fm2-paired-verdict.json")
    ap.add_argument("--run", type=Path, default=PROJ / "data" / "local_sample" / "slice_629p",
                    help="تشغيلةُ المرجع — يُقرأ منها نسبُ الكوربوس فلا يُدَّعى")
    ap.add_argument("--overread", type=Path,
                    default=PROJ / "docs" / "evidence" / "20260921-fm2-overread.json")
    args = ap.parse_args()

    verdict, overread = build(args.a, args.b, args.run)
    args.out.mkdir(parents=True, exist_ok=True)
    vp = (args.out / args.name).resolve()
    vp.write_text(json.dumps(verdict, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    op = args.overread.resolve()
    op.write_text(json.dumps(overread, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    w = verdict["page_level_wins"]
    print(f"صفحاتٌ زوجية: {verdict['pages']['clean_in_both']} · فوزٌ: a={w['a']} b={w['b']} · "
          f"تعادل={w['tie']}")
    print(f"أزواجٌ مطابقة: a={verdict['a']['pairs_matching']} · b={verdict['b']['pairs_matching']} · "
          f"متوسطُ الفرق={verdict['paired_difference_pairs']['mean']}")
    print(f"قراءةٌ زائدة (صفوفٌ لا تُصدّقها السلسلة): a={verdict['a']['overread']} · "
          f"b={verdict['b']['overread']} · صفحاتٌ فيها زيادة: "
          f"{overread['pages_with_any_overread']}")
    print(f"المصروف: ${verdict['spend_usd']} · منها على صفحاتٍ خارج العدّ "
          f"${verdict['spend_on_pages_outside_the_count_usd']}")
    print(f"القوائم كاملة: خسر a في {len(verdict['pages_where_a_lost'])} · "
          f"خسر b في {len(verdict['pages_where_b_lost'])}  (وكانتا مقصوصتين إلى 14)")
    print(f"الملفان: {vp.name} · {op.name}")


if __name__ == "__main__":
    main()
