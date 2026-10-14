#!/usr/bin/env python3
"""**التغطيةُ المتوقَّعة — تُحسب قبل الصرف ولا تُستشرف** (R112-2 · شرطُ مراجعة ١١٢).

**العلّةُ التي وُلدت منها:** رقمُ «≈٤٧ من ٥٠» كُتب في تقريري بحسابٍ يدويّ **يتجاهل الأسئلةَ الخمسة
المركّبة** (سقفُها ٧٢ نداءً لا ٣٦) ⇒ سقط بالقياس (المحاكاةُ قالت **٢٤ من ٥٠** عند سقف العشرة).
**والقاعدة:** التغطيةُ **دالّةٌ محسوبة** في السعرِ والسقفِ وترتيبِ الحزمة، لا رأي — فتُطبع قبل الدفع.

## ما تفعله بالحرف

تُعيد تشغيل **القانون نفسه** الذي تحكم به الحلقةُ المدفوعة — لا نسخةً ثانيةً منه:
`cap_verdict` من `tools/eval_questions` (وحدَه: **المُنفَقُ المُحاسَب مقابل السقف** — والحجزُ
الاستباقيُّ أُزيل في R117-4)، و`question_ceiling` من التطبيق (`statement_qa.qa`) للرقم **الاستشاريّ**
الذي تقيسه بوّابةُ `check_cap_can_carry` (هل يحمل السقفُ أوسعَ سؤال أصلًا).
وتُغذّى بعددِ نداءاتٍ لكلّ سؤال **من آخر جولةٍ محفوظة** (أرضيةٌ: أثرُه + ١)
وبسعرِ نداءٍ **مشهود** (من الجولة السابقة أو من سطر الأمر) — **وبلا أيّ نداءِ نموذج ⇒ $0**.

## الاستعمال

    python3 tools/expected_coverage.py --cap 0.15 --price-per-call 0.000633 \\
        --from-answers data/eval_pack/answers-r108-02.json

وتطبع: أين يتوقّف القانونُ · التغطيةَ من ٥٠ · الصرفَ المتوقَّع · **وهل يستطيع السقفُ أن يحمل أوسعَ
سؤال أصلًا** (بوّابةٌ لا تمرّ مسرح، كبوّابةٍ لا تفشل).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from tools.eval_questions import (  # noqa: E402
    PER_CALL_MARGIN,
    cap_verdict,
)

QUESTIONS = pathlib.Path(__file__).resolve().parent.parent / "docs" / "eval_pack" / "questions.json"


def question_ceiling(question: str) -> int:
    """**المرآةُ الوحيدةُ المسموحة:** تُنادي التطبيقَ نفسَه — لا تُعيد تعريفَ الحدّ."""
    from statement_qa.qa import question_ceiling as _qc      # noqa: PLC0415

    return _qc(question)


def calls_from_answers(path: pathlib.Path) -> tuple[dict[str, int], str]:
    """عددُ النداءات لكلّ سؤال من جولةٍ محفوظة — **ومعه إعلانُ مصدره** (R113-1).

    **المصدرُ الأوّلُ الردودُ المشهودة** (`replies_observed` · ملفّاتُ R113 فصاعدًا): عددٌ لا أرضية
    ⇒ فالسعرُ والتغطيةُ محسوبان بما **قِيس** فعلًا. **وبلا حقل الردود** (ملفّاتٌ أقدم) تُستعمل أرضيةُ
    «أثرُه + ١» **وتُعلَن أرضيةً**: النداءاتُ الوسيطةُ بلا أداةٍ لا تُسجَّل ⇒ فالكلفةُ المتوقَّعةُ أدنى
    من الواقع **والتغطيةُ متفائلةٌ بالنسبة نفسِها** — فالإعلانُ يمنع قراءةَ الأرضية كعدد.
    """
    d = json.loads(path.read_text())
    rows = [r for r in d.get("results", []) if r.get("id")]
    if rows and all("replies_observed" in r for r in rows):
        return {r["id"]: max(1, int(r["replies_observed"])) for r in rows}, "observed-replies"
    return {r["id"]: len(r.get("tools_used") or []) + 1 for r in rows}, "floor-tools-plus-one"


def simulate(questions: list[dict], *, cap: float, price_per_call: float,
             calls_by_id: dict[str, int] | None = None, default_calls: int = 2) -> dict:
    """إعادةُ تشغيل القانون بلا كلفة: أين يقف، وما التغطيةُ، وما الصرفُ المتوقَّع.

    **والنمطُ مطابقٌ للحلقة بعد R117-4:** القرارُ = `cap_verdict(spent, cap)` **وحدَه** — لا حجزَ
    استباقيًّا بسقف السؤال القادم (أُزيل: كان يعيد صنعَ ما يقدّمه المزوّد)، والصرفُ يتراكم بكلفة
    كلّ سؤال ⇒ فيتوقّف القانونُ عند **بلوغ المُنفَق السقف** قبل السؤال التالي.
    """
    calls_by_id = calls_by_id or {}
    spent = 0.0
    for i, q in enumerate(questions, 1):
        verdict = cap_verdict(spent, cap)
        if verdict == "at-cap":
            return {"stopped_before": i, "coverage": i - 1, "spent": round(spent, 6),
                    "cap": cap, "price_per_call": price_per_call,
                    "verdict": verdict, "stopped_at": q["id"],
                    "widest_ceiling": max(question_ceiling(x["q"]) for x in questions)}
        calls = max(1, int(calls_by_id.get(q["id"], default_calls)))
        spent += calls * price_per_call
    return {"stopped_before": None, "coverage": len(questions), "spent": round(spent, 6),
            "cap": cap, "price_per_call": price_per_call,
            "verdict": "covered", "stopped_at": None,
            "widest_ceiling": max(question_ceiling(x["q"]) for x in questions)}


def check_cap_can_carry(questions: list[dict], *, cap: float, price_per_call: float,
                        margin: float = PER_CALL_MARGIN) -> str | None:
    """**هل يستطيع هذا السقفُ أن يحمل أوسعَ سؤال؟** — إن لا، فلا سؤالَ يمرّ أصلًا.

    سقفُ أوسعِ سؤال = حدُّ نداءاته × سعرِ النداء × الهامش؛ فإن كان أكبرَ من السقف الماليّ **فالبوّابةُ
    لا تستطيع أن تمرّ** — وهي مسرحٌ تمامًا كبوّابةٍ لا تفشل (الخيارُ «د» في مراجعة ١١٢).
    """
    widest = max(question_ceiling(q["q"]) for q in questions)
    needed = widest * price_per_call * margin
    if needed > cap:
        return (f"⛔ سقفُ أوسعِ سؤال (${needed:.4f} = حدُّ {widest} نداءً × ${price_per_call:.6f} × "
                f"هامش {margin}) أكبرُ من السقف الماليّ (${cap:.4f}) ⇒ **لا سؤالَ يمرّ بعد أوّل مشاهدة** "
                f"⇒ لا يُشترى بهذا السقف شيء.")
    return None


def smallest_cap_for(questions: list[dict], *, price_per_call: float,
                     calls_by_id: dict[str, int] | None = None, default_calls: int = 2) -> float:
    """أصغرُ سقفٍ يغطّي الحزمةَ كاملة — بالبحث لا بالتقدير (والدالّةُ رتيبةٌ في السقف)."""
    lo = price_per_call
    hi = max(1.0, price_per_call * 100)
    while hi - lo > 1e-6:
        mid = (lo + hi) / 2
        if simulate(questions, cap=mid, price_per_call=price_per_call, calls_by_id=calls_by_id,
                    default_calls=default_calls)["coverage"] == len(questions):
            hi = mid
        else:
            lo = mid
    return round(hi, 6)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="التغطيةُ المتوقَّعة للخمسين تحت سقفٍ وسعرِ نداء (بلا كلفة)")
    ap.add_argument("--cap", type=float, required=True, help="السقفُ الماليّ بالدولار")
    ap.add_argument("--price-per-call", type=float, required=True,
                    help="سعرُ النداء المشهود (من الجولة السابقة: المُنفَق ÷ النداءات)")
    ap.add_argument("--from-answers", type=pathlib.Path,
                    help="ملفُّ أجوبةٍ محفوظ ⇒ أرضيةُ النداءات لكلّ سؤال (أثرُه + ١)")
    ap.add_argument("--default-calls", type=int, default=2,
                    help="نداءاتُ سؤالٍ بلا سجلّ (أرضيةٌ مُعلَنة)")
    ap.add_argument("--questions", type=pathlib.Path, default=QUESTIONS)
    a = ap.parse_args(argv)

    qs = json.loads(a.questions.read_text())["questions"]
    calls: dict[str, int] = {}
    src = "بلا سجلّ"
    if a.from_answers:
        calls, src = calls_from_answers(a.from_answers)
    sim = simulate(qs, cap=a.cap, price_per_call=a.price_per_call, calls_by_id=calls,
                   default_calls=a.default_calls)
    gate = check_cap_can_carry(qs, cap=a.cap, price_per_call=a.price_per_call)

    print(f"الأسئلة: {len(qs)} · السقف: ${a.cap:.4f} · سعرُ النداء: ${a.price_per_call:.6f}"
          f" · الهامش: {PER_CALL_MARGIN}")
    print(f"مصدرُ النداءات: {src} ({a.from_answers}) " if a.from_answers else
          f"مصدرُ النداءات: {src} (افتراضٌ مُعلَن: {a.default_calls} نداءً)")
    if src == "floor-tools-plus-one":
        print("⚠️ الملفُّ لا يحمل `replies_observed` ⇒ النداءاتُ **أرضيةٌ** (أثرُه + ١) لا عددًا: "
              "فالكلفةُ أدنى من الواقع والتغطيةُ متفائلةٌ بالنسبة نفسِها (R113-1).")
    print(f"**التغطيةُ المتوقَّعة: {sim['coverage']} من {len(qs)}**"
          + (f" · التوقّفُ قبل السؤال {sim['stopped_before']} ({sim['stopped_at']})"
             f" بحكم «{sim['verdict']}» عند مُنفَقٍ ${sim['spent']:.4f}"
             if sim["stopped_before"] else " · ولا توقّف"))
    print(f"الصرفُ المتوقَّع: ${sim['spent']:.4f} من ${a.cap:.4f}")
    print(f"أوسعُ سؤال: {sim['widest_ceiling']} نداءً")
    print(f"أصغرُ سقفٍ يغطّي الحزمة: ${smallest_cap_for(qs, price_per_call=a.price_per_call, calls_by_id=calls, default_calls=a.default_calls):.4f}")
    if gate:
        print(gate)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
