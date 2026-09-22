"""Unit tests: parser + verifier (no API key, no network)."""

from decimal import Decimal

from statement_qa.parser import _to_decimal, normalize_digits, parse_text
from statement_qa.verifier import verify_statement


# ---------- digit normalization ----------

def test_normalize_arabic_indic_digits():
    assert normalize_digits("١٢٣٫٤٥") == "123.45"
    assert normalize_digits("١٬٢٣٤") == "1,234" or normalize_digits("١٬٢٣٤") == "1,234"


def test_to_decimal_arabic_style():
    assert _to_decimal("1.234,56") == Decimal("1234.56")
    assert _to_decimal("1,234.56") == Decimal("1234.56")
    assert _to_decimal("1234.56") == Decimal("1234.56")
    assert _to_decimal("") == Decimal("0")


# ---------- parser ----------

def _mk_csv_text(rows: list[str]) -> str:
    return "\n".join(rows)


def test_parse_western_rows():
    text = _mk_csv_text([
        "[PAGE 1]",
        "01/01/2026 رصيد افتتاحي 9001.00",
        "02/01/2026 تحويل صادر مطعم ب 120.50 9879.50",
    ])
    df = parse_text(text)
    assert df.height == 2
    assert df["balance"][1] == Decimal("9879.50")
    assert df["debit"][1] == Decimal("120.50")


def test_parse_arabic_indic_rows():
    # ٠١/٠١/٢٠٢٦  رصيد افتتاحي  9001.00
    text = _mk_csv_text([
        "٠١/٠١/٢٠٢٦ رصيد افتتاحي 9001.00",
        "٠٢/٠١/٢٠٢٦ تحويل وارد شركة أ 9001.00 ١9001.00",
    ])
    df = parse_text(text)
    assert df.height == 2
    # Chain arbitration (load_statement contract): 10000+1500=11500 ✓ → credit.
    # parse_text returns the raw debit-default; fix_sides_by_chain flips it.
    from statement_qa.parser import fix_sides_by_chain
    fixed = fix_sides_by_chain(df)
    assert fixed["credit"][1] == Decimal("9001.00")
    assert fixed["debit"][1] == Decimal("0.00")
    assert fixed["balance"][1] == Decimal("19001.00")


def test_parse_empty():
    assert parse_text("").is_empty()


# ---------- verifier ----------

def _rows(balances, debits, credits):
    lines = ["01/01/2026 رصيد افتتاحي " + balances[0]]
    for i, (b, d, c) in enumerate(zip(balances[1:], debits, credits), start=2):
        parts = [f"{i:02d}/01/2026 حركة"]
        if d:
            parts.append(d)
        else:
            parts.append("0.00")
        if c:
            parts.append(c)
        else:
            parts.append("0.00")
        parts.append(b)
        lines.append(" ".join(parts))
    return "\n".join(lines)


def test_verify_chain_ok():
    text = _rows(
        ["9001.00", "9879.50", "11379.50"],
        ["120.50", "0.00"],
        ["0.00", "9001.00"],
    )
    rep = verify_statement(parse_text(text))
    assert rep["balance_ok"] is True
    assert rep["balance_chain_ok"] is True
    assert rep["suspect_rows"] == []


def test_verify_chain_broken_flags_suspect():
    text = _rows(
        ["9001.00", "9879.50", "11379.60"],   # last balance corrupted (OCR error)
        ["120.50", "0.00"],
        ["0.00", "9001.00"],
    )
    rep = verify_statement(parse_text(text))
    assert rep["balance_chain_ok"] is False
    assert rep["suspect_rows"] == [2]


# ---------- vlm_reader amount parser (629-page inheritance regressions) ----------

from statement_qa.vlm_reader import _parse_amount  # noqa: E402


def test_parse_amount_comma_decimal():
    # Old prints: comma IS the decimal point with exactly 2 digits after it.
    assert _parse_amount("٣٠٠,٠٠") == Decimal("300.00")
    assert _parse_amount("١٠٠,٠٠") == Decimal("100.00")
    assert _parse_amount("۲۴۵,۰۰") == Decimal("245.00")   # Persian digits


def test_parse_amount_printed_zero_as_dots():
    # Old pages print a zero balance as dots — must be 0, never None.
    assert _parse_amount(".,..") == Decimal("0")


def test_parse_amount_lost_dot():
    assert _parse_amount("٦١,١٦٥١٢") == Decimal("61165.12")


def test_parse_amount_trailing_minus():
    # Negative balances print the minus at the END — sign must survive.
    assert _parse_amount("١١٩.٠٠-") == Decimal("-119.00")
    assert _parse_amount("۳۰۰,۰۰-") == Decimal("-300.00")


def test_parse_amount_none_and_empty():
    assert _parse_amount(None) is None
    assert _parse_amount("") is None
    assert _parse_amount("سحب الصراف") is None
