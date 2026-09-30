"""سياسةُ اللاحتميّة في الفحص الشامل: دالّةٌ خالصةٌ تُقاس بلا خدمةٍ ولا شبكةٍ ولا نموذج.

**ولماذا وحدةٌ مستقلّة؟** لأنّ هذه السياسةَ تُحدّد لونَ البوّابة عند كلّ إقلاعٍ عبر قراءةٍ غيرِ حتميّة —
فهي منطقُ حكمٍ لا تفصيلًا؛ والقاعدةُ في `tools/qa_gate.py::decide_two_runs`. والوحدةُ خفيفةٌ
(ستاندرد + `tools.qa_gate`) فتُدرَج في الـCI الخفيف، ولا تعتمد على خدمةٍ حيّة.

**ولا تُقرأ السياسةُ من نصٍّ عامّ:** الأساسُ الذي تُقاس عليه هو `_run` أدناه — عدّادٌ صريحٌ لكلّ قراءة.

**وحدودٌ أُغلقت هنا بعد قياس المقاعد الثلاثة (٢٠٢٦-٠٩-٢٥):** قراءةٌ ثانيةٌ **أنحفُ** لا تُبرّئ ·
مخالفةُ أوراكل الفوتر في القراءة الأولى **تُعلَن ولا تُغسَل** · والنظافةُ تشمل الفوتر · وعقدُ القياس
(`RUN_FIELDS`) موضعٌ واحد بين المنتج والمستهلك.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.qa_gate import RUN_FIELDS, decide_two_runs  # noqa: E402


def _run(n_rows: int = 104, total: int = 104, clean: int = 104, ids: tuple[str, ...] = (),
         footer: tuple[int, int] = (10, 10), flag: bool = False,
         cov: tuple[int, int] | None = (10, 10)) -> dict:
    """قراءةٌ واحدةٌ كما تُنتجها `_e2e_measure` فعلًا: العدّاداتُ والهويّةُ وأوراكلُ الفوتر."""
    return {"summary": "s", "data": [], "idx": {}, "total": total, "clean": clean,
            "susp": len(ids), "ids": list(ids), "n_rows": n_rows,
            "footer_pair": footer, "footer_seg": ("⚠ " if flag else "") + "seg",
            "footer_flag": flag, "rows_flag": False, "coverage_pair": cov}


def test_the_run_contract_is_declared_in_one_place():
    """**الدَّرزُ يُقاس:** ما يبنيه الضابطُ يطابق ما يُنتجه القياسُ ويستهلكه الحكم — وإلّا تباعدا صامتين."""
    assert set(_run()) == set(RUN_FIELDS)


def test_a_clean_first_read_passes_and_costs_one_read():
    ok, why = decide_two_runs(_run())
    assert ok, why
    assert "الأولى" in why, why


def test_a_lone_dirty_read_is_never_a_pass_by_itself():
    """القراءةُ الواحدةُ المشبوهةُ لا تكون حكمًا — الحكمُ يحتاج قراءةً ثانية."""
    ok, why = decide_two_runs(_run(clean=103, ids=("10:41",)))
    assert not ok, "قراءةٌ واحدةٌ غيرُ نظيفةٍ مُرّرت"
    assert "بلا محاولةٍ ثانية" in why, why


def test_the_failure_message_names_the_class_it_saw():
    """**R74-2 (مراجعة ٧٤):** رسالةُ «لا قراءةَ نظيفة» كانت تُسقط أسماءَ الصفحاتِ بلا حكم وتبقى وصفاً
    عامّاً («٩/٩» و«٩/١٠») ⇒ المشخِّصُ يستنتج — وهو ما وقع فعلًا: رجّحتُ سبباً لا يمكن أن يقع في الكود.
    الآن تُمرَّر الفئةُ باسمها وصفحاتها **من ملخّص التشغيلة نفسِه** (فلا وصفَ ثانٍ يخالف الأصل).
    """
    s = ("… • تحقق الفوتر: 9/9 مطابق (دقة)، وتغطية 9/10 — غير قابلة للتحقق: 1 • الكلفة: $0.0100")
    dirty = dict(_run(clean=103, footer=(9, 9), cov=(9, 10)), summary=s)
    ok, why = decide_two_runs(dict(dirty), dict(dirty))
    assert not ok, why
    assert "غير قابلة للتحقق: 1" in why, why
    assert "الفئاتُ المسمّاة" in why, why
    # وبلا فئاتٍ مسمّاة: يُقال ذلك صراحةً بدل الفراغ (فراغُ التقاطع ليس نظافة)
    clean_summary = dict(dirty, summary="… • تحقق الفوتر: 9/9 …")
    _ok2, why2 = decide_two_runs(dict(clean_summary), dict(clean_summary))
    assert "لا فئةَ مسمّاةٍ في الملخّص" in why2, why2


def test_no_verdict_on_unknown_code_and_the_class_carries_its_reason():
    """**R74-3 (مراجعة ٧٤) وR76-2 (مراجعة ٧٦):**

    ① **لا حكمَ على كودٍ مجهول:** الفحصُ الشامل يقيس العمليةَ الجارية لا الشجرة، وقد أعلن «٥/٥» وهو يقيس
    كودًا عمرُه اثنا عشر يومًا (٢٠٢٦-٠٩-٢٦) ⇒ فصار التطبيقُ ينشر بصمةَ كوده، والبوّابةُ ترفض المطابقةَ
    الفاشلة **فشلًا مُغلَقًا** (بصمةٌ غائبة · `unknown` · أو مختلفةٌ ⇒ لا رقمَ من نتيجة).
    ② **والفئةُ تحمل سببَها كما كتبه التطبيق** («أوّلُ صفحة — لا مرجعَ سابق») فلا يُستنتج سببُها ثانيةً
    (وهو بعينه ما أوقعني في R74-1: استنتاجُ تخطّيٍ لا يقع في الكود).
    """
    from tools.qa_gate import _named_classes, _provenance_verdict

    # **المقارنةُ على بصمة الكود لا على الالتزام (R77-4):** تطابقُ `code_hash` يكفي — ولو اختلف
    # `sha` (تصحيحُ وثيقةٍ لا يمسّ الكود لا يُلزم بإعادة تشغيل ✓ وهذا هو المكسبُ المقصود).
    assert _provenance_verdict(
        {"sha": "abc1234", "code_hash": "h1"}, "abc1234", "h1") is None
    assert _provenance_verdict(
        {"sha": "abc1234", "code_hash": "h1"}, "def5678", "h1") is None
    _no_stamp = _provenance_verdict(None, "abc1234", "h1")
    assert _no_stamp and "لا حكمَ" in _no_stamp
    _other = _provenance_verdict({"sha": "abc1234", "code_hash": "h1"}, "abc1234", "h9")
    assert _other and "أعِد تشغيل" in _other
    # **وتطبيقٌ أقدمُ لا ينشر `code_hash` يُرفض** ولا يُفترض فيه أنّه على الكود (فشلٌ مُغلَق).
    _old = _provenance_verdict({"sha": "abc1234"}, "abc1234", "h1")
    assert _old and "unknown" in _old
    _unknown = _provenance_verdict({"sha": "abc1234", "code_hash": "unknown"}, "abc1234", "h1")
    assert _unknown and "unknown" in _unknown

    s = ("… • تحقق الفوتر: 9/9 مطابق (دقة)، وتغطية 9/10 — غير قابلة للتحقق: "
         "1 (أوّلُ صفحة — لا مرجعَ سابق) • الكلفة: $0.0100")
    got = _named_classes({"summary": s})
    assert "لا مرجعَ سابق" in got, got

    # **وصفحةٌ أرجعت مصفوفةً فارغةٌ تُسمّى ويُرفض معها الحكم (قاسه قياسُ البروفة ٢٠٢٦-٠٩-٣٠):**
    # إجابةٌ صحيحةُ الشكل لكنها فارغة ⇒ صفحةٌ كاملةٌ تُفقد بلا استثناء (٩٤ صفًّا بدل ١٠٤) ⇒ فليست
    # «نظيفة» ولا تُبرّأ بإعادةٍ ثانية.
    from tools.qa_gate import _is_clean
    rows_sum = ("… • تحقق الفوتر: 10/10 مطابق (دقة)، وتغطية 10/10 • ⚠ صفحةٌ بلا صفوفٍ وتذييلُها "
                "يُظهر حركات (قراءةٌ فاشلة لا صفحةٌ فارغة): ص5")
    empty_page = dict(_run(), summary=rows_sum, rows_flag=True)
    assert not _is_clean(empty_page), "قراءةٌ فيها صفحةٌ بلا صفوفٍ قُرئت نظيفة"
    assert "صفحةٌ بلا صفوف: ص5" in _named_classes(empty_page), _named_classes(empty_page)
    assert _is_clean(dict(_run(), summary=rows_sum, rows_flag=False)), \
        "الوسمُ وحدَه يحكم — لا نصُّ الملخّص (لو حكم النصُّ لمرّ عطبٌ في صياغته)"


def test_repeating_suspect_names_a_deterministic_defect():
    """عطبٌ حتميّ: المعرّفُ نفسُه يعود في القراءتين ⇒ أحمر **باسمه**، لا «شكوك»."""
    ok, why = decide_two_runs(_run(clean=103, ids=("10:41", "9:7")),
                              _run(clean=103, ids=("9:7",)))
    assert not ok, "عطبٌ متكرّرٌ مُرّر"
    assert "تتكرّر" in why and "9:7" in why, why


def test_the_decisive_rule_is_no_clean_read_no_acquittal():
    """القاعدةُ الحاسمة: تقاطعٌ فارغٌ لا يعني براءةً ما دامت لا قراءةَ نظيفةَ واحدة.

    (والتقاطعُ **تشخيصيٌّ** لا حاسم: أيُّ تقاطعٍ يستلزم أنّ الثانيةَ غيرُ نظيفةٍ حتمًا.)
    """
    ok, why = decide_two_runs(_run(clean=103, ids=("10:41",)),
                              _run(clean=102, ids=("10:42", "9:7")))
    assert not ok, "قراءتان غيرُ نظيفتين مُرّرتَا لمجرّد اختلاف المعرّفات"
    assert "لا قراءةَ نظيفة" in why, why


def test_a_flaky_read_passes_declared_when_one_read_is_clean():
    ok, why = decide_two_runs(_run(clean=103, ids=("10:41",)), _run())
    assert ok, why
    assert "غيرُ حتميّة" in why, why


def test_a_lost_row_is_not_clean_even_with_zero_suspects():
    """صفرُ شكوكٍ مع صفٍّ مفقودٍ من العدّ = عطبُ عدّ لا نظافة. (سمُّه: م١٤)"""
    ok, _ = decide_two_runs(_run(total=104, clean=103, ids=()))
    assert not ok, "صفٌّ مفقودٌ مع صفرِ شكوكٍ عُدَّ نظافة"


def test_a_thinner_second_read_cannot_acquit():
    """**عِلّةٌ اصطادها مقعدا المعايير والمواصفة بالقياس:** قراءةٌ ثانيةٌ أنحفُ تُقرأ نظيفةً فيُعتمد
    نقصُها — و`MIN_ROWS` وحدَه يسمح بفقدِ صفوفٍ كثيرة. فهي تُرفض بسببها المُسمّى. (سمُّه: م١٥)"""
    ok, why = decide_two_runs(_run(n_rows=104, total=104, clean=103, ids=("10:41",)),
                              _run(n_rows=99, total=99, clean=99))
    assert not ok, "قراءةٌ أنحفُ أبرّأت فقدَ صفوف"
    assert "أنحف" in why, why


def test_a_footer_denominator_hole_is_a_dirty_read_not_a_silent_gate_failure():
    """**R60-2 (قاسه المدقّق في مراجعة ٦٠) — وهو ما أسقط البوّابة ٤/٥ ثمّ أُعيدت باليد:**

    ثقبُ مقام التغطية (`f_possible < cov[1]`: صفحاتٌ خرجت من الأوراكل بلا حكم) كان **يُقرأ نظيفًا**
    عند السياسة ⇒ لا إعادةَ قراءةٍ ولا وسمَ `[flaky_read]`، ثمّ تسقط البوّابةُ على التأكيد الصلب
    (`g_end_to_end`) ⇒ «أعِدْ حتى تخضرّ». والآن الثقبُ **عطبُ نظافة**: تُطلَب قراءةٌ ثانية، وإن أبرّأت
    فالإبراءُ **مُعلَنٌ ومُوسَّم** يُقيَّد في السجلّ (وسمُّه: م٢٣).
    """
    hole = {"footer": (9, 9), "cov": (9, 10)}      # مقامُ الأوراكل ٩ مقابل تغطيةٍ ١٠ ⇒ صفحةٌ بلا حكم
    ok, why = decide_two_runs(_run(footer=hole["footer"], cov=hole["cov"]))
    assert not ok, "ثقبُ المقام عُدَّ نظافةً من قراءةٍ واحدة (وهو عطبُ ٤/٥ نفسُه)"
    assert "بلا محاولةٍ ثانية" in why, why
    # **ولا يُغسَل صامتًا:** قراءةٌ ثانيةٌ نظيفةٌ تُبرّئ **مُعلَنةً** (ويُقيَّد الوسمُ في السجلّ)
    ok2, why2 = decide_two_runs(_run(clean=103, ids=("10:41",), footer=hole["footer"], cov=hole["cov"]),
                                _run())
    assert ok2, why2
    assert "غيرُ حتميّة" in why2 and "9/10" in why2, f"الإبراءُ لم يُعلن الثقبَ المقيس: {why2}"
    # **وقراءةٌ بلا مقامِ تغطيةٍ مقروء ليست نظيفة** — فشلٌ مُغلَق: لا نظافةَ بلا قياس
    ok3, why3 = decide_two_runs(_run(cov=None))
    assert not ok3, "قراءةٌ بلا مقامِ تغطيةٍ عُدَّت نظيفة ⇒ نظافةٌ بلا قياس"


def test_a_footer_violation_in_the_first_read_is_declared_not_washed():
    """**عِلّةٌ اصطادها مقعدُ المواصفة:** مخالفةُ أوراكل الفوتر (أقوى حارسٍ خارجيّ) في القراءة الأولى
    كانت تُغسَل بصمتٍ بإعادةِ قراءةٍ نظيفة. الآن تُمرَّر **وبيانُها مُعلَن**: المقامان والوسم."""
    ok, why = decide_two_runs(_run(clean=103, ids=("10:41",), footer=(9, 10), flag=True), _run())
    assert ok, why
    assert "9/10" in why and "⚠" in why, f"مخالفةُ الفوتر غُسلت صامتة: {why}"


def test_a_footer_mismatch_in_the_second_read_is_not_clean():
    """والنظافةُ تشمل الفوتر: قراءةٌ بلا شكوكٍ وبعدّادٍ مغلقٍ ومخالفةِ فوترٍ **ليست نظيفة**."""
    ok, why = decide_two_runs(_run(clean=103, ids=("10:41",)), _run(footer=(9, 10), flag=True))
    assert not ok, "قراءةٌ بمخالفةِ فوترٍ عُدَّت نظيفة"
    assert "لا قراءةَ نظيفة" in why, why
