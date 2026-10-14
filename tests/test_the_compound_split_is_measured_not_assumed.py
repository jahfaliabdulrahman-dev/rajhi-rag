"""**R105-5 — تقسيمُ السؤال المركّب: يُقاس بلا كلفةٍ أوّلًا، ثمّ يُحذف أو يُمرَّر النصفُ الأول سياقًا.**

**القياسُ وقع (٢٠٢٦-١٠-١٤ · $0 · بلا نداءِ نموذج):** من الحزمة (`docs/eval_pack/questions.json`)
والجولة المحفوظة الأخيرة (`answers-r108-03.json`) ومن الأثر المحفوظ لكلّ سؤال:

| الوجه | المقيس |
| :--- | :--- |
| الأسئلةُ المفصولة | **٥ من ٥٠** (`chn-01..04` · `cit-02`) — والباقي لا يُمَسّ |
| صوابُها في تلك الجولة | **٥/٥** (وأربعتُها يشترط مصحِّحُها النصفَين معًا) |
| ما أسند النصفَ الثاني | كلُّ سؤالِ سلسلةٍ استدعى `page_rows` **مرّتين** (نداءً لكلّ نصف) |
| ثمنُه | الردودُ المشهودة ٣ · ٣ · ٣ · ٣ · ٦ (وسيط ٣) مقابل وسيط ٢ وأقصى ٢ للمفردة ⇒ **+٨ ردود** |

**والنتيجةُ المعلَنة:** لا حذفَ ولا استبدالَ في هذه الجولة — لأنّ **الحذفَ و«تمرير النصف الأول
سياقًا» تغييران في المسار المقيس** لا يقرّرهما قياسٌ بلا كلفة، ويُقاسان بتجربة ذراعين مدفوعة
(~٢ سنت) مسجَّلةً بندًا تاليًا. **وهذا الضابطُ يحرس الأمرين:** نطاقَ الفصل كما قِيس، وأنّ القرارَ
المؤجَّل مكتوبٌ في موضعه لا مُضمَر.
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from statement_qa.qa import split_compound  # noqa: E402

PACK = ROOT / "docs" / "eval_pack" / "questions.json"
RUN = pathlib.Path.home() / "Projects" / "rajhi-rag" / "data" / "eval_pack" / "answers-r108-03.json"
MEASURED_COMPOUND = ("chn-01", "chn-02", "chn-03", "chn-04", "cit-02")


def _pack() -> list[dict]:
    return json.loads(PACK.read_text(encoding="utf-8"))["questions"]


def _run_by_id() -> dict[str, dict] | None:
    try:
        return {r["id"]: r for r in json.loads(RUN.read_text(encoding="utf-8"))["results"]}
    except (OSError, ValueError, KeyError):
        return None


# ── ① نطاقُ الفصل كما قِيس (لا أوسع ولا أضيق) ────────────────────────────────────────────
def test_the_pack_has_exactly_the_five_measured_compound_questions():
    qs = _pack()
    split = [q["id"] for q in qs if len(split_compound(q["q"])) > 1]
    assert tuple(split) == MEASURED_COMPOUND, (
        f"نطاقُ الفصل تغيّر: {split} — كان {list(MEASURED_COMPOUND)} (R105-5)")


def test_the_second_half_is_the_part_that_was_lost_alone():
    """النصفُ الثاني في عائلة السلسلة هو «ما الفرق؟» — وهو ما كان يُسقَط قبل الفصل."""
    for q in _pack():
        if q["id"] in ("chn-01", "chn-02", "chn-03", "chn-04"):
            parts = split_compound(q["q"])
            assert len(parts) == 2, f"{q['id']}: {parts}"
            assert "الفرق" in parts[1], f"{q['id']}: النصفُ الثاني ليس سؤالَ الفرق: {parts[1]}"


def test_a_single_question_is_never_split():
    """**نقيضٌ في الضابط نفسه:** الفصلُ الزائد يقصّ سؤالًا سليمًا نصفين — وهو أسوأُ من العطب."""
    for q in _pack():
        if q["id"] in ("abs-01", "abs-02", "abs-09", "cit-03", "cit-08", "num-01"):
            assert len(split_compound(q["q"])) == 1, f"{q['id']} قُصَّ وهو سؤالٌ واحد"
    # والعطفُ داخل الفلتر ليس سؤالين (الحالةُ التي بُني عليها شرطُ «كلمةُ استفهام في كلّ شقّ»)
    assert len(split_compound("ما مجموع الحركات المدينة والدائنة في الصفحة ٥٢؟")) == 1


# ── ② القياسُ يُعاد إنتاجُه من الأدلّة المحفوظة بلا كلفة ─────────────────────────────────
def test_the_zero_cost_measurement_is_reproducible():
    """**يُعاد تشغيلُه من الملفّ لا يُقتبس من التقرير** — والبياناتُ محليّةٌ فقط ⇒ يُعلَن التخطّي."""
    rec = _run_by_id()
    if rec is None:
        pytest.skip("لا جولةَ محفوظة في هذا الشجر (بياناتُ المالك لا تصل الـCI) — يُقاس عليه فقط")
    qs = {q["id"]: q for q in _pack()}
    compound = [i for i in MEASURED_COMPOUND if i in rec]
    assert compound == list(MEASURED_COMPOUND), f"سجلٌّ ناقص: {compound}"
    replies_c, replies_s = [], []
    for qid, r in rec.items():
        if r.get("replies_observed") is None:
            continue
        parts = len(split_compound(qs[qid]["q"])) if qid in qs else 1
        (replies_c if parts > 1 else replies_s).append(r["replies_observed"])
    assert sum(1 for i in MEASURED_COMPOUND if rec[i].get("ok")) == 5, "الخمسةُ ليست كلُّها صحيحة"
    for qid in ("chn-01", "chn-02", "chn-03", "chn-04"):
        tools = list(rec[qid].get("tools_used") or [])
        assert tools.count("page_rows") == 2, (
            f"{qid}: الأثرُ لا يشهد نداءً لكلّ نصف: {tools} — فالفصلُ لم يُسند النصفَ الثاني")
    assert statistics.median(replies_c) == 3 and statistics.median(replies_s) == 2, (
        f"ثمنُ الفصل تغيّر: المفصولة {replies_c} · المفردة {sorted(set(replies_s))}")


# ── ③ القرارُ المؤجَّل مكتوبٌ في موضعه لا مُضمَر ─────────────────────────────────────────
def test_the_deferred_decision_is_recorded_where_the_code_lives():
    qa = (ROOT / "src" / "statement_qa" / "qa.py").read_text(encoding="utf-8")
    doc = qa.split("def split_compound")[1][:2600]
    assert "تجربة ذراعين مدفوعة" in doc, "القرارُ المؤجَّل (الذراعُ المدفوع) غيرُ مكتوبٍ في موضعه"
    assert "لا يُحذف" in doc, "الحذفُ صار مسموحًا بلا قياس ⇒ القيدُ ضاع"
    # **والآليّةُ باقية:** موضعا النداء (السؤال المركّب في `answer_question`، وسقفُ السؤال)
    assert qa.count("split_compound(") >= 3, "الفصلُ نُزع من موضعٍ ⇒ يُقاس قبل الحذف لا بعده"
