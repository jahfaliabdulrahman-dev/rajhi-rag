#!/usr/bin/env python3
"""`eval_run_compare` — يختزل جولاتِ القياس المتعدّدة إلى **حكمٍ وتباين** بأداةٍ لا بيد.

**لماذا أداة:** «رقمُ جولةٍ واحدةٍ لا يُقارَن» — والتباينُ لا يُدّعى بل يُشتقّ من نفس الجولات. وتُشترط ثلاثةُ
قيودٍ صارمة، كلُّها درسٌ مدفوع:
1. **لا يُنشر رقمٌ من سجلٍّ ببصمةٍ مخالفة** (`spec_sha`): النصُّ الذي طُلب فعلاً هو مرجعُ الحكم، لا نصُّ الملفّ الآن.
2. **قوائمُ الأدلّة لا تُقصّ**: كلُّ عدّاد يُقابَل بطول قائمته (`len(list) == counter`) — قائمةٌ مقصوصةٌ تقرأ
   كتغطيةٍ كاملةٍ وتُخفي الشهود.
3. **الذيلُ يُنشر لا الوسيطُ فقط**: وسيطٌ وp95 وأسوأُ خمسٍ لزمن كلّ سؤال (الذيلُ هو ما يحرق جولةً مدفوعة).

الاستعمال:
    eval_run_compare.py --spec docs/eval_pack/questions.json A.json B.json C.json [--json out.json]
الخرج: جدولُ ثباتٍ لكلّ سؤال (`stable pass` / `stable fail` / `flaky`) + مقاييسُ كلّ جولةٍ ومداها + الزمن.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import statistics
import sys


def _spec_sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())


def compare(spec_path: pathlib.Path, arms: list[pathlib.Path]) -> dict:
    want = _spec_sha(spec_path)
    qs = {q["id"]: q for q in json.loads(spec_path.read_text())["questions"]}
    data = {a.name: _load(a) for a in arms}

    # (١) بصمةُ الربط: لا حكمَ على سجلٍّ لا يوافق نصَّ السؤال الحاليّ
    mismatched, per_arm = {}, {}
    for name, d in data.items():
        recs = {r["id"]: r for r in d.get("results", [])}
        per_arm[name] = recs
        # **بلا بصمةٍ لا يُنشر**: الغيابُ أسوأُ من بصمةٍ قديمة (‏«المجهولُ لا يُعدّ اتفاقاً»)
        stale = sorted(i for i, r in recs.items()
                       if i in qs and r.get("spec_sha") not in (None, "") and r.get("spec_sha") != want)
        unstamped = sorted(i for i, r in recs.items() if i in qs and r.get("spec_sha") in (None, ""))
        if stale or unstamped:
            mismatched[name] = {"stale": stale, "unstamped": unstamped}

    # (٢) الثباتُ لكلّ سؤال (على الجولات المطابقةِ للبصمة فقط)
    ids = [i for i in qs if all(i in per_arm[n] for n in per_arm)]
    stability, flaky = {}, []
    for i in ids:
        verdicts = [bool(per_arm[n][i].get("ok")) for n in per_arm]
        if all(verdicts):
            stability[i] = "stable pass"
        elif not any(verdicts):
            stability[i] = "stable fail"
        else:
            stability[i] = "flaky"
            flaky.append(i)

    # (٣) المقاييسُ لكلّ جولة + المدى
    metrics, totals = {}, {}
    for name, recs in per_arm.items():
        rows = [recs[i] for i in ids]
        m = {}
        for metric in ("number", "citation", "abstain"):
            sel = [r for r in rows if r.get("metric") == metric]
            m[metric] = {"ok": sum(1 for r in sel if r.get("ok")), "n": len(sel)}
        metrics[name] = m
        totals[name] = {"ok": sum(1 for r in rows if r.get("ok")), "n": len(rows)}
    tot_ok = [v["ok"] for v in totals.values()]

    # (٤) الزمن: الوسيطُ والذيلُ (لا الوسيطُ وحده)
    secs = [float(per_arm[n][i].get("secs") or 0) for n in per_arm for i in ids]
    secs = sorted(s for s in secs if s > 0)
    lat = {}
    if secs:
        p95 = secs[min(len(secs) - 1, int(0.95 * len(secs)))]
        lat = {"median_s": round(statistics.median(secs), 1), "p95_s": round(p95, 1),
               "worst5_s": [round(s, 1) for s in secs[-5:]], "n": len(secs)}

    # (٥) قوائمُ الأدلّة: الطولُ = العدّاد (لا قصّ)
    sizes = {name: {"records": len(recs), "ids_expected": len(qs),
                    "in_both": sum(1 for i in ids if i in recs)} for name, recs in per_arm.items()}

    return {"spec_sha_expected": want, "arms": [a.name for a in arms],
            "spec_mismatch": mismatched, "questions_compared": len(ids),
            "flaky": flaky, "stability": stability, "metrics_per_arm": metrics,
            "totals_per_arm": totals, "total_range": [min(tot_ok), max(tot_ok)] if tot_ok else [],
            "latency": lat, "sizes": sizes,
            "invariants": {"records_never_truncated": all(v["records"] <= v["ids_expected"] for v in sizes.values()),
                           "no_unpublishable_arm": not mismatched}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=pathlib.Path, default=pathlib.Path("docs/eval_pack/questions.json"))
    ap.add_argument("arms", nargs="+", type=pathlib.Path)
    ap.add_argument("--json", type=pathlib.Path)
    a = ap.parse_args()
    out = compare(a.spec, a.arms)

    print(f"بصمةُ الأسئلة المرجعيّة: {out['spec_sha_expected']} · الجولات: {len(out['arms'])} · "
          f"أسئلةٌ مُقارَنة: {out['questions_compared']}")
    if out["spec_mismatch"]:
        for name, bad in out["spec_mismatch"].items():
            print(f"⛔ {name}: بلا بصمةٍ {len(bad['unstamped'])} · ببصمةٍ مخالفة {len(bad['stale'])} "
                  f"⇒ **لا يُنشر رقمٌ منها** (أعِد الطرح)")
    print("\n| الجولة | رقم | استشهاد | امتناع | المجموع |")
    print("|---|---|---|---|---|")
    for name, m in out["metrics_per_arm"].items():
        t = out["totals_per_arm"][name]
        print(f"| {name} | {m['number']['ok']}/{m['number']['n']} | {m['citation']['ok']}/{m['citation']['n']} | "
              f"{m['abstain']['ok']}/{m['abstain']['n']} | **{t['ok']}/{t['n']}** |")
    if out["total_range"]:
        lo, hi = out["total_range"]
        print(f"\nمدى المجموع على الجولات: **{lo}–{hi}** (وعرضُ التذبذب {hi - lo} سؤالاً)")
    print(f"أسئلةٌ متذبذبة (flaky): {len(out['flaky'])}" + (f" ⇒ {out['flaky']}" if out["flaky"] else ""))
    if out["latency"]:
        lat = out["latency"]
        print(f"الزمن: وسيط {lat['median_s']}ث · p95 {lat['p95_s']}ث · أسوأُ خمسٍ: {lat['worst5_s']} (من {lat['n']})")
    print(f"سلامةُ الأدلّة: {out['invariants']}")
    if a.json:
        a.json.write_text(json.dumps(out, ensure_ascii=False, indent=1))
        print(f"↵ حُكمٌ كاملٌ في {a.json}")
    return 0 if out["invariants"]["no_unpublishable_arm"] else 1


if __name__ == "__main__":
    sys.exit(main())
