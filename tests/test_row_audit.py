"""The row-level audit: a description that contradicts its own direction.

Why this file exists: the balance chain proves amounts and directions, and the
printed footer proves page totals — neither touches the free-text description
column. A row whose description was paired with the wrong amount therefore passed
every gate and reached a delivered workbook. These tests pin the check that
catches it, and its documented limit (debit↔debit shifts stay invisible).
"""
from __future__ import annotations

from decimal import Decimal

from statement_qa.row_audit import (
    clash_resolved, column_vs_chain, desc_direction_clash, nonzero_row_count,
    repair_balance_by_amount,
)


def _row(desc: str, side: str, mv: str, opening: bool = False) -> dict:
    return {"desc": desc, "side": side, "derived_movement": Decimal(mv),
            "opening": opening}


def test_a_pos_payment_read_as_a_credit_is_flagged():
    """The measured case (page 190): «مدفوعات نقاط البيع» with +100.00.

    A POS payment takes money OUT; the balance chain says this row went UP. One
    of the two is wrong and it cannot be the chain — so the description was
    paired with another row's amount.
    """
    rows = [_row("مدفوعات نقاط البيع (٦٣٨١٥٣١١", "credit", "100.00")]
    hits = desc_direction_clash(rows)
    assert len(hits) == 1
    assert hits[0]["row"] == 1
    assert "دائناً" in hits[0]["reason"]


def test_an_atm_withdrawal_read_as_a_credit_is_flagged():
    hits = desc_direction_clash([_row("سحب الصراف الآلي Ather Distict", "credit", "150.00")])
    assert len(hits) == 1


def test_the_same_labels_on_the_correct_side_are_silent():
    rows = [_row("مدفوعات نقاط البيع (٦٣٥", "debit", "22.00"),
            _row("سحب الصراف الآلي", "debit", "150.00"),
            _row("تحويل W-/FRACCT/365", "credit", "100.00"),
            _row("مدفوعات نقاط البيع الأخرى", "debit", "10.00")]
    assert desc_direction_clash(rows) == []


def test_an_undecided_row_is_never_accused():
    """side "" means the chain could not decide — that is not evidence."""
    assert desc_direction_clash([_row("مدفوعات نقاط البيع", "", "22.00")]) == []


def test_the_limit_is_documented_not_hidden():
    """A shift between two debit-only rows is invisible to this detector.

    «سحب الصراف الآلي» at 150.00 where the paper had a POS of 150.00 is a real
    misplacement this check cannot see — the docstring says so, and this test
    keeps that honest instead of letting the check look complete.
    """
    assert desc_direction_clash([_row("سحب الصراف الآلي", "debit", "150.00")]) == []


def test_nonzero_row_count_skips_openings_and_blank_rows():
    rows = [_row("رصيد افتتاحي", "", "0.00", opening=True),
            _row("مدفوعات نقاط البيع", "debit", "22.00"),
            {"desc": "لا حركة", "side": "", "derived_movement": Decimal("0")},
            {"desc": "بلا رصيد", "side": "", "derived_movement": None}]
    assert nonzero_row_count(rows) == 1


def test_balance_repair_needs_two_witnesses():
    """رقم واحد قُرئ خطأً: المبلغ المطبوع ورصيد السطر التالي يثبتان الصواب.

    حالة ص219 بالحرف: 55.62 ثم المطبوع 5.00 والرصيد المقروء 51.62 (الصواب 50.62)،
    ثم السطر التالي مطبوعه 22.00 ورصيده 28.62: 50.62 − 22.00 = 28.62 ✓
    """
    rows = [{"movement": None, "balance": Decimal("55.62"), "desc": "سابق"},
            {"movement": Decimal("5.00"), "balance": Decimal("51.62"), "desc": "نقاط بيع"},
            {"movement": Decimal("22.00"), "balance": Decimal("28.62"), "desc": "نقاط بيع"}]
    fixed = repair_balance_by_amount(rows)
    assert fixed[1]["balance"] == Decimal("50.62")
    assert "repaired" in fixed[1]
    assert fixed[0]["balance"] == Decimal("55.62")     # لا لمس لغير الخطأ
    assert fixed[2]["balance"] == Decimal("28.62")


def test_balance_repair_refuses_without_the_second_witness():
    """بلا شاهد ثانٍ لا إصلاح: قد يكون الخطأ في المبلغ لا في الرصيد."""
    rows = [{"movement": None, "balance": Decimal("55.62"), "desc": "سابق"},
            {"movement": Decimal("5.00"), "balance": Decimal("51.62"), "desc": "نقاط بيع"},
            {"movement": Decimal("900.00"), "balance": Decimal("28.62"), "desc": "لاحق"}]
    assert repair_balance_by_amount(rows)[1]["balance"] == Decimal("51.62")


def test_balance_repair_refuses_when_more_than_one_digit_differs():
    """خطأ محرف واحد فقط: فرق أكبر ليس خطأ قراءة رقمية."""
    rows = [{"movement": None, "balance": Decimal("9001.00"), "desc": "سابق"},
            {"movement": Decimal("5.00"), "balance": Decimal("900.00"), "desc": "نقاط بيع"},
            {"movement": Decimal("22.00"), "balance": Decimal("878.00"), "desc": "نقاط بيع"}]
    assert repair_balance_by_amount(rows)[1]["balance"] == Decimal("900.00")


def test_a_reread_is_accepted_only_when_the_clash_is_gone():
    """قاعدة قبول إعادة القراءة: زال التناقض ⇒ مقبولة.

    مُثبتة على الحالة الحقيقية (ص190): قراءة مخزّنة فيها صفّان يناقض وصفهما
    اتجاهَه، وإعادة قراءة واحدة صحيحة ⇒ التقرير يسجّل صفر تناقض والكاش يحمل
    القراءة الجديدة.
    """
    before = desc_direction_clash([_row("مدفوعات نقاط البيع", "credit", "100.00")])
    after = desc_direction_clash([_row("تحويل W-/FRACCT", "credit", "100.00")])
    assert clash_resolved(before, after) is True


def test_a_reread_that_keeps_the_clash_is_rejected():
    """إعادة قراءة تُبقي التناقض لا تُقبل — ولو طابقت أرقامَها."""
    before = desc_direction_clash([_row("مدفوعات نقاط البيع", "credit", "100.00")])
    after = desc_direction_clash([_row("مدفوعات نقاط البيع", "credit", "100.00")])
    assert clash_resolved(before, after) is False


def test_no_clash_means_nothing_to_accept():
    """بلا تناقض أصلاً لا تُقبل «إصلاحات»: الشرط كان موجوداً ثم زال."""
    assert clash_resolved([], []) is False


def test_the_printed_column_is_a_second_witness_not_a_judge():
    """عمود مطبوع يوافق السلسلة ⇒ شاهدان؛ ويخالفها ⇒ إشارة عيب لا ترجيح."""
    rows = [{"desc": "مدفوعات نقاط البيع", "side": "debit", "printed_col": "debit",
             "derived_movement": Decimal("22.00")},
            {"desc": "تحويل", "side": "credit", "printed_col": "credit",
             "derived_movement": Decimal("100.00")},
            {"desc": "مدفوعات نقاط البيع", "side": "credit", "printed_col": "debit",
             "derived_movement": Decimal("100.00")}]
    clashes = column_vs_chain(rows)
    assert len(clashes) == 1
    assert clashes[0]["row"] == 3
    assert clashes[0]["printed_col"] == "debit" and clashes[0]["chain_side"] == "credit"


def test_a_row_without_a_readable_column_is_never_accused():
    """غياب الشاهد ليس دليلاً: صفّ بلا عمود مقروء لا يدخل قائمة الخلاف."""
    assert column_vs_chain([{"desc": "س", "side": "debit", "printed_col": None,
                             "derived_movement": Decimal("5")}]) == []
    assert column_vs_chain([{"desc": "س", "side": "", "printed_col": "debit",
                             "derived_movement": None}]) == []
