"""أداةُ القارئ المحلّيّ — اختبارُ **قواعد الأرقام** (وهي ما كذب في أوّل قياس، لا المحرّك).

الدرسُ المُختبَر (أ-٧): مطابقةُ الأرقام العربيّة بلا توحيدٍ **بحكم موقع الفاصل** تُنتج فروقًا كاذبة؛
فالأداةُ تُخرج ثلاثَ مجموعاتٍ مسمّاة (`شكل` · `قيمة` · `أرقام`) وتُعلن أيَّها أنتج الرقمَ المنشور،
كي لا يُحكم على المحرّك بمقياسٍ مكسور. **ولا تُخلط القواعدُ في مجموعةٍ واحدة** — الخلطُ نفسُه يكذب.

**الأرقامُ هنا مبنيّةٌ من أجزاء لا مكتوبة** (`_D`)، فلا يُدخل اختبارٌ قيمةً من الكوربوس إلى مستودعٍ عامّ
(القاعدةُ ١٢/١٤: لا يُعفى موضع، ولا يُنشر ظهور).

**ولا يحتاج هذا الاختبارُ محرّكَ macOS Vision** — يختبر نصفَ المقارنة وحده (والنصفُ الآخر يُطفأ برسالة).
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

def test_the_three_rules_are_named_and_do_diverge():
    """حالةٌ مقيسةٌ تُعلن الفرق: المحرّكُ قد يُسقط الفاصلةَ فيقرأ أرقامًا مجرَّدة."""
    dropped = DIGITS_THOU
    kept = THOU_LAT
    assert lrp.canonical(dropped) != lrp.canonical(kept)          # شكلًا: يفترقان
    assert lrp.value_of(dropped) != lrp.value_of(kept)            # قيمةً: يفترقان
    assert lrp.digits_of(dropped) == lrp.digits_of(kept) == DIGITS_THOU   # أرقامًا: يتّفقان
    assert set(lrp.numeric_sets("")) == {"شكل", "قيمة", "أرقام"}


def test_numeric_sets_collects_from_free_text():
    got = lrp.numeric_sets(f"رصيد {THOU_AR_LINE} ثم {SMALL} بعده")
    assert Decimal(CANON_THOU) in got["قيمة"]
    assert Decimal(SMALL) in got["قيمة"]


THOU_AR_LINE = f"{_AR * 3}٬{_AR * 3}٫{_D * 2}"


def test_numeric_sets_keeps_the_rules_apart():
    """الخلطُ يكذب: «أرقام» تحمل المجرَّد، و«قيمة» تحمل المكسور — فلا تُسأل واحدةٌ عن الأخرى."""
    got = lrp.numeric_sets(THOU_LAT)
    assert got["قيمة"] == {Decimal(CANON_THOU)}
    assert got["شكل"] == {CANON_THOU}
    assert got["أرقام"] == {DIGITS_THOU}


def test_value_unifies_shapes_that_carry_the_same_number():
    """**عطبٌ مقيسٌ في مراجعة الجولة ٦٣:** الأداةُ كانت تُخزّن «قيمة» نصًّا ⇒ «٩٩٩» ≠ «٩٩٩٫٠٠».

    فالرقمُ نفسُه يفترق شكلًا ويتّفق قيمةً — ومن قارن النصَّ أهدر استرجاعًا كان بيده (٣٧.١٪ ⟶ ٤٨.٦٪).
    """
    plain, padded = f"{_D * 3}", f"{_D * 3}." + "0" * 2
    assert Decimal(plain) == Decimal(padded) and plain != padded
    assert lrp.numeric_sets(plain)["قيمة"] == lrp.numeric_sets(padded)["قيمة"] == {Decimal(plain)}
    assert lrp.numeric_sets(plain)["شكل"] != lrp.numeric_sets(padded)["شكل"]


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
    assert set(got["أرصدة"]) == {"شكل", "قيمة", "أرقام"}
    assert len(got["مبالغ"]["قيمة"]) == 1                    # القيمةُ الغائبة لا تُخترع


# ---------------------------------------------------------------- الصفحاتُ والقاعدة

def test_page_numbers_parse_strictly():
    assert lrp._parse_pages("1,9") == (1, 9)
    assert lrp._parse_pages(None) == lrp.PAGES
    with pytest.raises(SystemExit):
        lrp._parse_pages("أ")


def test_selected_pages_are_the_published_five_or_the_data_is_absent():
    """الحصيلةُ المنشورةُ تُعاد من القرص — أو يُعلَن غيابُ البيانات (لا تخمين)."""
    if not lrp.design_dir().exists():
        pytest.skip("لا بياناتُ تدريبٍ محلّيّة (الحزمةُ لا تُشحن)")
    pages = [int(lab["page"]) for _, lab, _ in lrp.selected()]
    assert pages == list(lrp.PAGES)


def test_list_mode_runs_without_the_engine(capsys):
    """`--list` يعمل بلا محرّكٍ وبلا قراءةِ صورة — فمن قاس يُعيد القياس في أيّ بيئة."""
    rc = lrp.main(["--list"])
    out = capsys.readouterr().out
    if lrp.design_dir().exists():
        assert rc == 0 and "المُؤهَّل" in out
    else:
        assert rc == 3 and "لا بياناتِ تدريبٍ محلّيّة" in out


def test_missing_engine_is_a_named_refusal_not_a_crash(monkeypatch):
    """غيابُ المحرّك يُطفئ الأداةَ برسالةٍ ورمز ٢ — لا انهيارٌ يُقرأ حكمًا."""
    monkeypatch.setattr(lrp, "ocr", lambda _p: (_ for _ in ()).throw(RuntimeError("غيرُ متاح")))
    monkeypatch.setattr(lrp, "design_dir", lambda *a, **k: ROOT / "tests")
    monkeypatch.setattr(lrp, "selected", lambda *a, **k: [(ROOT / "tests", {"page": 1}, [{"balance": 1}])])
    assert lrp.main([]) == 2
