"""التصديقُ الخارجيّ: مقابلةُ ثلاثةِ أرقامٍ مطبوعة — والحالاتُ أربعٌ لا اثنتان.

الاختبارُ **بلا شبكة** عمداً: منطقُ المقابلة يُختبر على أرقامٍ معلومة، والنداءُ المدفوع
يبقى خارجَ الاختبار. وأهمُّ ما يحرسه هذا الملفُّ: أن **«غيرُ مقروء» لا يُحسب اتفاقاً** —
لأن عدَّ ما لا يُثبت نجاحاً هو الصنفُ الذي كلَّفنا في هذا المشروع أكثر من غيره.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from tools.oracle_confirm import (  # noqa: E402
    assert_not_published, compare_footers, rule_of_three, wilson,
)

PARSED = {"debits": "7754.00", "credits": "13400.00", "balance": "5646.00"}


def test_three_printed_cells_matching_are_counted_and_named():
    got = compare_footers(PARSED, dict(PARSED))
    assert (got["agree"], got["compared"], got["verdict"], got["differ"]) == (3, 3, "مطابق", [])
    assert all(c["verdict"] == "مطابق" for c in got["cells"])


def test_a_single_field_difference_is_named_not_swallowed():
    oracle = {**PARSED, "balance": "5647.00"}
    got = compare_footers(PARSED, oracle)
    assert got["differ"] == ["balance"] and got["verdict"] == "مختلف" and got["agree"] == 2
    cell = [c for c in got["cells"] if c["field"] == "balance"][0]
    assert cell["ours"] == "5646.00" and cell["oracle"] == "5647.00"


def test_an_unreadable_field_is_neither_agreement_nor_difference():
    """جوهرُ الملف: ما لا يُقرأ **لا يُعدّ نجاحاً** — ولا يُسقط الصفحةَ إلى فشل كاذب."""
    got = compare_footers(PARSED, {**PARSED, "debits": None})
    assert got["unread"] == 1 and got["agree"] == 2 and got["compared"] == 2
    assert got["differ"] == [] and got["verdict"] == "مطابق"  # لا اختلافَ مقيساً
    assert [c["verdict"] for c in got["cells"]] == ["غيرُ مقروء", "مطابق", "مطابق"]


def test_an_absent_printed_footer_is_declared_absent_not_matched():
    got = compare_footers({}, {})
    assert got["absent"] == 3 and got["compared"] == 0 and got["verdict"] == "غائب"


def test_arabic_printed_digits_compare_equal_to_latin_parsed_ones():
    """الرقمُ المطبوع عربيٌّ والمقروءُ لدينا لاتينيّ — والمقارنةُ بالأرقام لا بالحروف."""
    arabic = {"debits": "٧٧٥٤٫٠٠", "credits": "١٣٤٠٠٫٠٠", "balance": "٥٦٤٦٫٠٠"}
    got = compare_footers(PARSED, arabic)
    assert got["verdict"] == "مطابق" and got["agree"] == 3


# ─────────────────────────────────────────────────────────────────────────────
# المجالُ الإحصائي: عند «صفر اختلافات» لا يُقال «دقّة 100٪» — وهذا ما يحرسه الاختبار
# ─────────────────────────────────────────────────────────────────────────────

def test_wilson_refuses_to_call_perfection_a_certainty():
    """جوهرُ الدرس: التقريبُ الطبيعيّ عند p̂=1 يعطي مجالاً بعرض **صفر** ⇒ «دقّةٌ مطلقة»، وهي كذب."""
    lo, hi = wilson(20, 20)
    assert hi == 1.0
    assert lo < 1.0, "مجالٌ بعرض صفر عند الاتفاق التام = ادّعاءُ يقينٍ لا يملكه القياس"
    # وكلّما كثُر n ضاق المجالُ من جهة الدنيا (المعلومُ أكثرُ ⇒ الشكُّ أقلّ)
    assert wilson(200, 200)[0] > wilson(20, 20)[0] > wilson(2, 2)[0]


def test_wilson_stays_inside_the_unit_interval_and_is_ordered_in_k():
    for n in (5, 50, 500):
        prev = -1.0
        for k in range(n + 1):
            lo, hi = wilson(k, n)
            assert 0.0 <= lo <= k / n <= hi <= 1.0
            assert lo >= prev - 1e-12
            prev = lo
    assert wilson(0, 0) == (0.0, 1.0)  # لا قياسَ ⇒ لا ادّعاء


def test_rule_of_three_gives_the_honest_zero_failure_bound():
    """صفرُ اختلافاتٍ في n ⇒ معدّلُ الخطأ < 3/n بثقة 95٪ — وهذي هي الصياغةُ التي تُقال."""
    assert round(rule_of_three(1887), 6) == round(3 / 1887, 6)
    assert rule_of_three(3) == 1.0
    assert rule_of_three(0) != rule_of_three(0)  # NaN: بلا n لا حدّ (ولا يُطبع صفراً)


# ─────────────────────────────────────────────────────────────────────────────
# حارسُ الخصوصية: شهادةُ التصديق تحمل تذييلاتِ كشفٍ مصرفيّ ⇒ لا تُدفع إلى مستودعٍ عامّ
# ─────────────────────────────────────────────────────────────────────────────

def test_the_oracle_refuses_to_write_where_git_would_publish_it():
    """حارسٌ يُجرَّب سقوطُه: مسارٌ متتبَّعٌ يُرفض بالاسم، ومسارٌ مُهمَلٌ يمرّ."""
    ignored = PROJ / "data/eval_pack/oracle-probe.json"        # داخل .gitignore ✓
    assert_not_published(ignored)                              # لا يرفع
    tracked = PROJ / "docs/evidence/oracle-probe.json"         # متتبَّع ⇒ يُنشر
    with pytest.raises(SystemExit) as err:
        assert_not_published(tracked)
    assert "ليس مُهمَلاً" in str(err.value)
    # وخارج المستودع لا شأنَ للحارس (لا يدفع شيئاً).
    assert_not_published(Path("/tmp/oracle-probe.json"))



# ─────────────────────────────────────────────────────────────────────────────
# لا يعود `tools` حزمةَ namespace فتُحجب بـPYTHONPATH غريب (عطبٌ قِيس ثلاث مرّات)
# ─────────────────────────────────────────────────────────────────────────────

def test_the_project_tools_package_is_regular_and_resolves_inside_the_project():
    """حارسُ الصنف: `tools` **نظامية** (`__file__` معرَّف) **و**تُحلّ من المشروع.

    كان `tools` بلا `__init__.py` فيُدمج مع `tools/` آخرَ على `sys.path` (بيئةُ التشغيل تحمل
    `PYTHONPATH=…/.hermes/hermes-agent`) ⇒ 9 أخطاء جمع منها `No module named 'tools.eval_pack'`،
    بلا تفسيرٍ في السجلّ. الاختبارُ يمنع رجوعَها: namespace لا تُحلّ بترتيبٍ بيئيّ بل بترتيب sys.path.
    """
    import tools as tools_pkg
    assert tools_pkg.__file__ is not None, "tools حزمةُ namespace — تُحجب بترتيب sys.path"
    resolved = Path(tools_pkg.__file__).resolve().parent
    assert resolved == (PROJ / "tools").resolve(), f"tools تُحلّ من مكانٍ آخر: {resolved}"
