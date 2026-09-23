#!/usr/bin/env python3
"""شهادةُ الحزمة المجمّدة — **أمرٌ واحد يُعيد إنتاج الشهادة** (البند ٤: «دليلُ الإنجاز»).

يكتب `docs/evidence/<date>-item4-pack-free-capture.json` وفيه:
  · **قائمةُ الـ٢٠٠ صفحة كاملةً** + بصمةُ المجموعة كاملةً (sha256) — فالختمُ لا يغطّي الإحصاءَ وحدَه،
    وسمُّ «تغييرُ صفحةٍ مقيَّدة ⇒ يسقط» يصير قابلًا للتنفيذ على كل الحزمة.
  · بوابتا الحزمة (`size_gate` · `intersection_gate`) وسمومُها.
  · عدّاداتُ الالتقاط الحيّة (من البيان على القرص لا من ذاكرة تشغيلة).
  · **إعلانُ ما أُنفِق سابقًا** (عيّنةُ ذراعَي FM-2) وحجمُ المجموعة الحرّة فعلًا — فلا يُدّعى
    «لم تُستعمل في أيّ ضبط» ما لم يُقس.
والقاعدة ١٣ محفوظة: لا قيمةَ مبلغٍ هنا — بصماتٌ وأعدادٌ وأسماءُ ملفّات.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.pack_io import data_root  # noqa: E402 — **جذرٌ واحد** (يعمل من شجرة عمل)

DATA = data_root()                       # الجذرُ المشترك: الأدلّةُ الثقيلةُ باقيةٌ في الشجرة الأمّ
PACK = DATA / "data/eval_pack/pack.json"
TRAIN = DATA / "data/training"
EVID = DATA / "docs/evidence"
FM2 = ("docs/evidence/20260921-fm2-v1-arm.json", "docs/evidence/20260921-fm2-v2-arm.json")


def page_numbers(pack: dict) -> list[int]:
    out = {int(p["page"]) if isinstance(p, dict) else int(p) for p in pack["census"]["pages"]}
    for r in pack["ranges"]:
        out |= {int(p) if not isinstance(p, dict) else int(p["page"]) for p in r["pages"]}
    return sorted(out)


def bias_metrics(pages: set[int]) -> dict:
    """الانحياز **مقيسًا لا مُعلَنًا** — بمقياسين يُعرضان معًا (قرارُ المالك 2026-09-23: «(أ)»).

    والقاعدةُ الحاكمة: **لا يُنتقى مقياسٌ واحد**. المقياسُ الأوّل (صفوفٌ لم تُثبّتها السلسلة) هو ما
    بُنيت الذراعان لقياسه ⇒ **v2 يتقدّم فيه**؛ والمقياسان الآخران (اكتمالُ الأزواج · انحرافُ العدّ)
    يرجّحان **v1** ⇒ فيُعلنان معه. وإن سقط أحدُهما من الشهادة فقد صار إعلانُ الانحياز دعايةً لا قياس.
    """
    per = {}
    for tag in ("v1", "v2"):
        f = EVID / f"20260921-fm2-{tag}-arm.json"
        d = json.loads(f.read_text(encoding="utf-8"))
        per[tag] = {"file": f.name, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()[:16],
                    "pages": {e["page"]: e for e in d["prompts"][tag]["per_page"] if "rows_read" in e}}
    common = sorted(set(per["v1"]["pages"]) & set(per["v2"]["pages"]))
    outside = [p for p in common if p not in pages]

    def rows(a, p):
        e = per[a]["pages"][p]
        return (e["rows_read"] - e["rows_chain_verified"],
                max(0, e["pairs_certified"] - e["pairs_matching_certified"]),
                abs(e["rows_read"] - e["rows_certified"]))

    chain = {a: sum(rows(a, p)[0] for p in outside) for a in ("v1", "v2")}
    pairs = {a: sum(rows(a, p)[1] for p in outside) for a in ("v1", "v2")}
    devc = {a: sum(rows(a, p)[2] for p in outside) for a in ("v1", "v2")}
    won = {a: sum(1 for p in outside if rows(a, p)[0] < rows("v2" if a == "v1" else "v1", p)[0])
           for a in ("v1", "v2")}
    best = lambda d: min(d, key=lambda k: (d[k], k))
    return {
        "decision": "(أ) **إعلانُ انحيازٍ مؤرَّخ مع عمود المقياسين** — قرارُ المالك 2026-09-23",
        "why_it_exists": ("ذراعا FM-2 سحبا صفحاتٍ من الحزمة **قبل** ختمها (2026-09-21 مقابل 2026-09-22)، "
                          "فلا يجوز أن يُنشر مقياسٌ من هذه الحزمة بلا هذا الإعلان."),
        "arms": {a: {"file": per[a]["file"], "sha256": per[a]["sha256"][:16]} for a in ("v1", "v2")},
        "measured_pages_outside_pack": len(outside),
        "metrics": {
            "chain_unproven_rows": {**chain, "better": best(chain), "meaning": "صفوفٌ قُرئت ولم تُثبّتها السلسلة (الأقلُّ أفضل)"},
            "pages_won": {**won, "better": best(won), "meaning": "صفحاتٌ تفوّق فيها كلُّ طرفٍ بالمقياس أعلاه"},
            "missing_pairs": {**pairs, "better": best(pairs), "meaning": "أزواجٌ ناقصة عن المُصدَّق (الأقلُّ أفضل)"},
            "row_count_deviation": {**devc, "better": best(devc), "meaning": "انحرافُ عدد الصفوف عن المُصدَّق (الأقلُّ أفضل)"},
        },
        "reading": ("على مقياس السلسلة (وهو ما بُنيت الذراعان لقياسه) **v2 يتقدّم بلا أيّ صفحةٍ من الحزمة**، "
                    "وعلى اكتمال الأزواج وانحراف العدّ **v1 يتقدّم قليلًا** ⇒ القرارُ يمضي بالمقياسين معلنين."),
        "invalidated_by": ("تغيُّرُ بصمة الحزمة (‏`pages_sha256`) أو تغيُّرُ ملفَّي الذراعين ⇒ أعِد التوليد: "
                           "`python3 tools/pack_evidence.py` — والقارئُ في `tests/test_pack_seal_and_root.py` يقيسه."),
    }


def main() -> int:
    if not PACK.exists():
        raise SystemExit("لا حزمةَ على القرص — الشهادةُ تُبنى حيث الأدلّةُ موجودة (الالتقاطُ خارج git)")
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    pages = page_numbers(pack)
    digest = hashlib.sha256(json.dumps(pages).encode()).hexdigest()

    raw = pack.get("doc_id") or pack.get("identity")
    ident = raw.get("doc_id") if isinstance(raw, dict) else raw
    if not ident:
        raise SystemExit("⛔ الحزمةُ بلا هويّة (doc_id/identity) ⇒ لا شهادةَ بلا مفتاح")
    doc_id = str(ident)
    man = TRAIN / doc_id / "manifest.json"
    cap = json.loads(man.read_text(encoding="utf-8")) if man.exists() else {}
    captured = {int(d.name.split("-")[-1]) for d in (TRAIN / doc_id).glob("pg-*")
                if d.name.split("-")[-1].isdigit()}

    spent: set[int] = set()
    arms = []
    for f in FM2:
        p = ROOT / f
        if not p.exists():
            continue
        s = json.loads(p.read_text(encoding="utf-8")).get("sample", {})
        pg = {int(x) for x in s.get("pages") or []}
        arms.append({"file": p.name, "from": s.get("from"), "picked": len(pg),
                     "intersection_with_pack": len(pg & set(pages))})
        spent |= pg

    free = sorted(set(range(1, 627)) - (captured | spent))
    runs, cur = [], []
    for p in free:
        if cur and p == cur[-1] + 1:
            cur.append(p)
        else:
            if cur:
                runs.append(len(cur))
            cur = [p]
    if cur:
        runs.append(len(cur))

    ev = {
        "what": "شهادةُ الحزمة المجمّدة بعد إغلاق التلوّث (البند ٤) — والقياسُ يأتي من القرص لا من نصّ",
        "generated_by": "python3 tools/pack_evidence.py",
        "date": date.today().isoformat(),
        "document": doc_id,
        "value_redaction": "القاعدةُ ١٣: لا قيمةَ مبلغٍ في هذا الملفّ — بصماتٌ وأعدادٌ وأسماءُ ملفّات",
        "pack": {
            "size_gate": pack["size_gate"],
            "intersection_gate": {k: v for k, v in pack["intersection_gate"].items()},
            "capture_mode": pack.get("capture_mode"),
            "built_at": pack.get("built_at"),
            "census_fingerprint": (pack.get("census") or {}).get("fingerprint"),
            "pages": pages,
            "pages_count": len(pages),
            "pages_sha256": digest,
            "note": ("بصمةُ المجموعة أعلاه تغطّي **الإحصاءَ والمديات** معًا؛ وكانت الشهادةُ السابقة "
                     "تغطّي الإحصاءَ وحدَه (٥٠ من ٢٠٠). فأدخلها في سمّ «تغييرُ صفحةٍ مقيَّدة»."),
        },
        "capture": {
            "command": ("python3 tools/capture_training.py --run data/local_sample/slice_629p "
                        "--export data/local_sample/export-629p.xlsx --out data/training"),
            "policy": "الحمايةُ بنيويّة: حزمةٌ على القرص تُستثنى بلا علَم (والعملُ الحقيقيّ في البيان)",
            "exclusion": (cap.get("pack_exclusion") or {}),
            "pages": cap.get("pages", {}),
            "cost_usd": cap.get("cost_usd"),
        },
        "spent_before_the_pack": {
            "arms": arms,
            "measured": ("صفحاتُ ذراعَي FM-2 (مقارنةُ التلقينتين) تتقاطع مع الحزمة: "
                         f"{len(set(pages) & spent)} من {len(pages)} — وهذا **إنفاقٌ سابقٌ لختم الحزمة** "
                         "(الشهادةُ 2026-09-21، والحزمةُ 2026-09-22) لا يمنعه استثناءُ الالتقاط."),
            "free_pages": len(free),
            "longest_contiguous_free_run": max(runs, default=0),
            "consequence": ("اختيارُ ٢٠٠ صفحةٍ «لم تُنفَق في أيّ ضبط» **غيرُ ممكنٍ ببنية المديات الحالية**: "
                            "المجموعةُ الحرّة ٢٠٨ صفحة كلُّها %3==0 ⇒ أطولُ مدًى متّصلٍ فيها صفحةٌ واحدة "
                            "(والمطلوب ٣ مديات × ٥٠ متّصلة) ⇒ القرارُ للمالك: إعلانُ الانحياز المؤرَّخ، "
                            "أو تغييرُ بنية الاختيار إلى صفحاتٍ متفرّقة (٢٠٨ ≥ ٢٠٠ بهامش ٨)."),
        },
        "bias_declaration": bias_metrics(set(pages)),
        "invalidates": {
            "file": "docs/evidence/20260922-item4-step1-gate3-eval-pack.json",
            "why": ("ذاك سجلٌّ مؤرَّخ يقول `capture_mode=explicit-list · captured=416 · intersection=133 · "
                    "pass=false` — وهذا صحيحٌ بتاريخه ولا يُمحى؛ والحالُ اليومَ يخالفه ويكفيه إحالةٌ "
                    "لا محو (الرسالةُ المؤرَّخة تُبطَل بتصريحٍ مؤرَّخ يُحيل إلى الحيّ)."),
        },
    }
    EVID.mkdir(parents=True, exist_ok=True)
    out = EVID / f"{date.today().strftime('%Y%m%d')}-item4-pack-free-capture.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"الشهادةُ: {out.relative_to(ROOT)}")
    print(f"  الحزمة {len(pages)} صفحة · بصمةُ المجموعة {digest[:16]} · التقاطع {len(pack['intersection_gate']['intersection'])}"
          f" · مستثناةٌ من الالتقاط {len(captured & set(pages))}")
    print(f"  المُنفَقُ سابقًا: {len(set(pages) & spent)} صفحةً من الحزمة (ذراعا FM-2) · الحرُّ {len(free)} · أطولُ مدًى {max(runs, default=0)}")
    bm = ev["bias_declaration"]["metrics"]
    print(f"  إعلانُ الانحياز: خارجَ الحزمة {ev['bias_declaration']['measured_pages_outside_pack']} صفحة · "
          f"سلسلةٌ غيرُ مُثبَتة v1 {bm['chain_unproven_rows']['v1']} → v2 {bm['chain_unproven_rows']['v2']} · "
          f"أزواجٌ ناقصة {bm['missing_pairs']['v1']} → {bm['missing_pairs']['v2']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
