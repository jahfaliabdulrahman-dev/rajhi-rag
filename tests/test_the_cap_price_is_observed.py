"""**R112-1/R112-2 — سعرُ النداء الذي يقرّر به الحاجزُ يُشاهَد من الرموز، ولا يُستنتَج من رصيد حساب.**

**العطبُ المقيس (مراجعة ١١٢ · قياسُ REQ-108-02):** الحاجزُ بنى «سعرَ النداء» من رصيد حساب المزوّد
بعد كلّ سؤال؛ والرصيدُ يتحرّك **متأخّرًا وعلى دفعات**: ١٢ نافذةً من ١٣ رأت **صفرًا**، ثمّ كتلةٌ واحدة
($0.006732) نُسبت إلى سؤالٍ بأداةٍ واحدة ⇒ `0.006732 ÷ 2 × 36 × 1.5 = $0.18176` — **أكبرُ من السقف
كلِّه** ($0.10) ⇒ توقّفٌ عند ١٣ من ٥٠ وصرفُ ١٧.٧٪ فقط. **و٦٠٪ من الصرف وقع خارج نوافذ الأسئلة**
(مجموعُ كلفات الأسئلة المسجَّلة 0.006732 مقابل مُنفَقٍ 0.0170 عند القرار).

**والقاعدة (ثوابتُ مراجعة ١١٢):** العددُ من **البنية** (`question_ceiling`) · والسعرُ **مُشاهَدٌ**
لحظةَ القرار من `usage_metadata` لكلّ ردّ × **سعرِ الرمز المنشور** (قائمةُ النماذج العامّة، بلا مفتاح) ·
والهامشُ بسببٍ مكتوب. **ورصيدُ المزوّد يبقى الحَكَمَ على مجموع الجولة** (قبلها، وبعد الخروج بثلاث
دقائق)، **لا على سعر النداء**.

**ونصفا الضابط:** النصفُ الأوّلُ يعمل في أيّ بيئة — دوالُّ خالصةٌ على مدخلاتٍ مصنوعةٍ من أرقام
الواقعة، بلا شبكةٍ ولا `langchain` ثقيل. والنصفُ الثاني يقرأ **الوصلَ** في الملفّ: الحلقةُ تُغذّي
القانونَ بالمشاهدة لا بالعدّاد، وتُسجّل ما حوكم به ⇒ فالمقياسُ لا يُدَّعى بلا وصل.

**والبوّابةُ التنفيذيّةُ لهذا البند هي `tools/expected_coverage.py`** (R112-2 · صفُّ ١٩ في `docs/GATES.md`):
يُعيد تشغيل القانون نفسِه بلا كلفة ويطبع التغطيةَ، **ويرفض** سقفًا لا يحمل أوسعَ سؤال — وهذا الملفُّ
هو ضابطُه (يقيس `simulate` و`check_cap_can_carry` على الحزمة الحقيقيّة).
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(ROOT))
EVAL = ROOT / "tools" / "eval_questions.py"

#: أرقامُ الواقعة كما قِيست في REQ-108-02 (‏`answers-r108-02.json` وسجلُّ التشغيل).
#: **(كلفةُ النافذة من الرموز, عددُ الردود المشهودة)** — والثاني كان «أدواتُ الأثر» قبل R113-1،
#: وقد صار **الردود**: نافذةُ الكتلة $0.006732 كانت **ردّين** (سؤال بأداةٍ واحدة = نداءُ أداةٍ + نداءُ
#: جواب) ⇒ فالسعرُ نفسه `0.006732 ÷ 2 = $0.003366` — والواقعةُ أُعيد إنتاجُها بالقسمة الصحيحة.
MEASURED_WINDOWS = [(0.0, 1)] * 12 + [(0.006732, 2)]
MEASURED_SPENT_BEFORE_14 = 0.0170
MEASURED_CAP = 0.10
SIMPLE = "ما عددُ الحركات في الصفحة ١٢؟"
COMPOUND = "ما عددُ الحركات في الصفحة ١٢ وما مجموعُ مدين الصفحة ١٣؟"

#: سعرُ الرمز المنشور لـ`z-ai/glm-5.3-flash` (مراجعة ١١٢ · قائمةُ النماذج العامّة بلا مفتاح).
PRICE_IN_PER_M = 0.0351
PRICE_OUT_PER_M = 0.90


def _eval_module():
    """الوحدةُ كما تستوردها الحلقة — بلا استيرادِ `langchain` على مستوى الوحدة."""
    from tools import eval_questions

    return eval_questions


# ── ① السعرُ يُشاهَد من الرموز (لا من رصيدٍ متأخّر) ──────────────────────────────────────────
def test_a_window_carries_its_own_tokens_by_the_published_price():
    """**نافذةٌ واحدة = نافذةٌ مشهودة:** الرموزُ من فرق `usage_metadata`، والسعرُ من الرمز المنشور."""
    m = _eval_module()
    before = {"z-ai/glm-5.3-flash": {"input_tokens": 0, "output_tokens": 0}}
    after = {"z-ai/glm-5.3-flash": {"input_tokens": 5200, "output_tokens": 240}}

    cost, tin, tout = m.tokens_cost(m.usage_delta(before, after), PRICE_IN_PER_M, PRICE_OUT_PER_M)
    assert (tin, tout) == (5200, 240), "الفرقُ لا يُقرأ من الرموز المتراكمة"
    assert cost == pytest.approx((5200 * PRICE_IN_PER_M + 240 * PRICE_OUT_PER_M) / 1e6)

    obs = m.observation(before, after, 1, PRICE_IN_PER_M, PRICE_OUT_PER_M)
    assert obs is not None and obs[1] == 1, "النافذةُ لا تُنتج مشاهدةً (كلفة, ردود)"
    assert obs[0] == pytest.approx(cost)
    # **والردودُ هي المقسومُ عليها (R113-1):** نافذةٌ بخمسةِ ردودٍ تُسعَّر بكلفتها ÷ 5 لا ÷ أرضية
    five = m.observation(before, after, 5, PRICE_IN_PER_M, PRICE_OUT_PER_M)
    assert m.per_call_cost([five]) == pytest.approx(cost / 5)
    assert m.per_call_cost([five]) < m.per_call_cost([obs])


def test_the_ceiling_is_positive_from_the_second_question_at_the_latest():
    """**القبولُ المنصوص:** بسعرٍ مشهودٍ يصير سقفُ السؤال التالي موجبًا — لا صفرًا كما قِيس."""
    m = _eval_module()
    obs = m.observation({"x": {"input_tokens": 0, "output_tokens": 0}},
                        {"x": {"input_tokens": 5200, "output_tokens": 240}},
                        1, PRICE_IN_PER_M, PRICE_OUT_PER_M)
    bound = m.next_question_ceiling(SIMPLE, [obs])
    from statement_qa.qa import question_ceiling

    assert bound > 0, "سقفٌ صفرٌ بعد نافذةٍ مشهودة ⇒ الحاجزُ ما زال أعمى"
    assert bound == pytest.approx(m.per_call_cost([obs]) * question_ceiling(SIMPLE) * m.PER_CALL_MARGIN)
    # وبلا مشاهدةٍ يبقى الحدُّ المُعلَن: صفر (لا سندَ يُضرب) — لم يتغيّر
    assert m.next_question_ceiling(SIMPLE, []) == 0.0


def test_a_window_without_tokens_is_not_recorded_as_a_zero_price():
    """**لا يُخترع عدد:** نافذةٌ لم تتحرّك رموزُها لا تُنتج مشاهدة (لا صفرًا يُنسب لها).

    و`before=None` تعني «منذ البداية» (**قراءةٌ مُعلَنةٌ للتراكم**، وهي نافذةُ السؤال الأوّل) — ولا تعني
    «صفرَ رموز»؛ فالصفرُ سعرٌ يُقبل ويُعمي الحاجز، وهو عينُ ما وقع اثنتَي عشرةَ مرّة.
    """
    m = _eval_module()
    same = {"x": {"input_tokens": 10, "output_tokens": 10}}
    assert m.observation(same, same, 1, 1.0, 1.0) is None
    assert m.observation({}, {"x": {"input_tokens": 0, "output_tokens": 0}}, 1, 1.0, 1.0) is None
    first = m.observation(None, same, 1, 1.0, 1.0)
    assert first is not None and first[0] == pytest.approx(2e-05), "النافذةُ الأولى من البداية لا صفرًا"
    # **ونافذةٌ أنفقت ولم يُعرف عددُ ردودها لا تُنتج سعرًا (R113-1):** تُسقَط من العيّنة، ولا يُخترع
    # لها مقسومٌ (وهو عينُ ما كان يفعل «الأدوات + ١» ⇒ سعرٌ منفوخ ⇒ سقفٌ يقفز ⇒ توقّفُ الجولة).
    assert m.observation(None, same, 0, 1.0, 1.0) is None, "نافذةٌ بلا ردودٍ مشهودة أنتجت سعرًا"


# ── ② العطبُ يُعاد إنتاجه بالأرقام المقيسة (فلا يُغلق بادّعاء) ────────────────────────────────
def test_the_measured_meter_windows_reproduce_an_eighteen_cent_bound():
    """**بالعدّاد وحدَه:** الكتلةُ على سؤالٍ بأداةٍ واحدة ⇒ `0.003366 × 36 × 1.5 = $0.18176`."""
    m = _eval_module()
    assert m.per_call_cost(MEASURED_WINDOWS) == pytest.approx(0.003366, abs=5e-7)
    bound = m.next_question_ceiling(SIMPLE, MEASURED_WINDOWS)
    assert bound == pytest.approx(0.18176, abs=5e-4)
    assert bound > MEASURED_CAP, "السقفُ ما زال قابلًا للمرور ⇒ الواقعةُ لم تُعَد إنتاجها"
    assert m.cap_verdict(MEASURED_SPENT_BEFORE_14, MEASURED_CAP, bound) == "anticipatory"


# ── ③ التغطيةُ محسوبةٌ قبل الصرف (R112-2) ────────────────────────────────────────────────────
def _questions_texts() -> list[dict]:
    import json

    spec = json.loads((ROOT / "docs" / "eval_pack" / "questions.json").read_text())
    return spec["questions"]


def test_the_fifty_does_not_stop_at_fourteen_when_the_price_is_observed():
    """**القبولُ المنصوص:** بسعرٍ مشهود وبسقف المالك ($0.15) تُغطّي الجولةُ ٥٠/٥٠،
    وبسقف العشرة لا تتوقّف عند ١٤ (وهو ما توقّف عنده العدّاد)."""
    from tools import expected_coverage as ec

    price = 0.000633      # المُنفَق المستقرّ ($0.01772722) ÷ ٢٨ نداءً على الأقلّ — سعرُ الجولة المقيس
    qs = _questions_texts()

    at_15 = ec.simulate(qs, cap=0.15, price_per_call=price)
    assert at_15["coverage"] == len(qs), at_15
    at_10 = ec.simulate(qs, cap=0.10, price_per_call=price)
    assert at_10["stopped_before"] > 14, f"توقّفَ عند ١٤ أو قبله: {at_10}"


def test_the_coverage_tool_refuses_a_cap_that_cannot_carry_the_widest_question():
    """**بوّابةٌ لا تمرّ مسرحٌ** (الخيار د): سقفٌ أصغر من سقف أوسع سؤال لا يُشترى به شيء."""
    from tools import expected_coverage as ec

    qs = _questions_texts()
    widest = max(qs, key=lambda q: ec.question_ceiling(q["q"]))
    needed = ec.question_ceiling(widest["q"]) * 0.000633 * ec.PER_CALL_MARGIN
    assert ec.check_cap_can_carry(qs, cap=needed * 0.9, price_per_call=0.000633) is not None
    assert ec.check_cap_can_carry(qs, cap=needed * 1.1, price_per_call=0.000633) is None


# ── ④ الدليلُ يحمل ما حُوكم به (R112-4) ─────────────────────────────────────────────────────
def test_the_evidence_carries_the_price_the_law_used_and_the_spend_before_it():
    m = _eval_module()
    ev = m.cap_evidence(spent_before=0.0170, spent_after=0.0237, cost_here=0.006732, bound=0.18176,
                        price=0.003366, source="observed-tokens", meter_delta=0.006732,
                        tokens=0, tools=1, replies=2)
    assert ev["cap_price_usd"] == pytest.approx(0.003366)
    assert ev["cap_price_source"] == "observed-tokens"
    assert ev["spent_before_usd"] == pytest.approx(0.0170)
    assert ev["spent_after_usd"] == pytest.approx(0.0237)
    assert ev["cost_by_tokens_usd"] == pytest.approx(0.006732)
    assert ev["meter_delta_usd"] == pytest.approx(0.006732)
    assert ev["cap_bound_usd"] == pytest.approx(0.18176)
    # **والمقسومُ يُنشر معه (R113-1):** الردودُ المشهودة عددًا، والأرضيةُ **مُعلَنةً** لا مقسومًا عليها
    assert ev["replies_observed"] == 2 and ev["calls_floor"] == 2
    assert ev["tools_in_trace"] == 1
    assert "next_ceiling_usd" not in ev, "الحقلُ المكرَّرُ بالاسم المضلِّل عاد"


def test_the_loop_reads_the_observed_price_and_records_it():
    """**توصيلٌ لا تعريف (بالـAST):** الحلقةُ تنادي القانونَ، والحقلان الجديدان مكتوبان،
    والاستيرادُ الثقيلُ داخلَ الدالّة (فالوحدةُ تُستورَد في البيئة الخفيفة)."""
    text = EVAL.read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(text).body
              if isinstance(n, ast.FunctionDef) and n.name == "run_questions")
    called = {getattr(c.func, "id", "") for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert {"next_question_ceiling", "cap_verdict", "observation", "cap_evidence"} <= called, sorted(called)
    # والاستيرادُ الثقيلُ ليس على مستوى الوحدة (يُقاس: أوّلُ 120 سطرًا بلا langchain)
    head = "\n".join(text.splitlines()[:120])
    assert "langchain_core" not in head, "استيرادٌ ثقيلٌ على مستوى الوحدة ⇒ البيئةُ الخفيفةُ تسقط"


def test_finish_reasons_are_read_from_the_response_and_never_fabricated():
    """**القطعُ يُقرأ من بيانات الردّ** (مراجعة ١١٢) — ولا يُخترع حين لا يُبلّغ المزوّد."""
    m = _eval_module()

    class _Gen:
        def __init__(self, info):
            self.generation_info = info

    class _Resp:
        def __init__(self, gens, out=None):
            self.generations = gens
            self.llm_output = out or {}

    assert m.finish_reasons_from(_Resp([[_Gen({"finish_reason": "stop"})],
                                        [_Gen({"finish_reason": "length"})]])) == ["stop", "length"]
    assert m.finish_reasons_from(_Resp([[_Gen(None)]])) == []
    assert m.finish_reasons_from(object()) == [], "ردٌّ بلا بيانات ⇒ صفرُ أسبابٍ لا سببٌ مخترع"


# ── ⑤ الثابتُ الثالث: الردودُ تُقرأ متى حملها الملفّ، والأرضيةُ تُعلَن حين لا يحملها (R113-1) ────────
def test_the_coverage_tool_reads_replies_when_the_file_has_them_and_declares_a_floor_when_not(tmp_path):
    """**الثابتُ الثالثُ في مراجعة ١١٣:** أداةُ التغطية تقرأ **عددَ الردود المسجَّل** متى حمله ملفُّ
    الأجوبة (من ملفّ هذه الجولة فصاعدًا)، **وتُعلن الأرضيةَ** حين لا يحمله — والأرضيةُ **أدنى من
    العدد** ⇒ فالتغطيةُ المحسوبةُ بها متفائلة، والإعلانُ يمنع قراءةَ الأرضية عددًا.

    والمقيسُ **المصدرُ المُعلَنُ نفسُه** (`observed-replies` / `floor-tools-plus-one`) لا رقمٌ في نثر.
    """
    import json

    from tools import expected_coverage as ec

    with_replies = {"results": [{"id": "q1", "tools_used": ["a"], "replies_observed": 7},
                                {"id": "q2", "tools_used": ["a", "b"], "replies_observed": 3}]}
    floor_only = {"results": [{"id": "q1", "tools_used": ["a"]},
                              {"id": "q2", "tools_used": ["a", "b"]}]}
    p1, p2 = tmp_path / "with.json", tmp_path / "without.json"
    p1.write_text(json.dumps(with_replies), encoding="utf-8")
    p2.write_text(json.dumps(floor_only), encoding="utf-8")

    calls1, src1 = ec.calls_from_answers(p1)
    calls2, src2 = ec.calls_from_answers(p2)
    assert (src1, calls1) == ("observed-replies", {"q1": 7, "q2": 3}), (src1, calls1)
    assert (src2, calls2) == ("floor-tools-plus-one", {"q1": 2, "q2": 3}), (src2, calls2)
    assert calls2["q1"] < calls1["q1"], "الأرضيةُ ليست أدنى من العدد ⇒ فالفرضُ عن الأرضية خاطئ"
