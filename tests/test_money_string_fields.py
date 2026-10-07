"""بوّابةُ صنف «مالٌ نصّيّ»: العقدُ يخزّن المال `TEXT` ⇒ أدواتُ الوكيل يجب ألّا تسقط عليه.

**العطبُ الذي تمنعه (كُشف بمسبارٍ حقيقيّ، لا بمراجعة):** `_MONEY.format(str)` يرفع
`ValueError: Unknown format code 'f'` ⇒ فسقطت `page_summary` في **ستّة مواضع**، والمسارُ نزل إلى
البديل صامتًا. والباقي في المستودع الآن حوّلٌ واحد `_m()` تمرّ منه كلُّ حقول المال.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

# حارسُ التبعيّات (قاعدةٌ مقيسة: بلا LangChain يسقط الاستيرادُ بدل أن يُتخطّى ⇒ CI أحمر بلا عطب)
pytest.importorskip("langchain")

from statement_qa.qa_tools import _m, make_qa_tools       # noqa: E402

ROWS = [
    {"page": 1, "row": 1, "row_no": 1, "description": "شراء", "debit": "10.00", "credit": None,
     "balance": "100.00", "amount": "10.00", "kind": "txn", "side": "debit",
     "movement": "10.00", "derived_movement": "10.00", "opening": False, "proven": True},
    {"page": 1, "row": 2, "row_no": 2, "description": "إيداع", "debit": None, "credit": "15.00",
     "balance": "115.00", "amount": "15.00", "kind": "txn", "side": "credit",
     "movement": "15.00", "derived_movement": "15.00", "opening": False, "proven": True},
]


def _tool(rows: list[dict], name: str):
    """أداةٌ من المجموعة باسمها — نداءٌ واحدٌ لا تكرارَ في كلّ ضابط."""
    tools = make_qa_tools(rows, trace=[], footers={})
    return next(t for t in tools if getattr(t, "name", "") == name)


def test_the_money_convertor_accepts_text_and_arithmetic_alike() -> None:
    assert _m("100.00") == "100.00" and _m("1234.5") == "1,234.50"
    assert _m(None) == "—" and _m("") == "—"
    assert _m("غير رقم") == "غير رقم", "قيمةٌ ليست رقمًا تُعرَض كما هي — لا تُبتلع"
    # **وموضعُه واحد (R93-7):** التنسيقُ والتحويلُ في `statement_qa.money` لا نسخةً في الأدوات،
    # والشرطةُ صيغةُ عرضٍ تُطلَب صراحةً (`dash`) بدل أن تكون افتراضًا ثانيًا في ملفٍّ آخر.
    from statement_qa.money import amount, money
    assert money("1234.5") == "1,234.50" and money(None) == "" and money(None, dash="—") == "—"
    assert amount("1,234.50") == Decimal("1234.50") and amount("غير رقم") is None
    assert amount(None) is None and amount("") is None


def test_the_extremes_are_compared_by_value_not_by_text() -> None:
    """**R93-7 (مقيس):** «أعلى رصيد» كان يُختار بمقارنة **النصّ** نصًّا.

    بمبالغ `9.00 · 10.00 · 120.00` كان الجوابُ «أعلى = 9.00» و«أدنى = 10.00» — **جوابٌ خاطئ
    يُسلَّم**، وضابطُه القديم كان يقيس غيابَ `TypeError` فقط فيمرّ عليه. وهذا الضابطُ **يقيس القيمةَ**.
    """
    rows = [{**ROWS[0], "row": i + 1, "row_no": i + 1, "balance": b,
             "description": f"حركة {i + 1}"}
            for i, b in enumerate(("9.00", "10.00", "120.00"))]
    out = _tool(rows, "balance_extremes").invoke({})
    high, low = str(out).split("|")
    assert "120.00" in high, f"الأعلى بالحساب 120.00 لا 9.00 (مقارنةُ نصّ): {out}"
    assert "9.00" in low, f"الأدنى بالحساب 9.00 لا 10.00 (مقارنةُ نصّ): {out}"


def test_an_unreadable_balance_is_counted_not_swallowed() -> None:
    """**ولا يُبتلع غيرُ الرقميّ:** رصيدٌ لا يُقرأ رقمًا **يُعدّ** ويُقال بعدده، ولا يُخمَّن مكانُه."""
    rows = [*ROWS, {**ROWS[0], "row": 3, "row_no": 3, "balance": "غيرُ مقروء"}]
    out = str(_tool(rows, "balance_extremes").invoke({}))
    assert "غيرُ مقروء" in out and "1 رصيدًا" in out, f"غيرُ المقروء لم يُعدّ: {out}"


def test_the_page_summary_tool_does_not_fall_on_text_money() -> None:
    """**ولا سقوط:** صفوفٌ بمبالغ نصّيّة (كما في العقد) ⇒ الأداةُ تُجيب، والرصيدُ يظهر فيها."""
    trace: list[dict] = []
    tools = make_qa_tools(ROWS, trace=trace, footers={})
    by_name = {getattr(t, "name", ""): t for t in tools}
    out = by_name["page_summary"].invoke({"page": 1})
    assert "100.00" in out and "115.00" in out, f"الرصيدُ النصّيّ لم يظهر: {out[:160]}"
    # **الصنفُ لا عيّنةٌ منه (قِيس):** كلُّ أداةٍ ماليّة تُستدعى بحركةٍ **نصّيّة** كما يفرض العقد
    for name, arg in (("sum_movements", {}), ("page_rows", {"page": 1}),
                      ("balance_extremes", {}), ("closing_balance", {})):
        tool = by_name.get(name)
        assert tool is not None, f"أداةٌ غابت: {name}"
        res = tool.invoke(arg)
        assert "TypeError" not in str(res) and "ValueError" not in str(res), f"{name} سقطت: {res}"
