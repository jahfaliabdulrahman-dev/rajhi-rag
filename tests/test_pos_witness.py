"""الشاهد الموضعي: تُختبر القطع الحتمية فقط — بلا API وبلا كلفة.

أرقام الشاهد الحقيقية (ص621) مستعملة كحقيقة أرضية: السلسلة والهندسة اتفقتا 10/10
بينما أخطأ قارئنا في صفّ واحد — فالاختبار يثبّت أن الاتفاق ليس صدفةً في العيّنة.
"""
import numpy as np
from decimal import Decimal

from statement_qa.pos_witness import (INK_MIN, assign_column, chain_side,
                                      compare_with_chain, parse_lines, snap_point,
                                      to_decimal)

# أعمدة ص621 كما أعادها الشاهد (نسبية) — والحقيقة الأرضية من الورق بعينه
COLS_621 = {"debit_x": 0.440, "credit_x": 0.306, "balance_x": 0.142}
# الأرصدة المطبوعة في الورق، والأعمدة كما أثبتها الحبر والعين
ROWS_621 = [
    {"x": 0.440, "balance": "١,١٧٤.٥٧"},
    {"x": 0.440, "balance": "٧٧٤.٠١"},
    {"x": 0.440, "balance": "٥٦١.٧٨"},
    {"x": 0.306, "balance": "٨٦١.٧٨"},
    {"x": 0.306, "balance": "٩١١.٧٨"},
    {"x": 0.440, "balance": "٨٢٦.٧٨"},
    {"x": 0.440, "balance": "٤٢٦.٣٥"},
    {"x": 0.306, "balance": "٤٧٦.٣٥"},
    {"x": 0.440, "balance": "٤٢٦.٣٥"},      # ← صفّ ٩: الخلاف الذي أخطأ فيه القارئ
    {"x": 0.440, "balance": "٢٥.٩٢"},
    {"x": 0.440, "balance": "١١.٩٢"},
]


def test_the_line_format_survives_a_truncated_answer():
    """JSON انقطع مرتين وضاع الجواب؛ السطري يُفقد سطراً ويُبقي الباقي."""
    text = ("COLS|debit_x=0.440|credit_x=0.306|balance_x=0.142\n"
            "ROW|٢٠٢٤١١١٨|0.440|0.293|٤٠٠.٥٦|١,١٧٤.٥٧\n"
            "ROW|٢٠٢٤١١١٨|0.440|0.315|٤٠٠.٥٦|٧٧٤.٠١\n"
            "ROW|٢٠٢٤١١١٨|0.4")                       # سطر مقطوع
    cols, rows = parse_lines(text)
    assert cols["debit_x"] == 0.440 and len(rows) == 2
    assert rows[0]["amount"] == "٤٠٠.٥٦"


def test_junk_lines_are_ignored_not_guessed():
    cols, rows = parse_lines("COLS|debit_x=abc|credit_x=0.3\nتمام\nROW|١\nROW|أ|ب|ج|د|هـ")
    assert "debit_x" not in cols and cols["credit_x"] == 0.3
    assert rows == []


def test_the_column_is_derived_from_horizontal_position_only():
    assert assign_column(0.44, COLS_621) == "debit"
    assert assign_column(0.31, COLS_621) == "credit"
    assert assign_column(0.99, COLS_621) == "debit"      # الأقرب لا الأبعد
    assert assign_column(0.5, {}) is None


def test_chain_side_reads_arabic_digits_and_commas():
    assert chain_side("١,١٧٤.٥٧", "٧٧٤.٠١") == "debit"     # انخفض ⇒ مدين
    assert chain_side("٤٢٦.٣٥", "٤٧٦.٣٥") == "credit"      # ارتفع ⇒ دائن
    assert chain_side("١٠٠.٠٠", "١٠٠.٠٠") is None
    assert to_decimal("٠٫٥٠") == Decimal("0.50")           # «٫» فاصلة عشرية لا تُرمى
    assert to_decimal("١٬٢٣٤.٥٠") == Decimal("1234.50")
    assert to_decimal("غير مقروء") is None


def test_geometry_agrees_with_the_chain_on_the_real_page_and_catches_row_nine():
    v = compare_with_chain(ROWS_621, COLS_621)
    assert v["clash"] == 0 and v["agree"] == 10            # عشرة أزواج متعاقبة
    assert v["undetermined"] == 0
    # والصفّ التاسع — الذي أخطأ فيه قارئنا — يُسنَد إلى مدين بالهندسة
    assert assign_column(ROWS_621[8]["x"], COLS_621) == "debit"


def test_geometry_disagreement_is_reported_with_numbers_not_hidden():
    broken = [dict(r) for r in ROWS_621]
    broken[4]["x"] = 0.440                                 # صفّ دائن نُسب لعمود مدين
    v = compare_with_chain(broken, COLS_621)
    assert v["clash"] >= 1 and v["clashes"][0]["chain"] == "credit"


def test_snap_moves_an_approximate_claim_onto_real_ink():
    """إحداثيات النموذج تقريبية (35–105 بكسل): السنّ هو ما يجعلها دليلاً."""
    arr = np.full((400, 400), 250, dtype=np.uint8)
    arr[190:215, 250:330] = 60                             # كتلة حبر حقيقية
    ink = lambda x0, y0, x1, y1: (                            # noqa: E731
        float((arr[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] < 185).mean())
        if arr[max(0, y0):max(0, y1), max(0, x0):max(0, x1)].size else 0.0)
    claim_x, claim_y = 250 - 95, 200                       # إزاحة 95 بكسل (مقيسة)
    before = ink(claim_x - 60, claim_y - 13, claim_x + 60, claim_y + 13)
    sx, sy, after = snap_point(arr, claim_x, claim_y, ink)
    assert before < INK_MIN < after
    assert abs(sx - claim_x) >= 60


def test_snap_leaves_an_already_good_claim_where_it_is():
    arr = np.full((400, 400), 250, dtype=np.uint8)
    arr[190:215, 250:330] = 60
    ink = lambda x0, y0, x1, y1: (                            # noqa: E731
        float((arr[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] < 185).mean())
        if arr[max(0, y0):max(0, y1), max(0, x0):max(0, x1)].size else 0.0)
    sx, sy, after = snap_point(arr, 290, 202, ink)
    assert after >= 0.3 and abs(sx - 290) <= 15
