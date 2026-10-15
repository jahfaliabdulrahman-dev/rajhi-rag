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
    """**نافذةٌ واحدة = ردٌّ مشهود:** الرموزُ من بيانات الردّ، والسعرُ من الرمز المنشور — **والحاكمُ
    كلفةُ الردود المحاسَبة** (`billed_window` · R115-1) لا `رموز × قائمة`.
    """
    m = _eval_module()
    # ردٌّ يحمل `cost` المزوّد ⇒ **يُؤخذ كما هو** (R122-1: المُحاسَبُ لا يتجاوز ما يُحاسِب به المزوّد).
    win = m.billed_window([(5200, 240, 0.0009)], PRICE_IN_PER_M, PRICE_OUT_PER_M, (0.225, 1.60))
    assert win is not None, "ردٌّ مشهود بلا كلفة"
    cost, src, replies = win
    assert replies == 1 and src == "provider-cost", win
    assert cost == pytest.approx(0.0009), cost
    # وبلا `cost`: رموزُه × **حدِّ الطلب** (لا سعرَ القائمة ولا أعلى سعرِ مضيف) — R122-1:
    win2 = m.billed_window([(5200, 240, None)], PRICE_IN_PER_M, PRICE_OUT_PER_M, (0.225, 1.60))
    # **وتغيّر اسمُ المرتبة مع تغيّر ما يحكم (R122-1):** بلا `cost` يحكم **حدُّ الطلب** لا أعلى
    # سعرِ مضيف ⇒ والاسمُ يتبع الحاكم (`provider-max-price`)، وأعلى سعرِ المضيف شاهدٌ يُطبع.
    assert win2[1] == "provider-max-price", win2
    # **والمُقارَنُ الآن هو السعرُ المُمرَّر (حدُّ الطلب) بحرفه** — لا «أعلى المضيف» ولا القائمة
    assert win2[0] == pytest.approx((5200 * PRICE_IN_PER_M + 240 * PRICE_OUT_PER_M) / 1e6), win2
    # والقائمةُ وحدَها **حدٌّ أدنى** (٤٢ مقابل ٦٧٫٥ سنتًا في القياس الحقيقيّ): تُنشر للمساءلة لا للسقف
    assert m.tokens_cost({"x": {"input_tokens": 5200, "output_tokens": 240}},
                         PRICE_IN_PER_M, PRICE_OUT_PER_M)[0] == pytest.approx(
        (5200 * PRICE_IN_PER_M + 240 * PRICE_OUT_PER_M) / 1e6)

def test_the_price_is_positive_and_the_advisory_ceiling_is_not_a_verdict():
    """**القبولُ المنصوص:** بسعرٍ مشهودٍ يصير سعرُ النداء موجبًا (لا صفرًا كما قِيس)،
    و**سقفُ السؤال البنيويُّ رقمٌ استشاريّ لا حكم** (أُزيل الفرعُ الاستباقيُّ في R117-4)."""
    m = _eval_module()
    w = m.billed_window([(5200, 240, 0.0009)], PRICE_IN_PER_M, PRICE_OUT_PER_M, (0.225, 1.60))
    obs = (w[0], w[2])                     # (كلفةٌ محاسَبة, ردودٌ) — المقسومُ عليه في `per_call_cost`
    from statement_qa.qa import question_ceiling

    assert m.per_call_cost([obs]) > 0, "سعرٌ صفرٌ بعد نافذةٍ مشهودة ⇒ الحاجزُ ما زال أعمى"
    advisory = m.per_call_cost([obs]) * question_ceiling(SIMPLE) * m.PER_CALL_MARGIN
    assert advisory > 0
    # **والنقيض:** مُنفَقٌ دون السقف ⇒ «go» ولو كان الرقمُ الاستشاريُّ فوقه (لا حجزَ استباقيًّا)
    assert m.cap_verdict(0.01, 0.02) == "go"
    # وبلا مشاهدةٍ يبقى الحدُّ المُعلَن: صفر (لا سندَ يُضرب) — لم يتغيّر
    assert m.per_call_cost([]) == 0.0


def test_a_window_without_tokens_is_not_recorded_as_a_zero_price():
    """**لا يُخترع عدد:** نافذةٌ بلا ردودٍ **لا تُنتج سعرًا** (‏`None`) — ولا صفرًا يُنسب لها.

    (R113-1 · ومُثبَّتةٌ في R115-1) و`None` تعني «لا كلفةَ تُدَّعى»، فالصفرُ سعرٌ يُقبل ويُعمي الحاجز
    — وقد فعله اثنتَي عشرةَ مرّة. **والردُّ بلا `cost` ومع قائمة مضيفين يُسعَّر بأعلاها مُعلَنًا**
    (‏`host-max-price`) **لا صفرًا**؛ **وبلا قائمةٍ أصلًا ⇒ `None`** (فلا سعرَ يُخترع).
    """
    m = _eval_module()
    assert m.billed_window([], PRICE_IN_PER_M, PRICE_OUT_PER_M, (0.225, 1.60)) is None
    assert m.billed_reply_cost(0, 0, None, PRICE_IN_PER_M, PRICE_OUT_PER_M, None) is None
    # والقائمةُ وحدَها ليست حدًّا: **الرتبةُ تُسمّى**، ومع صفرِ رموزٍ لا كلفةَ تُدَّعى بلا سعر مضيف
    assert m.billed_reply_cost(0, 0, None, PRICE_IN_PER_M, PRICE_OUT_PER_M, (0.225, 1.60))[0] == 0.0
    got = m.billed_reply_cost(5200, 240, None, PRICE_IN_PER_M, PRICE_OUT_PER_M, (0.225, 1.60))
    assert got[1] == "provider-max-price" and got[0] > 0   # ← الاسمُ يتبع الحاكم (R122-1)


# ── ② العطبُ يُعاد إنتاجه بالأرقام المقيسة (فلا يُغلق بادّعاء) ────────────────────────────────
def test_the_measured_meter_windows_reproduce_the_price_the_old_reservation_used():
    """**الواقعةُ بأرقامها:** الكتلةُ على سؤالٍ بأداةٍ واحدة ⇒ `per_call = 0.003366`، وحدُّ السؤال
    البنيويُّ ٣٦ نداءً × الهامش = **$0.18176 أكبرُ من السقف كلِّه** — وهو الرقمُ الذي كان يُوقف
    الجولةَ في الحجز الاستباقيّ. **ولم يبقَ له حكم:** `cap_verdict` تُقرأ بالمُنفَق المحاسَب وحدَه
    ⇒ فمُنفَقُ ١٫٧ سنت مقابل سقف ١٠ سنتات ⇒ **«go»**، ولا يُحجز استباقيًّا (R117-4).
    """
    m = _eval_module()
    assert m.per_call_cost(MEASURED_WINDOWS) == pytest.approx(0.003366, abs=5e-7)
    advisory = m.per_call_cost(MEASURED_WINDOWS) * 36 * m.PER_CALL_MARGIN
    assert advisory == pytest.approx(0.18176, abs=5e-4)
    assert advisory > MEASURED_CAP, "السقفُ ما زال قابلًا للمرور ⇒ الواقعةُ لم تُعَد إنتاجها"
    assert m.cap_verdict(MEASURED_SPENT_BEFORE_14, MEASURED_CAP) == "go", \
        "الرقمُ الاستشاريُّ يحكم من جديد ⇒ الحجزُ الاستباقيُّ عاد (R117-4)"


# ── ③ التغطيةُ محسوبةٌ قبل الصرف (R112-2) ────────────────────────────────────────────────────
def _questions_texts() -> list[dict]:
    import json

    spec = json.loads((ROOT / "docs" / "eval_pack" / "questions.json").read_text())
    return spec["questions"]


def test_the_coverage_tool_mirrors_the_law_it_predicts():
    """**أداةُ التغطية تُعيد تشغيل القانون نفسِه:** بسقف العشرة تُغطّى الحزمةُ كاملةً الآن
    (مجموعُ الصرف المقيس $0.0675 < $0.10)، وبسقفٍ أدنى من مجموعها **يتوقّف العملُ عند المُنفَق
    المُحاسَب** لا عند تقدير — ولا حجزَ استباقيًّا (R117-4 · مراجعة ١١٧).
    """
    from tools import expected_coverage as ec

    price = 0.000633      # سعرُ النداء المشهود (المُنفَق المستقرّ ÷ نداءاته — R112-1)
    qs = _questions_texts()

    at_15 = ec.simulate(qs, cap=0.15, price_per_call=price)
    assert at_15["coverage"] == len(qs), at_15
    at_10 = ec.simulate(qs, cap=0.10, price_per_call=price)
    assert at_10["coverage"] == len(qs), f"السقفُ توقّف بلا أن يبلغه الصرفُ: {at_10}"
    low = ec.simulate(qs, cap=0.02, price_per_call=price)
    assert low["stopped_before"] and low["verdict"] == "at-cap", low
    assert low["spent"] >= 0.02 - 0.005, f"التوقّفُ ليس عند الصرف: {low}"


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
    ev = m.cap_evidence(spent_before=0.0170, spent_after=0.0237, cost_here=0.006732,
                        cost_by_tokens=0.004200, cost_source="provider-cost",
                        price=0.001061, source="observed-billed",
                        meter_delta=0.006732, tokens=0, tools=1, replies=2)
    assert ev["cost_billed_usd"] == pytest.approx(0.006732)      # **حدُّ ما يُحاسَب عليه**
    assert ev["cost_by_tokens_usd"] == pytest.approx(0.004200)   # **حدٌّ أدنى للعرض** (كان يُظنُّ أعلى)
    assert ev["cost_source"] == "provider-cost"                  # أيُّ رتبةٍ حكمت — مُعلَنة
    assert ev["cap_price_usd"] == pytest.approx(0.001061)
    assert ev["cap_price_source"] == "observed-billed"
    assert ev["spent_before_usd"] == pytest.approx(0.0170)
    assert ev["spent_after_usd"] == pytest.approx(0.0237)
    assert ev["meter_delta_usd"] == pytest.approx(0.006732)
    assert "cap_bound_usd" not in ev, "الحقلُ الذي كان يُسجَّل كأنّه حدّ عاد (R117-4)"
    # **والمقسومُ يُنشر معه:** الردودُ عددًا، و«الأدوات + ١» **حدٌّ أعلى للنداءات** لا «أرضية» (R115-5)
    assert ev["replies_observed"] == 2 and ev["tools_plus_one"] == 2 and ev["tools_in_trace"] == 1
    assert "calls_floor" not in ev, "الاسمُ القديم (أرضية) عاد — وهو حدٌّ أعلى للنداءات لا أرضية"
    assert "next_ceiling_usd" not in ev, "الحقلُ المكرَّرُ بالاسم المضلِّل عاد"


def test_the_loop_reads_the_observed_price_and_records_it():
    """**توصيلٌ لا تعريف (بالـAST):** الحلقةُ تنادي القانونَ، والحقلان الجديدان مكتوبان،
    والاستيرادُ الثقيلُ داخلَ الدالّة (فالوحدةُ تُستورَد في البيئة الخفيفة)."""
    text = EVAL.read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(text).body
              if isinstance(n, ast.FunctionDef) and n.name == "run_questions")
    called = {getattr(c.func, "id", "") for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert {"cap_verdict", "billed_window", "cap_evidence",
            "cost_log", "host_max_price"} <= called, sorted(called)
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


def test_the_providers_cost_is_the_accounted_cost_and_the_floor_is_gone():
    """**R122-1 (P2 · مراجعة ١٢٢) — وقاعدةُ R116-1 أُبطلت بتاريخها وسببها لا حُذفت صامتة.**

    **ما كانت R116-1 تفرضه:** «`cost` أدنى من الرموز × سعر القائمة ⇒ يُؤخذ **الأكبر** (القائمة)»،
    خوفَ أن يُرسل المزوّدُ `cost` أقلَّ من الواقع. **والفرضُ سقط بقياس (2026-10-15):** القائمةُ
    $0.15/$0.50 لكلّ مليون، والمضيفون تحت `max_price` (**١٣ من ٣٤**) مدخلُهم **$0.04–$0.12** ⇒
    **كلُّهم دون القائمة** ⇒ فالأرضيةُ **ضاعفت المحاسَب**: السجلُّ `$0.004933` ⇔ عدّادُ المفتاح
    `$0.002519` (ثابتٌ في قراءتين بعد ٤٤ دقيقة) = **×1.96** ⇒ والسقفُ يقف عند نصف الفعليّ.

    **والثابتُ الآن:** المُحاسَبُ **لا يتجاوز ما يُحاسِب به المزوّد** ⇒ `cost` يُؤخذ كما هو.
    """
    from tools import eval_questions as m

    cost, src = m.billed_reply_cost(1_000_000, 0, 0.10, 0.12, 0.60, (0.225, 1.60))
    assert (cost, src) == (0.10, "provider-cost"), (cost, src)
    # والقائمةُ لا تعلوه: نفسُ الردّ بسعر قائمةٍ أعلى (0.30) يبقى `cost`
    cost2, src2 = m.billed_reply_cost(1_000_000, 0, 0.10, 0.30, 0.30, (0.225, 1.60))
    assert (cost2, src2) == (0.10, "provider-cost"), (cost2, src2)
    # **وحيث يُرسل المزوّدُ cost أعلى** ⇒ هو أيضًا (لا يُخفَّض بسقف)
    hi = m.billed_reply_cost(1_000_000, 0, 0.90, 0.12, 0.60, (0.225, 1.60))
    assert hi == (0.90, "provider-cost"), hi


def test_without_a_cost_the_reply_is_priced_at_the_request_ceiling():
    """**القبولُ الثاني (R122-1):** بلا `cost` ⇒ **الرموز × `max_price`** (حدُّ الطلب نفسِه) — لا سعرُ
    القائمة ولا أعلى سعرِ مضيف؛ **والمصدرُ يُسمّى** فيُقرأ من الملفّ أيُّ مرتبةٍ حكمت."""
    from tools import eval_questions as m

    got = m.billed_reply_cost(1_000_000, 1_000_000, None, 0.12, 0.60, (0.225, 1.60))
    assert got is not None
    cost, src = got
    assert src == "provider-max-price", got
    assert cost == pytest.approx(0.12 + 0.60), cost          # الرموز × حدِّ الطلب، لا القائمة
    # **وبلا سعرٍ معروف** (صفر) ⇒ أعلى سعرِ مضيفٍ يُعلَن، **وبلا قراءةٍ ⇒ لا كلفةَ تُدَّعى**
    assert m.billed_reply_cost(1_000_000, 0, None, 0.0, 0.0, (0.225, 1.60))[1] == "host-max-price"
    assert m.billed_reply_cost(0, 0, None, 0.0, 0.0, None) is None


def test_the_run_feeds_the_request_ceiling_into_the_law_not_the_list_price():
    """**والقانونُ يستهلك حدَّ الطلب في الجولة نفسِها** (لا سعرَ القائمة): يُقاس بالنصّ وبالدالّة —
    فالسعرُ الذي يُمرَّر إلى `billed_window` هو `ceiling_pair`، وسعرُ القائمة شاهدٌ للطباعة."""
    import argparse

    from tools import eval_questions as m

    a = argparse.Namespace(budget=0.15, model=None, price_in_per_m=None, price_out_per_m=None,
                           questions=pathlib.Path("docs/eval_pack/questions.json"))
    ceiling = m._resolve_ceiling(a)
    assert ceiling is not None, "حدُّ الطلب لم يُقرأ من `provider_max_price`"
    from statement_qa.qa import effective_model

    mp = m.provider_max_price(effective_model(None))
    assert ceiling == (pytest.approx(mp["prompt"]), pytest.approx(mp["completion"])), ceiling
    src = (pathlib.Path(__file__).resolve().parents[1] / "tools/eval_questions.py").read_text("utf-8")
    assert "price_in, price_out = ceiling_pair or (0.0, 0.0)" in src
    assert "price_in, price_out = price_pair or (0.0, 0.0)" not in src
