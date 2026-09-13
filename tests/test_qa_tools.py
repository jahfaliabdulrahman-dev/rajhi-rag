"""Unit tests: deterministic QA tools over the verified rows (no network)."""

from decimal import Decimal

from statement_qa.qa_tools import make_qa_tools

def _rows():
    return [
        {"page": 1, "kind": "opening", "balance": Decimal("0.00"),
         "movement": None, "side": "", "ok": True,
         "desc": "الرصيد الافتتاحى", "date": None},
        {"page": 1, "kind": "txn", "balance": Decimal("300.00"),
         "movement": Decimal("300.00"), "side": "credit", "ok": True,
         "desc": "تحويل FRACCT/ من خالد", "date": None},
        {"page": 1, "kind": "txn", "balance": Decimal("200.00"),
         "movement": Decimal("100.00"), "side": "debit", "ok": True,
         "desc": "سحب الصراف الآلي AL SAFA", "date": None},
        {"page": 2, "kind": "opening", "balance": Decimal("200.00"),
         "movement": None, "side": "", "ok": True,
         "desc": "رصيد سابق", "date": None},
        {"page": 2, "kind": "txn", "balance": Decimal("150.00"),
         "movement": Decimal("50.00"), "side": "debit", "ok": True,
         "desc": "سحب الصراف الآلي", "date": None},
    ]

def _tools():
    return {t.name: t for t in make_qa_tools(_rows())}

def test_sum_movements_debit():
    out = _tools()["sum_movements"].invoke({"side": "مدين"})
    assert "150.00" in out          # 100 + 50
    assert "عدد الحركات = 2" in out

def test_sum_movements_credit():
    out = _tools()["sum_movements"].invoke({"side": "دائن"})
    assert "300.00" in out
    assert "عدد الحركات = 1" in out

def test_sum_movements_keyword():
    out = _tools()["sum_movements"].invoke({"side": "الكل", "keyword": "تحويل"})
    assert "300.00" in out and "عدد الحركات = 1" in out

def test_count_movements():
    out = _tools()["count_movements"].invoke({"side": "الكل", "keyword": "سحب الصراف"})
    assert "العدد = 2" in out

def test_balance_extremes():
    out = _tools()["balance_extremes"].invoke({})
    assert "أعلى رصيد = 300.00" in out
    assert "أدنى رصيد = 0.00" in out

def test_closing_balance():
    out = _tools()["closing_balance"].invoke({})
    assert "آخر رصيد = 150.00" in out
    assert "صفحة 2" in out

def test_page_summary():
    out = _tools()["page_summary"].invoke({"page": 2})
    assert "آخر رصيد = 150.00" in out
    assert "إجمالي مدين = 50.00" in out
    assert "عدد الصفوف = 2" in out

def test_search_rows():
    out = _tools()["search_rows"].invoke({"keyword": "سحب"})
    assert "2 حركة مطابقة" in out

def test_empty_selection_is_explicit():
    out = _tools()["sum_movements"].invoke({"side": "مدين", "keyword": "لايوجد"})
    assert "لا توجد حركات مطابقة" in out


def _thousand_rows():
    """Owner's live case: four rows of 9001.00, four different real types."""
    return [
        {"page": 7, "kind": "txn", "balance": Decimal("9001.00"),
         "movement": Decimal("9001.00"), "side": "debit", "ok": True,
         "desc": "التحويل من الحساب الصراف الآلي الى حساب خالد",
         "date": None, "type": "تحويل صادر"},
        {"page": 8, "kind": "txn", "balance": Decimal("9001.00"),
         "movement": Decimal("9001.00"), "side": "credit", "ok": True,
         "desc": "ايداع الصراف الالي Cash Deposit CA-TUQBA ,TUQBA",
         "date": None, "type": "إيداع نقدي (صراف آلي)"},
        {"page": 10, "kind": "txn", "balance": Decimal("9001.00"),
         "movement": Decimal("9001.00"), "side": "credit", "ok": True,
         "desc": "تحويل FRACCT/ من IBOUOA", "date": None, "type": "تحويل وارد"},
        {"page": 10, "kind": "txn", "balance": Decimal("676.00"),
         "movement": Decimal("9001.00"), "side": "debit", "ok": True,
         "desc": "سحب الصراف الآلي DAMMAM MAIN, DAMMAM", "date": None,
         "type": "سحب صراف آلي"},
    ]


def _thousand_tools():
    return {t.name: t for t in make_qa_tools(_thousand_rows())}


def test_thousand_scenario_counts_by_type():
    """The exact question that once got a muddled answer: كم سحب ب1000؟"""
    out = _thousand_tools()["count_movements"].invoke(
        {"tx_type": "سحب صراف آلي", "amount": 1000})
    assert "العدد = 1" in out
    out_all = _thousand_tools()["count_movements"].invoke({"amount": 1000})
    assert "العدد = 4" in out_all


def test_thousand_scenario_search_lists_all_types():
    out = _thousand_tools()["search_rows"].invoke({"amount": 1000})
    assert "4 حركة مطابقة" in out
    for typ in ("تحويل صادر", "إيداع نقدي (صراف آلي)",
                "تحويل وارد", "سحب صراف آلي"):
        assert typ in out


def test_type_filter_substring_matches_family():
    out = _thousand_tools()["count_movements"].invoke({"tx_type": "تحويل"})
    assert "العدد = 2" in out


def test_sum_by_type():
    out = _thousand_tools()["sum_movements"].invoke({"tx_type": "سحب صراف آلي"})
    assert "المجموع = 9001.00" in out