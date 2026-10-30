"""**قارئُ تاريخٍ واحد** — كلُّ من يقرأ خانةَ تاريخٍ يقرؤها بـ`contract_rows.normalize_date`.

**العلّةُ المقيسة (2026-10-30):** كانت في المشروع أربعةُ قرّاء، وكلٌّ يفوته ما يقرؤه غيره. على ٦٢٩
صفحةً حقيقيّة (٥٧٩١ خانة) قرأت القاعدةُ كلَّ الخانات، وفات قارئَ الترتيب ١٣٧ خانةً بشكل `dddd/dd/dd`
في ١٥ صفحةً كلُّ تواريخها كذلك ⇒ صفحاتٌ لا يراها فحصُ الترتيب، وخاناتٌ تُعرض بأرقامٍ غير أرقام
العمود. وقرارُ المالك (الحلّ ١): قارئٌ واحد، صحّتُه بـ`datetime.date` من المكتبة القياسيّة.
"""
from __future__ import annotations

import pytest

from statement_qa.contract_rows import normalize_date
from statement_qa.ordering import check_order

#: الأشكالُ التي تصل فعلًا: مفصولٌ لاتينيّ · مفصولٌ عربيّ-هنديّ · ممتدٌّ بلا فاصل · تقويمان في خانة.
CELLS = {
    "2026/01/27": "2026-01-27",
    "٢٠٢٦/٠١/٢٨": "2026-01-28",
    "۲۰۲۶۰۱۲۹": "2026-01-29",
    "١٤٤٧٠٨٠٩ 2026/01/30": "2026-01-30",
}


@pytest.mark.parametrize("cell, iso", CELLS.items())
def test_every_reader_of_a_date_cell_gives_the_same_date(cell, iso):
    """الجدولُ والتنزيل · فحصُ الترتيب · سنواتُ بوّابة الوكيل · وسيطُ الأداة — جوابٌ واحد."""
    from statement_qa.qa import _data_facts
    from statement_qa.qa_tools import _parse_date_arg
    from statement_qa.render import date_cell

    assert normalize_date(cell)[:2] == (iso, "ok")
    assert date_cell({"date": cell}) == iso.replace("-", "/")
    assert check_order({1: [cell]})["coverage"] == (1, 1)
    assert _data_facts([{"date": cell, "page": 1}])[0] == {int(iso[:4])}
    assert _parse_date_arg(cell, "من") == iso


def test_pages_whose_dates_all_carry_separators_are_checked_for_order():
    """الخطرُ الذي كان قائمًا: صفحةٌ مقلوبةٌ كلُّ تواريخها مفصولة كانت تمرّ دون أن تُرى."""
    res = check_order({1: ["2026/01/27", "٢٠٢٦/٠١/٢٨"],
                       2: ["2026/01/05", "2026/01/06"]})      # الصفحةُ الثانية ترجع
    assert res["coverage"] == (4, 4)
    assert [(c[0], c[1]) for c in res["cross"]] == [(1, 2)]


def test_a_day_its_month_does_not_have_is_not_a_date():
    """التحقّقُ اليدويّ (اليومُ ≤ ٣١) كان يقبل ٣١ في شهرٍ من ثلاثين يومًا — والمكتبةُ القياسيّة لا تقبله."""
    assert normalize_date("20230231")[:2] == ("", "implausible")
    assert normalize_date("2023/04/31")[:2] == ("", "implausible")
    assert normalize_date("2024/02/29")[:2] == ("2024-02-29", "ok")      # سنةٌ كبيسة
    assert normalize_date("2023/02/29")[:2] == ("", "implausible")


def test_no_second_date_reader_is_left_in_the_code():
    """الحدُّ نفسُه: لا دالّةَ أخرى تقرأ خانةَ تاريخ (أسماءُ القرّاء المحذوفة لا تعود)."""
    import statement_qa.legacy.arabic_digit_parser as legacy
    import statement_qa.ordering as ordering
    import statement_qa.vlm_reader as vlm_reader

    assert not hasattr(ordering, "parse_gregorian")
    assert not hasattr(vlm_reader, "_is_gregorian")
    assert not hasattr(legacy, "gdate")
