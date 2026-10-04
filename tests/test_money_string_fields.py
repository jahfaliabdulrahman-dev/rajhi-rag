"""بوّابةُ صنف «مالٌ نصّيّ»: العقدُ يخزّن المال `TEXT` ⇒ أدواتُ الوكيل يجب ألّا تسقط عليه.

**العطبُ الذي تمنعه (كُشف بمسبارٍ حقيقيّ، لا بمراجعة):** `_MONEY.format(str)` يرفع
`ValueError: Unknown format code 'f'` ⇒ فسقطت `page_summary` في **ستّة مواضع**، والمسارُ نزل إلى
البديل صامتًا. والباقي في المستودع الآن حوّلٌ واحد `_m()` تمرّ منه كلُّ حقول المال.
"""

from __future__ import annotations

from decimal import Decimal

from statement_qa.qa_tools import _m, make_qa_tools

ROWS = [
    {"page": 1, "row": 1, "row_no": 1, "description": "شراء", "debit": "10.00", "credit": None,
     "balance": "100.00", "amount": "10.00", "kind": "txn", "side": "debit",
     "movement": Decimal("10.00"), "derived_movement": "10.00", "opening": False, "proven": True},
    {"page": 1, "row": 2, "row_no": 2, "description": "إيداع", "debit": None, "credit": "15.00",
     "balance": "115.00", "amount": "15.00", "kind": "txn", "side": "credit",
     "movement": Decimal("15.00"), "derived_movement": "15.00", "opening": False, "proven": True},
]


def test_the_money_convertor_accepts_text_and_arithmetic_alike() -> None:
    assert _m("100.00") == "100.00" and _m("1234.5") == "1,234.50"
    assert _m(None) == "—" and _m("") == "—"
    assert _m("غير رقم") == "غير رقم", "قيمةٌ ليست رقمًا تُعرَض كما هي — لا تُبتلع"


def test_the_page_summary_tool_does_not_fall_on_text_money() -> None:
    """**ولا سقوط:** صفوفٌ بمبالغ نصّيّة (كما في العقد) ⇒ الأداةُ تُجيب، والرصيدُ يظهر فيها."""
    trace: list[dict] = []
    tools = make_qa_tools(ROWS, trace=trace, footers={})
    page_summary = next(t for t in tools if getattr(t, "name", "") == "page_summary")
    out = page_summary.invoke({"page": 1})
    assert "100.00" in out and "115.00" in out, f"الرصيدُ النصّيّ لم يظهر: {out[:160]}"
