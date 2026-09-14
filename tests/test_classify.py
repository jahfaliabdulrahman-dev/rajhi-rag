"""Unit tests: deterministic type classification (no network)."""

from decimal import Decimal

from statement_qa.classify import annotate_types, classify


def test_atm_withdrawals_real_spellings():
    """All three printed spellings from the real sample -> one type."""
    cases = [
        "سحب الصراف الآلي AL RAKAN BUILDING, KHOBAR",
        "سحب الصراف الألي AL SAFA BRANCH ,JEDDAH",
        "سحب الصراف الالى AL SAFA BRANCH ,JEDDAH",
        "سحب الصراف الألي YANBU STREET ATM, AL KHOBAR",
        "سحب الصراف الآلي",
    ]
    for desc in cases:
        assert classify(desc, "debit") == "سحب صراف آلي", desc


def test_transfers_direction_split():
    # Synthetic values only — real account numbers/names never enter the repo.
    d = "تحويل FRACCT/١٠٠٠٥٧٦١FR-محمد احمد IBOUOA۰۲"
    assert classify(d, "credit") == "تحويل وارد"
    assert classify(d, "debit") == "تحويل صادر"
    assert classify(d, "") == "تحويل"


def test_transfer_via_atm_is_transfer_not_withdrawal():
    """'التحويل ... الصراف الالي' contains صراف — must NOT become a withdrawal."""
    out = classify(
        "التحويل من الحساب الصراف الآلي الى حساب سعد ابراهيم العلي",
        "debit")
    assert out == "تحويل صادر"
    out2 = classify(
        "التحويل للحساب الصراف الالي من حساب سلطان علي احمد شراحيلي",
        "credit")
    assert out2 == "تحويل وارد"


def test_cash_deposit():
    assert classify(
        "ايداع الصراف الالي Cash Deposit CA-TUQBA ,TUQBA",
        "credit") == "إيداع نقدي (صراف آلي)"


def test_pos_payments():
    assert classify(
        "مدفوعات نقاط البيع (5525-2547 ۳) KIA MOTORES S.A, DAMMAM, SA",
        "debit") == "مشتريات (نقاط بيع)"


def test_sadad_bills_and_license_fees():
    assert classify(
        "فواتير نظام سداد A#٩٩٩-٠٠٠١١١٢٢٢ SPOUD١٠١",
        "debit") == "فواتير ومدفوعات سداد"
    assert classify(
        "مدفوعات سداد رخص القيادة A حساب سالم محمد المطيري",
        "debit") == "فواتير ومدفوعات سداد"


def test_salary_and_fallbacks():
    assert classify("راتب شهر يناير", "credit") == "إيداع راتب"
    assert classify("", "") == "غير مصنّف"
    assert classify("نص غريب تماما لا كلمات معروفة", "debit") == "غير مصنّف"


def test_synthetic_demo_vocabulary():
    """The demo fixture's descriptions, each with its true direction."""
    cases = {
        "تحويل وارد - شركة أ": ("credit", "تحويل وارد"),
        "تحويل صادر - مطعم ب": ("debit", "تحويل صادر"),
        "سحب صراف آلي - الرياض": ("debit", "سحب صراف آلي"),
        "راتب شهري - جهة العمل": ("credit", "إيداع راتب"),
        "فاتورة كهرباء - الشركة السعودية": ("debit", "فواتير خدمات"),
        "شراء نقاط بيع - سوبرماركت د": ("debit", "مشتريات (نقاط بيع)"),
        "رسوم صيانة الحساب": ("debit", "رسوم وعمولات"),
        "إيداع نقدي - فرع الوديقي": ("credit", "إيداع"),
    }
    for desc, (side, want) in cases.items():
        assert classify(desc, side) == want, desc


def test_annotate_never_touches_numbers():
    """Invariant: classification is a label layer — chain fields stay byte-equal."""
    rows = [
        {"kind": "opening", "balance": Decimal("0.00"), "movement": None,
         "side": "", "ok": True, "desc": "الرصيد الافتتاحى"},
        {"kind": "txn", "balance": Decimal("300.00"), "movement": Decimal("300.00"),
         "side": "credit", "ok": True, "desc": "تحويل من خالد"},
        {"kind": "txn", "balance": Decimal("200.00"), "movement": Decimal("100.00"),
         "side": "debit", "ok": True, "desc": "سحب الصراف الآلي AL SAFA"},
    ]
    snapshot = [(r["balance"], r["movement"], r["side"], r["ok"]) for r in rows]
    annotate_types(rows)
    assert [r["type"] for r in rows] == ["رصيد افتتاحي", "تحويل وارد", "سحب صراف آلي"]
    assert [(r["balance"], r["movement"], r["side"], r["ok"]) for r in rows] == snapshot
