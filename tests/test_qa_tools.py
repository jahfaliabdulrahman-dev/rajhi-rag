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