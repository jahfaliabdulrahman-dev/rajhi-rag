"""قانون التواريخ: المصدر معلن، والصفّ لا يأخذ تاريخ جاره."""
from statement_qa.row_dates import (parse_cell, resolve, text_dates,
                                    is_not_movement)


def test_cell_dates_come_in_two_shapes_and_both_are_dates():
    """القارئ يعيد ``20160808`` و ``2016/08/08`` — ورفضُ إحداهما نقصٌ كاذب.

    هذا العيب وقع فعلاً: 117 صفّاً ظُنّت بلا تاريخ لأن الخانة كانت بصيغة فواصل.
    """
    assert parse_cell("20160808") == "20160808"
    assert parse_cell("2016/08/08") == "20160808"
    assert parse_cell("2016/8/8") == "20160808"
    assert parse_cell("٢٠١٦/٠٨/٠٨") == "20160808"
    assert parse_cell("2016-08-08") == "20160808"


def test_non_dates_are_refused_rather_than_guessed():
    assert parse_cell("") == ""
    assert parse_cell("None") == ""
    assert parse_cell("2016/13/45") == ""        # شهر ويوم خارج المدى
    assert parse_cell("14450324") == ""          # هجري، ليس ميلادياً
    assert parse_cell("١٤٤٥٠٣٢٤") == ""


def test_the_date_is_taken_from_the_same_row_only():
    """التاريخ من نصّ السطر **نفسه** — وهو مطبوع في الورق، لا من الصفّ المجاور."""
    row = {"date": None, "desc": "حوالات سريع الواردة ۲۰۱۸۱۲۰۲ ١٤٤٠٠٣٢٤ أحمد"}
    v = resolve(row)
    assert v["date"] == "20181202" and v["date_source"] == "text"


def test_a_row_without_a_date_says_so():
    v = resolve({"date": "", "desc": "سحب الصراف الألي"})
    assert v["date"] is None and v["date_source"] == "missing"


def test_opening_balance_rows_are_not_transactions():
    for desc in ("الرصيد الافتتاحى", "الرصيد الافتتاحي", "الحوالات الواردة"):
        assert is_not_movement(desc)
        assert resolve({"date": None, "desc": desc})["date_source"] == "not_a_movement"


def test_a_cell_that_contradicts_the_row_text_is_flagged_not_hidden():
    """شاهدان للتاريخ: الخانة والنصّ — واختلافهما يُعلن إشارةً لا يُكتم."""
    row = {"date": "20241120", "desc": "شراء انترنت ۲۰۲۴۱۱۲٥"}
    v = resolve(row)
    assert v["date"] == "20241120" and v["date_text_mismatch"] is True


def test_hijri_only_rows_are_not_turned_into_gregorian_by_guesswork():
    """لا تحويل بلا تقويم: الهجري في النصّ يُترك — والميلادي هو ما نأخذه."""
    greg, hij = text_dates("تحويل ١٤٤٣٠٤١٧ 20211121")
    assert greg == "20211121" and hij == "14430417"
