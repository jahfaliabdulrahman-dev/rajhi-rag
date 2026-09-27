"""The true page order from the printed CUMULATIVE footer totals.

The totals only rise sheet after sheet, so sorting by them recovers the true
order with no page number read (measured on the 629-page file: 625 readable
footers, zero descents in file order; shuffles of those real footers — the
owner's 10,12,11,13 case, a moved block, a reversed file, a random shuffle —
all came back exactly). And two neighbours are consecutive sheets only when
their footer difference equals the second sheet's own sums: on the real file
that confirmed 619 pairs and named the two known missing-sheet gaps.

No network, no API key, no real data: the footers here are synthetic.
"""
from __future__ import annotations

import sys
from decimal import Decimal as D
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
if str(PROJ / "src") not in sys.path:
    sys.path.insert(0, str(PROJ / "src"))

from statement_qa.ordering import (  # noqa: E402
    adjacency, decide_order, footer_order, summarize_footer_order,
)

# كشفٌ من ستّ أوراق: حركاتُ كلِّ ورقة (مدين، دائن) ⇒ إجمالياتُها التراكمية
OWN = {1: (D("100"), D("50")), 2: (D("30"), D("0")), 3: (D("0"), D("200")),
       4: (D("45.50"), D("10")), 5: (D("12"), D("12")), 6: (D("7"), D("0"))}


def _cumulative(sheets):
    out, d, c = {}, D("0"), D("0")
    for s in sheets:
        d, c = d + OWN[s][0], c + OWN[s][1]
        out[s] = (d, c)
    return out


TRUE = _cumulative(range(1, 7))


def _file(sheet_at_position):
    """موضعٌ في الملف ⇒ الورقةُ التي فيه: {موضع: تذييلُ تلك الورقة}."""
    return {pos: TRUE[s] for pos, s in enumerate(sheet_at_position, start=1)}


def test_a_file_in_order_is_recognised():
    fo = footer_order(_file([1, 2, 3, 4, 5, 6]))
    assert fo["order"] == [1, 2, 3, 4, 5, 6]
    assert fo["moved"] == [] and fo["conflicts"] == [] and fo["duplicates"] == []
    assert "✓ مطابقٌ لترتيب الملف (6/6)" in summarize_footer_order(fo)


def test_the_owners_case_one_swapped_pair_is_one_page_to_move():
    """10،12،11،13: الترتيبُ يُستعاد، ويُسمّى **أقلُّ** ما يُنقل — صفحةٌ واحدة."""
    sheets = [1, 3, 2, 4, 5, 6]
    fo = footer_order(_file(sheets))
    assert [sheets[p - 1] for p in fo["order"]] == [1, 2, 3, 4, 5, 6]
    assert len(fo["moved"]) == 1
    assert "في غير موضعها" in summarize_footer_order(fo)


def test_a_reversed_file_comes_back():
    sheets = [6, 5, 4, 3, 2, 1]
    fo = footer_order(_file(sheets))
    assert [sheets[p - 1] for p in fo["order"]] == [1, 2, 3, 4, 5, 6]


def test_an_unreadable_footer_stays_after_its_file_predecessor():
    footers = _file([1, 2, 3, 4, 5, 6])
    footers[4] = (None, TRUE[4][1])
    fo = footer_order(footers)
    assert fo["unplaced"] == [4]
    assert fo["order"] == [1, 2, 3, 4, 5, 6]


def test_debits_and_credits_that_disagree_are_a_conflict_not_a_guess():
    footers = _file([1, 2, 3, 4, 5, 6])
    footers[5] = (TRUE[5][0], D("1"))          # دائنٌ مقروءٌ خطأً: أصغرُ من سابقه
    fo = footer_order(footers)
    assert fo["conflicts"]
    assert "متناقض" in summarize_footer_order(fo)


def test_identical_totals_are_named_as_duplicates():
    footers = _file([1, 2, 3, 3, 4, 5])        # ورقةٌ مُسحت مرّتين
    fo = footer_order(footers)
    assert fo["duplicates"] == [[3, 4]]
    assert "مكرّرة" in summarize_footer_order(fo)


def test_below_half_coverage_there_is_no_verdict():
    footers = {p: None for p in range(1, 7)}
    footers[1], footers[2] = TRUE[1], TRUE[2]
    assert "لا حكم" in summarize_footer_order(footer_order(footers))


def test_consecutive_sheets_are_confirmed_by_arithmetic():
    fo = footer_order(_file([1, 2, 3, 4, 5, 6]))
    own = {p: OWN[p] for p in range(1, 7)}
    assert set(adjacency(fo["order"], _file([1, 2, 3, 4, 5, 6]), own).values()) == {"adjacent"}


def test_a_missing_sheet_is_a_mismatch_and_a_gap_once_numbers_jump():
    """الورقةُ ٤ غائبة: الفرقُ بين تذييلَي ٣ و٥ أكبرُ من حركات ٥."""
    footers = {1: TRUE[1], 2: TRUE[2], 3: TRUE[3], 4: TRUE[5], 5: TRUE[6]}
    own = {1: OWN[1], 2: OWN[2], 3: OWN[3], 4: OWN[5], 5: OWN[6]}
    order = footer_order(footers)["order"]
    assert adjacency(order, footers, own)[(3, 4)] == "mismatch"
    printed = {1: 1, 2: 2, 3: 3, 4: 5, 5: 6}
    pairs = adjacency(order, footers, own, printed)
    assert pairs[(3, 4)] == "gap"
    assert [s for s in pairs.values() if s != "adjacent"] == ["gap"]


def test_exact_arithmetic_outranks_a_misread_page_number():
    footers = _file([1, 2, 3, 4, 5, 6])
    own = {p: OWN[p] for p in range(1, 7)}
    misread = {p: p for p in range(1, 7)}
    misread[3] = 30                               # رقمٌ مطبوعٌ قُرئ خطأً
    assert set(adjacency(list(range(1, 7)), footers, own, misread).values()) == {"adjacent"}


def test_a_missing_total_leaves_the_pair_undecided():
    footers = _file([1, 2, 3, 4, 5, 6])
    footers[3] = None
    own = {p: OWN[p] for p in range(1, 7)}
    pairs = adjacency([1, 2, 3, 4, 5, 6], footers, own)
    assert pairs[(2, 3)] == pairs[(3, 4)] == "undecided"



# ——— R70-1: ترتيبُ التذييلات شاهدٌ واحد — لا يُطبَّق إلا بلا تناقضٍ ولا تكرار وبشاهدٍ ثانٍ ———

def _long_file():
    """اثنتا عشرة ورقةً بإجمالياتٍ تراكميةٍ متفاوتة الخطى (لا أرقامَ مستديرة)."""
    steps = [("137.25", "12.40"), ("58.60", "0"), ("311.05", "44.10"), ("9.75", "0"),
             ("206.35", "71.80"), ("84.20", "0"), ("163.45", "5.55"), ("27.90", "0"),
             ("412.15", "98.65"), ("66.30", "0"), ("145.85", "31.20"), ("73.40", "0")]
    out, d, c = {}, D("0"), D("0")
    for pos, (sd, sc) in enumerate(steps, start=1):
        d, c = d + D(sd), c + D(sc)
        out[pos] = (d, c)
    return out


def test_a_planted_one_digit_footer_misread_keeps_the_file_order():
    """الصنفُ المقيس على تذييلات المالك: خانةٌ واحدة في إجمالي مدين تنقل الصفحةَ عشراتِ المواضع."""
    footers = _long_file()
    d, c = footers[4]
    footers[4] = (d + D("600"), c)                        # خانةُ المئات: ٥١٦ ⇒ ١١١٦
    fo = footer_order(footers)
    assert fo["order"] != list(range(1, 13)), "الخطأُ المزروع يحرّك الترتيبَ فعلًا"
    printed = {p: p for p in range(1, 13)}                # الأرقامُ المطبوعة تتبع الملف
    order, held = decide_order(list(range(1, 13)), fo, printed, {})
    assert order == list(range(1, 13)) and held
    assert "عولجت بترتيب الملف" in summarize_footer_order(fo, held=held)


def test_contradicting_or_duplicate_footers_keep_the_file_order():
    footers = _file([1, 3, 2, 4, 5, 6])
    footers[5] = (TRUE[5][0], D("1"))                     # دائنٌ يتراجع ⇒ تناقض
    order, held = decide_order([1, 2, 3, 4, 5, 6], footer_order(footers), {}, {})
    assert order == [1, 2, 3, 4, 5, 6] and held == "تذييلٌ متناقض"
    order, held = decide_order([1, 2, 3, 4], footer_order(_file([1, 3, 3, 2])), {}, {})
    assert order == [1, 2, 3, 4] and held == "إجمالياتٌ مكرّرة"


def test_a_move_is_applied_only_with_a_second_witness():
    sheets = [1, 3, 2, 4, 5, 6]                           # الموضعان ٢ و٣ متبادلان
    fo = footer_order(_file(sheets))
    alone, held = decide_order([1, 2, 3, 4, 5, 6], fo, {}, {})
    assert alone == [1, 2, 3, 4, 5, 6] and "بلا شاهدٍ ثانٍ" in held
    by_number, held = decide_order([1, 2, 3, 4, 5, 6], fo, dict(zip(range(1, 7), sheets)), {})
    assert by_number == fo["order"] and held is None
    own = {pos: OWN[s] for pos, s in enumerate(sheets, start=1)}
    pairs = adjacency(fo["order"], _file(sheets), own)
    by_sum, held = decide_order([1, 2, 3, 4, 5, 6], fo, {}, pairs)
    assert by_sum == fo["order"] and held is None
    assert "عولجت بترتيبها الحقيقي" in summarize_footer_order(fo, applied=True)
