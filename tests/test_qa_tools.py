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
    """نفسُ حالة المالك (أربعُ حركاتٍ بالمبلغ نفسه، أربعةُ أنواع) — بقيمةٍ **صناعيّة** محجوزة."""
    return [
        {"page": 7, "kind": "txn", "balance": Decimal("9008.00"),
         "movement": Decimal("9001.00"), "side": "debit", "ok": True,
         "desc": "التحويل من الحساب الصراف الآلي الى حساب خالد",
         "date": None, "type": "تحويل صادر"},
        {"page": 8, "kind": "txn", "balance": Decimal("9013.00"),
         "movement": Decimal("9001.00"), "side": "credit", "ok": True,
         "desc": "ايداع الصراف الالي Cash Deposit CA-TUQBA ,TUQBA",
         "date": None, "type": "إيداع نقدي (صراف آلي)"},
        {"page": 10, "kind": "txn", "balance": Decimal("9003.00"),
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
        {"tx_type": "سحب صراف آلي", "amount": 9001})
    assert "العدد = 1" in out
    out_all = _thousand_tools()["count_movements"].invoke({"amount": 9001})
    assert "العدد = 4" in out_all


def test_thousand_scenario_search_lists_all_types():
    out = _thousand_tools()["search_rows"].invoke({"amount": 9001})
    assert "4 حركة مطابقة" in out
    for typ in ("تحويل صادر", "إيداع نقدي (صراف آلي)",
                "تحويل وارد", "سحب صراف آلي"):
        assert typ in out


def test_type_filter_substring_matches_family():
    out = _thousand_tools()["count_movements"].invoke({"tx_type": "تحويل"})
    assert "العدد = 2" in out


def test_sum_by_type():
    out = _thousand_tools()["sum_movements"].invoke({"tx_type": "سحب صراف آلي"})
    assert "المجموع = 9,001.00" in out


def test_trace_records_tool_selections():
    """Evidence trace: every non-empty call records the rows it selected."""
    trace = []
    tools = {t.name: t for t in make_qa_tools(_rows(), trace=trace)}
    tools["count_movements"].invoke({"side": "مدين"})
    tools["search_rows"].invoke({"keyword": "سحب"})
    tools["balance_extremes"].invoke({})
    tools["closing_balance"].invoke({})
    tools["page_summary"].invoke({"page": 2})
    tools["page_rows"].invoke({"page": 2})
    assert [c["tool"] for c in trace] == [
        "count_movements", "search_rows", "balance_extremes",
        "closing_balance", "page_summary", "page_rows"]
    assert trace[0]["row_nos"] == [3, 5]      # the fixture's two debit rows
    assert trace[2]["row_nos"] == [2, 1]      # hi (300.00) then lo (0.00)
    assert trace[3]["row_nos"] == [5]         # last balance-bearing row
    assert trace[4]["row_nos"] == [4, 5]      # page-2 rows
    assert trace[5]["row_nos"] == [4, 5]      # page-2 rows, listed


def test_page_rows_answers_the_row_family_with_statement_wide_numbers():
    """**ثقبُ سطح الأدوات (P-5) يُغلق:** لم تكن أداةٌ تعرض صفوفَ صفحةٍ ⇒ عائلةُ `argmax_row`
    («أكبر حركةٍ في الصفحة») غيرُ قابلةٍ للإجابة. وهذه الأداةُ تعرضها **بترقيم الكشف** لا من ١ داخل
    الصفحة — وهو عطبٌ مقيسٌ سابقًا (REVIEW-48 · P-1: أُجيب `tops=[3]` ترقيمًا داخلَ الصفحة فسقط)."""
    out = _tools()["page_rows"].invoke({"page": 2})
    assert "(صفحة 2، صف 4)" in out and "(صفحة 2، صف 5)" in out
    assert "(صفحة 2، صف 1)" not in out             # لا ترقيمَ داخلَ الصفحة
    assert "50.00" in out and "150.00" in out       # المبلغُ والرصيدُ ⇒ الأكبرُ قابلٌ للحساب


def test_search_rows_can_be_scoped_to_one_page():
    """`search_rows(page=…)` — النصفُ الثاني من الثقب: البحثُ كان بلا فلترِ صفحة."""
    tools = _tools()
    assert "50.00" in tools["search_rows"].invoke({"page": 2})
    assert tools["search_rows"].invoke({"page": 1}).count("(صفحة 1") == 2   # حركتا الصفحة ١


def test_trace_skips_empty_selections():
    trace = []
    tools = {t.name: t for t in make_qa_tools(_rows(), trace=trace)}
    tools["sum_movements"].invoke({"side": "مدين", "keyword": "لايوجد"})
    assert trace == []


def test_used_rows_union_sorted_deduped():
    from statement_qa.qa_tools import used_rows_from_trace

    trace = [{"tool": "a", "row_nos": [5, 3]},
             {"tool": "b", "row_nos": [3, 9]}]
    assert used_rows_from_trace(trace) == [3, 5, 9]
    assert used_rows_from_trace([]) == []


def test_thousand_trace_union_covers_all_four():
    """The owner scenario, trace view: both tools' sets merge for the evidence."""
    from statement_qa.qa_tools import used_rows_from_trace

    trace = []
    tools = {t.name: t for t in make_qa_tools(_thousand_rows(), trace=trace)}
    tools["count_movements"].invoke({"tx_type": "سحب صراف آلي", "amount": 9001})
    tools["search_rows"].invoke({"amount": 9001})
    assert used_rows_from_trace(trace) == [1, 2, 3, 4]