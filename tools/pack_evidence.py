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
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "data/eval_pack/pack.json"
TRAIN = ROOT / "data/training"
EVID = ROOT / "docs/evidence"
FM2 = ("docs/evidence/20260921-fm2-v1-arm.json", "docs/evidence/20260921-fm2-v2-arm.json")


def page_numbers(pack: dict) -> list[int]:
    out = {int(p["page"]) if isinstance(p, dict) else int(p) for p in pack["census"]["pages"]}
    for r in pack["ranges"]:
        out |= {int(p) if not isinstance(p, dict) else int(p["page"]) for p in r["pages"]}
    return sorted(out)


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
