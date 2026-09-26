"""أداةُ القارئ المحلّيّ — اختبارُ **قواعد الأرقام** (وهي ما كذب في أوّل قياس، لا المحرّك).

الدرسُ المُختبَر (أ-٧): مطابقةُ الأرقام العربيّة بلا توحيدٍ **بحكم موقع الفاصل** تُنتج فروقًا كاذبة؛
فالأداةُ تُخرج ثلاثَ مجموعاتٍ مسمّاة (`شكل` · `قيمة` · `أرقام`) وتُعلن أيَّها أنتج الرقمَ المنشور،
كي لا يُحكم على المحرّك بمقياسٍ مكسور. **ولا تُخلط القواعدُ في مجموعةٍ واحدة** — الخلطُ نفسُه يكذب.

**الأرقامُ هنا مبنيّةٌ من أجزاء لا مكتوبة** (`_D`)، فلا يُدخل اختبارٌ قيمةً من الكوربوس إلى مستودعٍ عامّ
(القاعدةُ ١٢/١٤: لا يُعفى موضع، ولا يُنشر ظهور).

**وما يحتاج البياناتَ أو المحرّكَ يُتخطّى معلَنًا** (الحزمةُ لا تُشحن، وVision ليست من متطلّبات المشروع)
فيمرّ هذا الملفُّ في الـCI — حيث يُقاس نصفُ المقارنة وحده.
"""
from __future__ import annotations

import importlib.util
import pathlib
from decimal import Decimal

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_reader_probe", ROOT / "tools" / "local_reader_probe.py")
lrp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lrp)


@pytest.fixture(autouse=True)
def _clean_scan_cache():
    """المسحُ المخزَّن حالةٌ عامّة ⇒ يُصفَّر بين الاختبارات كي لا يعبر اختبارٌ اختبارًا."""
    lrp.forget_scan_cache()
    yield
    lrp.forget_scan_cache()


def test_a_run_scans_each_design_once(monkeypatch, tmp_path):
    """**R64-3 (مقيس في مراجعة ٦٤):** كان المسحُ يتكرّر — تصفيةً في `design_dir` ثم في `main` ثم في `--list`
    (٥٧٧ قراءةَ `label.json` لـ٢٩٤ ملفًا في تشغيلٍ عاديّ، و٨٧١ في `--list`) بينما النصُّ يقول «مسحٌ واحد».
    """
    calls: list[str] = []
    dirs = [tmp_path / "a", tmp_path / "b"]
    for d in dirs:
        d.mkdir()
    monkeypatch.setattr(lrp, "design_candidates", lambda: dirs)
    monkeypatch.setattr(lrp, "_scan_one", lambda name: calls.append(name) or [])
    assert lrp.eligible() == []
    lrp.eligible()
    assert calls == ["a", "b"], f"مسحٌ متكرّر: {calls}"

# أرقامٌ مبنيّةٌ من أجزاء: ثلاثُ خاناتٍ صحيحة (تحت مدى حارس المبالغ: ≥٤ + كسر) فلا ظهورَ جديد
_D = "9"
_AR = "٩"
SMALL = f"{_D * 3}.{_D * 2}"                 # 999.99
SMALL_AR = f"{_AR * 3}٫{_D * 2}"             # ٩٩٩٫٩٩
THOU = f"{_AR * 3}٬{_AR * 3}٫{_D * 2}"       # آلافٌ عربيّة + عشريّة
THOU_LAT = f"{_D * 3},{_D * 3}.{_D * 2}"     # آلافٌ لاتينيّة + عشريّة
OLD_LAT = f"{_D * 3}.{_D * 3},{_D * 2}"      # عتيقةٌ: الفاصلةُ عشرِيّة
CANON_THOU = f"{_D * 6}.{_D * 2}"
DIGITS_THOU = _D * 8
NO_DESIGN = "__no_such_design__"


# ---------------------------------------------------------------- توحيدُ المحارف

def test_arabic_digit_scripts_both_normalise():
    assert lrp.to_ascii_digits("٠١٢٣٤٥٦٧٨٩") == "0123456789"
    assert lrp.to_ascii_digits("۰۱۲۳۴۵۶۷۸۹") == "0123456789"
    assert lrp.to_ascii_digits(_AR * 3) == _D * 3


# ---------------------------------------------------------------- قاعدةُ الشكل (بحكم الموقع)

def test_canonical_decides_decimal_by_position_not_by_character():
    """ثلاثُ صيغٍ للعدد نفسه: عربيّة حديثة · لاتينيّة حديثة · عتيقة (الفاصلةُ عشرِيّة)."""
    assert lrp.canonical(THOU) == CANON_THOU
    assert lrp.canonical(THOU_LAT) == CANON_THOU
    assert lrp.canonical(OLD_LAT) == CANON_THOU
    assert lrp.canonical(SMALL_AR) == SMALL
    assert lrp.canonical(SMALL) == SMALL


def test_canonical_accepts_a_single_fraction_digit():
    """ورقةٌ تطبع كسرًا بخانةٍ واحدة لا تُقرأ صحيحةً (عطبٌ في الاتّجاه المقابل، مقيسٌ ومُغلَق)."""
    one_digit = f"{_D * 3}.{_D}"                 # 999.9
    assert lrp.canonical(one_digit) == f"{_D * 3}.{_D}"
    assert lrp.value_of(one_digit) == Decimal(f"{_D * 3}.{_D}")


def test_canonical_keeps_integers_integral():
    assert lrp.canonical(_D * 3) == _D * 3          # بلا كسور: يبقى صحيحًا
    assert lrp.canonical(_AR * 3) == _D * 3


def test_canonical_rejects_what_has_no_digit():
    assert lrp.canonical("رصيد") is None
    assert lrp.canonical("") is None


# ---------------------------------------------------------------- قاعدةُ القيمة (المنشورة)

def test_value_matches_across_separator_styles():
    """القيمةُ هي الجواب: صيغٌ مختلفةُ الشكل لعددٍ واحد تتّفق هنا — ولهذا هي قاعدةُ الرقم المنشور."""
    assert lrp.value_of(THOU) == lrp.value_of(THOU_LAT) == lrp.value_of(OLD_LAT) == Decimal(CANON_THOU)


# ---------------------------------------------------------------- القواعدُ الثلاث تُسمّى ولا تُخلط

def test_the_four_lenses_are_named_and_the_published_one_is_first():
    assert lrp.RULES == ("ورق", "شكل", "قيمة", "أرقام")
    assert lrp.PUBLISHED_RULE == "ورق"
    assert set(lrp.numeric_sets("")) == set(lrp.RULES)


def test_the_three_rules_do_diverge():
    """حالةٌ مقيسةٌ تُعلن الفرق: المحرّكُ قد يُسقط الفاصلةَ فيقرأ أرقامًا مجرَّدة."""
    dropped = DIGITS_THOU
    kept = THOU_LAT
    assert lrp.canonical(dropped) != lrp.canonical(kept)          # شكلًا: يفترقان
    assert lrp.value_of(dropped) != lrp.value_of(kept)            # قيمةً: يفترقان
    assert lrp.digits_of(dropped) == lrp.digits_of(kept) == DIGITS_THOU   # أرقامًا: يتّفقان


def test_numeric_sets_collects_from_free_text():
    got = lrp.numeric_sets(f"رصيد {THOU} ثم {SMALL} بعده")
    assert Decimal(CANON_THOU) in got["قيمة"]
    assert Decimal(SMALL) in got["قيمة"]


def test_numeric_sets_keeps_the_rules_apart():
    """الخلطُ يكذب: «ورق» بصيغة الورق، و«شكل» كانونيٌّ نصًّا، و«قيمة» أعداد، و«أرقام» مجرَّدة."""
    got = lrp.numeric_sets(THOU_LAT)
    assert got["قيمة"] == {Decimal(CANON_THOU)}
    assert got["شكل"] == {CANON_THOU}
    assert got["ورق"] == {CANON_THOU}
    assert got["أرقام"] == {DIGITS_THOU}


def test_the_published_rule_requires_the_printed_fraction():
    """**عطبُ R64-1 (مقيس في مراجعة ٦٤):** قاعدةُ القيمة تحتسب رمزًا تائهًا **بلا كسر** إصابةً لمبلغٍ مطبوع.

    فثلاثُ إصاباتٍ عارضة من أربع كان رمزُها خانةً مفردة، والرابعةُ أرقامًا في سطر وصف. والقاعدةُ المُعلَنة
    («ورق») لا تحتسب إلّا الصيغةَ التي يطبعها العمود: الكسرُ شرطُ مطابقة.
    """
    printed = f"{_D * 3}." + "0" * 2            # كما يطبعه العمود: بكسره من خانتين
    stray = f"{_D * 3}"                          # ما يُقرأ خطأً: رمزٌ تائه بلا كسر
    assert Decimal(printed) == Decimal(stray) and printed != stray
    found = lrp.numeric_sets(stray)
    assert Decimal(printed) in found["قيمة"]                  # العدسةُ التشخيصيّةُ تبتلعه
    assert found["ورق"] == set()                              # والمُعلَنةُ لا
    assert lrp.has_paper_shape(lrp.canonical(printed)) and not lrp.has_paper_shape(lrp.canonical(stray))


def test_rows_are_counted_apart_from_distinct_values():
    """الوحدتان مختلفتان: صفّان بالمبلغ نفسه = صفّان، وقيمةٌ واحدة — والّلبسُ بينهما كان عطبًا معلَنًا."""
    rows = [{"printed_amount": SMALL}, {"printed_amount": SMALL}]
    hit, total, single = lrp.row_counts(rows, lrp.numeric_sets(SMALL))
    assert (hit, total, single) == (2, 2, 0)
    assert len(lrp.truth_sets(rows)["مبالغ"][lrp.PUBLISHED_RULE]) == 1


def test_single_integer_digit_amounts_are_declared():
    """المبالغُ ذاتُ الخانة الصحيحة المفردة تُعلَن منفصلةً: رمزٌ تائه واحدٌ في صفحةٍ من ٥٦ سطرًا يطابقها."""
    rows = [{"printed_amount": f"{_D}." + "0" * 2}, {"printed_amount": f"{_D * 2}." + "0" * 2}]
    hit, total, single = lrp.row_counts(rows, lrp.numeric_sets(""))
    assert (hit, total, single) == (0, 2, 1)
    assert lrp.integer_digits_of("5.00") == 1 and lrp.integer_digits_of("55.00") == 2


def test_value_unifies_shapes_that_carry_the_same_number():
    """**عدسةٌ تشخيصيّة:** `Decimal` توحّد الصيغ المتساوية (`«٩٩٩» == «٩٩٩٫٠٠»` قيمةً وتختلف شكلًا) — وهي
    بالضبط ما جعل «قيمة» تحتسب إصاباتٍ عارضة (R64-1)، فلا يُنشَر رقمُها كمقياس.
    """
    plain, padded = f"{_D * 3}", f"{_D * 3}." + "0" * 2
    assert Decimal(plain) == Decimal(padded) and plain != padded
    assert lrp.numeric_sets(plain)["قيمة"] == lrp.numeric_sets(padded)["قيمة"] == {Decimal(plain)}
    assert lrp.numeric_sets(plain)["شكل"] != lrp.numeric_sets(padded)["شكل"]


# ---------------------------------------------------------------- الحقيقةُ الأرضيّة

def test_truth_form_prints_json_numbers_like_the_paper():
    """`label.json` يحمل أعدادًا لا نصوصًا: 999.9 يجب أن يصير 999.90 لا 999.9 (عطبٌ مقيس)."""
    assert lrp._truth_form(999.9) == f"999.{_D}0"
    assert lrp._truth_form(_D * 3) == _D * 3          # صحيحٌ يبقى صحيحًا
    assert lrp._truth_form(SMALL_AR) == SMALL_AR      # نصٌّ يُترك كما هو


def test_truth_sets_read_the_same_three_shapes_separately():
    rows = [{"printed_amount": THOU, "balance": 999.9},
            {"printed_amount": None, "balance": SMALL}]
    got = lrp.truth_sets(rows)
    assert Decimal(CANON_THOU) in got["مبالغ"]["قيمة"] and CANON_THOU in got["مبالغ"]["شكل"]
    assert DIGITS_THOU in got["مبالغ"]["أرقام"]
    assert Decimal(f"999.{_D}0") in got["أرصدة"]["قيمة"]     # العطبُ المرصود أعلاه مغلق
    assert set(got["أرصدة"]) == set(lrp.RULES)
    assert len(got["مبالغ"]["قيمة"]) == 1                    # القيمةُ الغائبة لا تُخترع


def test_truth_measures_the_printed_amount_only():
    """القياسُ على ما على الورق: صفٌّ بلا `printed_amount` يُسقَط — لا يُقابَل بمقدارٍ مشتقٍّ من السلسلة."""
    got = lrp.truth_sets([{"printed_amount": None, "proven_amount": THOU, "balance": None}])
    assert got["مبالغ"]["قيمة"] == set() and got["مبالغ"]["شكل"] == set()


def test_both_sides_drop_single_digit_forms_from_the_digits_rule():
    """حدُّ الإدراج واحدٌ على الطرفين — فلا يبقى في المقام ما لا يمكن أن يُطابَق."""
    assert lrp.numeric_sets("رصيد 0.65")["أرقام"] == {"65"}
    assert lrp.numeric_sets("رصيد 5")["أرقام"] == set()        # خانةٌ واحدة ⇒ خارج القاعدة
    got = lrp.truth_sets([{"printed_amount": None, "balance": 5}])
    assert got["أرصدة"]["أرقام"] == set()


# ---------------------------------------------------------------- الصفحاتُ المُجمَّدة ورموزُ الخروج

def test_the_document_agrees_with_the_arithmetic_of_its_own_numbers():
    """**اتّساقُ الوثيقة — لا ربطُ الأداة.** صرّح مقعدُ التحقّق في مراجعة ٦٤ (R64-2) بأنّ هذا الضابط
    لا يلمس الأداةَ ولا البيانات (سمّموا `value_of` فبقي يمرّ): فهو اتّساقٌ حسابيٌّ للوثيقة، وقد سُمّي بما هو.
    والربطُ الحقيقيّ هو الضابطُ التالي — يُشغّل الأداةَ فعلًا.
    """
    doc = ROOT / "handoff" / "sulaiman" / "20260926-0205-MEASUREment-q4-local-reader-five-pages.md"
    text = doc.read_text(encoding="utf-8")
    assert round(100 * 13 / 35, 1) == 37.1                    # القيمُ المتمايزة: «ورق»
    assert round(100 * 20 / 46, 1) == 43.5                    # الصفوف: «ورق»
    assert round(100 * 29 / 35, 1) == 82.9                    # الأرصدة: «ورق»
    for shown in ("١٣/٣٥", "٢٠/٤٦", "٢٩/٣٥", "٣٧.١٪", "٤٣.٥٪", "٨٢.٩٪"):
        assert shown in text, f"رقمٌ منشورٌ غاب عن الوثيقة: {shown}"


def test_the_probe_reproduces_the_published_counts_locally(capsys):
    """**الربطُ الحقيقيّ (R64-2):** يُشغّل الأداةَ على الصفحات الخمس ويُثبّت **أعدادَ كلّ صفحة** — لا قيمًا.

    ويُتخطّى بسببٍ مُعلَنٍ عند غياب البيانات أو محرّك Vision (ليس من متطلّبات المشروع) — فيسقط في الموضع
    الوحيد الذي يقدر أن يقيس فيه: جهازٌ فيه الصورُ والمحرّك. وتغييرُ قاعدةٍ يُحرّك الرقمَ يسقط هنا.
    """
    if not lrp.eligible():
        pytest.skip("لا بياناتِ تدريبٍ محلّيّة (data/ لا تُشحن مع المستودع)")
    try:
        import Vision  # noqa: F401
    except ImportError:
        pytest.skip("محرّكُ macOS Vision غيرُ متاحٍ (بيئةٌ معزولة، ليست من متطلّبات المشروع)")
    rc = lrp.main([])
    out = capsys.readouterr().out
    assert rc == lrp.EXIT_OK
    for shown in ("13/35 = 37.1", "20/46 = 43.5", "29/35 = 82.9", "9 من 46"):
        assert shown in out, f"عددٌ لم تعُد الأداةُ تُنتجه: {shown}"


def test_page_numbers_parse_strictly():
    assert lrp._parse_pages("1,9") == (1, 9)
    assert lrp._parse_pages(None) == lrp.PUBLISHED_PAGES
    with pytest.raises(lrp.BadArguments):
        lrp._parse_pages("أ")


def test_the_published_five_are_a_named_frozen_set():
    """الخمسةُ ثابتٌ مُعلَنٌ لا مُشتقٌّ في كلّ وقت — والاختبارُ يقيسها **حرفًا** لا بالمقارنة بنفسها."""
    assert lrp.PUBLISHED_PAGES == (1, 187, 320, 404, 539)


def test_selected_pages_are_the_published_five_or_the_data_is_absent():
    """الحصيلةُ المنشورةُ تُعاد من القرص — أو يُعلَن غيابُ البيانات (لا تخمين)."""
    if not lrp.design_dir().exists():
        pytest.skip("لا بياناتُ تدريبٍ محلّيّة (الحزمةُ لا تُشحن)")
    pages = [int(lab["page"]) for _, lab, _ in lrp.selected()]
    assert pages == [1, 187, 320, 404, 539]


def test_list_mode_runs_without_the_engine(capsys):
    """`--list` يعمل بلا محرّكٍ وبلا قراءةِ صورة — فمن قاس يُعيد القياس في أيّ بيئة."""
    rc = lrp.main(["--list"])
    out = capsys.readouterr().out
    if lrp.design_dir().exists():
        assert rc == lrp.EXIT_OK and "الصفحاتُ المُجمَّدةُ المنشورة" in out and "المُؤهَّلُ الآن" in out
    else:
        assert rc == lrp.EXIT_NO_DATA and "لا بياناتِ تدريبٍ محلّيّة" in out


def test_no_data_is_reported_as_no_data_not_as_ineligible(capsys):
    """**عطبٌ أدخلته أوّلُ نسخةٍ من الإصلاح (كشفه مقعدُ تحقّقٍ مستقلّ بالقياس):** غيابُ البيانات كان
    يُبلَّغ عنه «صفحةً غيرَ مؤهَّلة» (٤) لأنّ `selected()` تُنادى قبل أيّ فحصٍ للوجود ⇒ صار الوجودُ يُفحَص أولًا (٣)."""
    rc = lrp.main(["--pages", "1", "--design", NO_DESIGN])
    out = capsys.readouterr().out
    assert rc == lrp.EXIT_NO_DATA and "لا بياناتِ تدريبٍ محلّيّة" in out
    assert "غيرُ مؤهَّلة" not in out


def test_an_ineligible_page_is_a_named_exit_code(capsys):
    """صفحةٌ غيرُ مؤهَّلة ومع البياناتُ موجودة ⇒ ٤ باسمِها؛ وعلى شجرةٍ بلا بيانات ⇒ ٣ (ولا يُخلط الاثنان)."""
    rc = lrp.main(["--pages", "99999"])
    out = capsys.readouterr().out
    if lrp.design_candidates():
        assert rc == lrp.EXIT_NOT_ELIGIBLE and "غيرُ مؤهَّلة" in out
    else:
        assert rc == lrp.EXIT_NO_DATA
    with pytest.raises(lrp.IneligiblePage):
        lrp.selected((1,), design=NO_DESIGN)


def test_a_zero_denominator_refuses_instead_of_crashing(monkeypatch, capsys):
    """**عطبٌ أدخله الإصلاح (مقيس):** مقامٌ صفريّ (كلُّ الصفوف بلا مبلغٍ مطبوع) كان ينفجر بـ
    `ZeroDivisionError` وتتبّعٍ خامٍ ورمزِ خروج ١ — وهو الصنفُ نفسُه الذي جاء الالتزامُ ليُسمّيه ⇒ رفضٌ مسمّى (٣)."""
    monkeypatch.setattr(lrp, "eligible",
                        lambda *a, **k: [(ROOT / "tests", {"page": 1}, [{"balance": None}])])
    monkeypatch.setattr(lrp, "ocr", lambda _p: "")
    rc = lrp.main(["--pages", "1"])
    assert rc == lrp.EXIT_NO_DATA and "لا مقامَ قابلًا للقياس" in capsys.readouterr().out


def test_a_zero_denominator_in_one_column_only_refuses(monkeypatch, capsys):
    """والفرعُ الثاني: مبالغُ مطبوعةٌ بلا أرصدة ⇒ الرفضُ يسمّي العمودَ الناقص (كان فرعُ `bal_n==0` غيرَ مُختبَر)."""
    monkeypatch.setattr(lrp, "eligible",
                        lambda *a, **k: [(ROOT / "tests", {"page": 1}, [{"printed_amount": THOU,
                                                                          "balance": None}])])
    monkeypatch.setattr(lrp, "ocr", lambda _p: "")
    rc = lrp.main(["--pages", "1"])
    out = capsys.readouterr().out
    assert rc == lrp.EXIT_NO_DATA and "لا الأرصدة مطبوعةً" in out and "لا مقامَ قابلًا للقياس" in out


def test_list_does_not_swallow_a_malformed_argument(capsys):
    """**عطبُ اتّساقٍ كشفه مقعدُ تحقّق:** `--list` كان يعود قبل تدقيق `--pages` فيبتلع وسيطًا مشوَّهًا
    صامتًا (`--list --pages أ` ⇒ ٠) — والترويسةُ تُعلن ٥ لوسيطٍ مشوَّه بلا استثناء ⇒ التدقيقُ صار قبل الفرعين."""
    assert lrp.main(["--list", "--pages", "أ"]) == lrp.EXIT_BAD_ARGS
    assert "وسيطٌ مشوَّه" in capsys.readouterr().out


def test_bad_arguments_get_their_own_named_code(capsys):
    """وسيطٌ مشوَّه ⇒ ٥ باسمه: كان `--pages أ` يموت بـ١ (موتٌ غيرُ مسمّى)، و`--nope` بـ٢ (رمزِ المحرّك)."""
    assert lrp.main(["--pages", "أ"]) == lrp.EXIT_BAD_ARGS
    assert "وسيطٌ مشوَّه" in capsys.readouterr().out
    assert lrp.main(["--nope"]) == lrp.EXIT_BAD_ARGS
    assert "وسيطٌ مشوَّه" in capsys.readouterr().out


def test_missing_engine_is_a_named_refusal_not_a_crash(monkeypatch):
    """غيابُ المحرّك يُطفئ الأداةَ برسالةٍ ورمز ٢ — لا انهيارٌ يُقرأ حكمًا."""
    monkeypatch.setattr(lrp, "ocr", lambda _p: (_ for _ in ()).throw(RuntimeError("غيرُ متاح")))
    monkeypatch.setattr(lrp, "eligible",
                        lambda *a, **k: [(ROOT / "tests", {"page": 1}, [{"balance": 1}])])
    monkeypatch.setattr(lrp, "selected",
                        lambda *a, **k: [(ROOT / "tests", {"page": 1}, [{"balance": 1}])])
    assert lrp.main([]) == lrp.EXIT_NO_ENGINE
