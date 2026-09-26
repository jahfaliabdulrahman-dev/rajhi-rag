"""حدودُ الصفوف من الحبر — على صفحاتٍ اصطناعية بقالب الكشف نفسه.

الصفحاتُ هنا مستطيلاتُ حبرٍ في مواضع القالب (بوحدة 100dpi، مُصيَّرةً بـ150dpi): سطرُ الـIBAN،
عنوانُ «العملة»، ولكلّ حركةٍ رصيدٌ وتاريخٌ على سطرها الأول وأسطرُ وصفٍ تحته. كلُّ اختبارٍ يحرس
حالةً قِيست على الورق الحقيقي (وحدةُ `statement_qa.row_bands`، «ثلاثةُ دروسٍ من القياس»).

No network, no API key, no real data: the pages are synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ / "src"), str(PROJ / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from statement_qa.row_bands import (  # noqa: E402
    analyze_page, link_pages, stitch,
)

DPI = 150
K = DPI / 100
FOOTER_TOP = 977
PITCH = 15                      # خطوةُ السطر في الطباعة (وحدة 100dpi)


def _box(g, x0, x1, y0, y1):
    g[int(y0 * K):int(y1 * K), int(x0 * K):int(x1 * K)] = 0


def _page(rows, *, orphan_lines=0, header=True, footer=True, start=400):
    """rows: [{lines, dated, credit, zero, title, thin, wide_line}] ⇒ (صورة، أسطرُ كلّ صفّ)."""
    g = np.full((int(1170 * K), int(827 * K)), 255, np.uint8)
    if header:
        _box(g, 400, 590, 332, 340)
    if footer:
        _box(g, 650, 700, FOOTER_TOP, FOOTER_TOP + 8)
    y = start
    orphan = []
    for _ in range(orphan_lines):
        _box(g, 380, 600, y, y + 10)
        orphan.append((y, y + 10))
        y += PITCH
    y += 5
    lines_of = []
    for r in rows:
        if r.get("zero"):
            _box(g, 115, 160, y + 4, y + 7)            # «٠٫٠٠»: نقاطٌ فقط، أدنى من سطرها
        elif r.get("thin"):
            _box(g, 130, 130.7, y, y + 8)              # «١»: خطٌّ عرضُه بكسلٌ واحد
        else:
            _box(g, 110, 160, y, y + 8)
        if r.get("dated", True):
            _box(g, 640, 705, y, y + 8)
        if r.get("credit"):
            _box(g, 240, 290, y, y + 8)
        if r.get("title"):
            _box(g, 420, 470, y - 3, y + 8)            # «الرصيد الافتتاحي»: يعلو «٠٫٠٠» بـ٧ (مقيس: ٤٠٤ مقابل ٤١١)
        else:
            _box(g, 400, 620, y - 1, y + 8)
        lines = [(y - 1, y + 8)]
        for j in range(1, r.get("lines", 2)):
            ly = y + PITCH * j
            right = 700 if r.get("wide_line") else 600
            _box(g, 380, right, ly - 3, ly + 12)       # شبهُ ملتصقٍ بما فوقه وما تحته
            _box(g, 380, 386, ly + 12, ly + 14)        # ذيلُ حرفٍ نازل يلامس السطرَ التالي
            lines.append((ly - 3, ly + 14))
        lines_of.append(lines)
        y += PITCH * r.get("lines", 2)
    return g, lines_of, orphan


def _px(v):
    return int(v * K)


def _inside(span, band):
    return band.top <= _px(span[0]) and _px(span[1]) - 1 <= band.bottom


ROWS = [{"lines": 2}, {"lines": 4, "credit": True}, {"lines": 1}, {"lines": 3}, {"lines": 2}]


def test_every_row_is_one_band_and_the_bands_tile_the_table():
    g, _lines, _ = _page(ROWS)
    pb = analyze_page(g, DPI)
    assert pb.kind == "transactions"
    assert len(pb.bands) == len(ROWS)
    for a, b in zip(pb.bands, pb.bands[1:]):
        assert a.bottom + 1 == b.top, "لا فجوةَ ولا تداخلَ بين صفّين"
    for b in pb.bands:
        assert b.top <= b.anchor[0] and b.anchor[1] <= b.bottom


def test_a_multiline_description_stays_in_its_row_even_when_lines_touch():
    """الانحدارُ المقيس: حدٌّ بهامشٍ ثابت فوق المرساة شطرَ آخرَ سطرٍ من وصف الصفّ الأعلى."""
    g, lines_of, _ = _page(ROWS)
    pb = analyze_page(g, DPI)
    for band, lines in zip(pb.bands, lines_of):
        for span in lines:
            assert _inside(span, band), (span, band)


def test_a_continuation_at_the_page_top_is_an_orphan_not_a_row():
    g, _, orphan = _page(ROWS, orphan_lines=2)
    pb = analyze_page(g, DPI)
    assert len(pb.bands) == len(ROWS)
    assert pb.orphan is not None
    assert pb.orphan[0] <= _px(orphan[0][0]) and _px(orphan[-1][1]) - 1 <= pb.orphan[1]
    assert pb.orphan[1] < pb.bands[0].top


def test_no_continuation_when_the_table_starts_with_a_row():
    g, _, _ = _page(ROWS)
    assert analyze_page(g, DPI).orphan is None


def test_the_opening_title_is_not_a_continuation():
    """الدرس ٣: عنوانُ «الرصيد الافتتاحي» يعلو أرقامَه ⇒ جزءٌ من صفّه، لا تكملة."""
    g, _, _ = _page([{"title": True, "dated": False, "zero": True, "lines": 1}] + ROWS)
    pb = analyze_page(g, DPI)
    assert pb.kind == "first"
    assert pb.orphan is None
    assert not pb.bands[0].dated
    assert pb.suspects() == []


def test_a_zero_balance_still_meets_its_date():
    """الدرس ٢: «٠٫٠٠» حافّتُه العليا أدنى من التاريخ — المطابقةُ بالتداخل."""
    g, _, _ = _page([{"lines": 2}, {"lines": 2, "zero": True}, {"lines": 2}])
    pb = analyze_page(g, DPI)
    assert [b.dated for b in pb.bands] == [True, True, True]


def test_a_one_pixel_stroke_is_still_an_anchor():
    """الدرس ١: «١» عرضُه بكسلٌ واحد — عتبةُ الحبر على أيّ بكسل لا على عددها."""
    g, _, _ = _page([{"lines": 2}, {"lines": 2, "thin": True}, {"lines": 2}])
    assert len(analyze_page(g, DPI).bands) == 3


def test_below_150_dpi_is_refused():
    g, _, _ = _page(ROWS)
    with pytest.raises(ValueError):
        analyze_page(g, 100)


def test_a_description_line_reaching_the_date_strip_is_not_an_anchor():
    g, _, _ = _page([{"lines": 3, "wide_line": True}, {"lines": 2}])
    pb = analyze_page(g, DPI)
    assert len(pb.bands) == 2
    assert pb.extra_date_lines == 1      # السطران المتلاصقان حبرٌ واحد في الشريط — عدٌّ للإعلام لا حكم


def test_the_last_row_stops_before_the_footer():
    g, lines_of, _ = _page(ROWS)
    pb = analyze_page(g, DPI)
    assert pb.bands[-1].bottom < _px(FOOTER_TOP)
    assert _inside(lines_of[-1][-1], pb.bands[-1])


def test_the_summary_page_has_balances_but_no_dates():
    g, _, _ = _page([{"lines": 1, "dated": False}] * 4, orphan_lines=1)
    pb = analyze_page(g, DPI)
    assert pb.kind == "summary"
    assert pb.orphan is None, "عنوانُ جدول الملخّص ليس تكملة"


def test_an_undated_anchor_mid_page_is_a_suspect():
    g, _, _ = _page([{"lines": 2}, {"lines": 2, "dated": False}, {"lines": 2}])
    pb = analyze_page(g, DPI)
    assert pb.kind == "transactions"
    assert pb.suspects() == [1]


def test_a_page_without_the_header_line_is_unknown():
    g, _, _ = _page(ROWS, header=False)
    pb = analyze_page(g, DPI)
    assert pb.kind == "unknown" and pb.bands == []


def test_credit_ink_marks_the_credit_column():
    g, _, _ = _page(ROWS)
    assert [b.credit_ink for b in analyze_page(g, DPI).bands] == [
        bool(r.get("credit")) for r in ROWS]


def test_a_continuation_links_to_the_previous_pages_last_row():
    first, _, _ = _page(ROWS, orphan_lines=1)
    second, _, _ = _page(ROWS[:2], orphan_lines=2)
    summary, _, _ = _page([{"lines": 1, "dated": False}] * 3)
    after_summary, _, _ = _page(ROWS[:1], orphan_lines=1)
    pages = [analyze_page(g, DPI) for g in (first, second, summary, after_summary)]
    assert link_pages(pages) == [
        {"page": 0, "owner_missing": True},          # صاحبُها قبل الدفعة: يُعلَّم لا يُحذف
        {"page": 1, "continues": [0, len(ROWS) - 1]},
        {"page": 3, "owner_missing": True},          # لا تُنسب إلى صفحة ملخّص
    ]


def test_stitch_puts_the_continuation_under_its_row():
    prev, _, _ = _page(ROWS)
    nxt, _, _ = _page(ROWS[:2], orphan_lines=2)
    pa, pb = analyze_page(prev, DPI), analyze_page(nxt, DPI)
    band = pa.bands[-1]
    img = stitch(Image.fromarray(prev), band, Image.fromarray(nxt), pb.orphan, sep=6)
    assert img.width == prev.shape[1]
    assert img.height == (band.bottom - band.top + 1) + 6 + (pb.orphan[1] - pb.orphan[0] + 1)


def test_the_tool_refuses_an_output_folder_the_repo_would_track(tmp_path):
    """الصورُ من كشفٍ حقيقي: داخل المستودع لا يُكتب إلا تحت `data/local_sample/` المُتجاهَل."""
    from row_bands import out_allowed

    assert not out_allowed(PROJ / "tools" / "bands")
    assert not out_allowed(PROJ / "data" / "sample" / "bands")
    assert out_allowed(PROJ / "data" / "local_sample" / "bands")
    assert out_allowed(tmp_path / "bands")
