"""The description column: amounts removed from the image, one numbered box per row, the
continuation riding on the last row, and a merge that only happens when counts match.

Measured before this code existed (20 pages, then 50): the stacked description image read
in one call per page matched the one-row-per-call reference on descriptions, at a quarter
of its cost; the image this module draws is pixel-identical to the experiment's on the
pages checked. No network, no API key, no real data: the pages here are synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

PROJ = Path(__file__).resolve().parents[1]
if str(PROJ / "src") not in sys.path:
    sys.path.insert(0, str(PROJ / "src"))

from statement_qa.desc_reader import (  # noqa: E402
    LABEL_W, SEP, ZONE_X, _zone, blank_debit_amount, continuation_for,
    merge_descriptions, parse_descriptions, stack_image, summarize_ar,
)
from statement_qa.row_bands import analyze_page  # noqa: E402

DPI = 200
K = DPI / 100


def _box(g, x0, x1, y0, y1):
    g[int(y0 * K):int(y1 * K), int(x0 * K):int(x1 * K)] = 0


def _page(rows, orphan=False):
    """rows: [{"amount": (x0, x1) | [(x0, x1), ...] | None, "credit": bool, "text_x0": int}]."""
    g = np.full((int(1170 * K), int(827 * K)), 255, np.uint8)
    _box(g, 400, 590, 332, 340)                  # سطرُ الـIBAN
    _box(g, 650, 700, 977, 985)                  # عنوانُ «العملة»
    y = 400
    if orphan:
        _box(g, 380, 600, y, y + 10)
        y += 20
    for r in rows:
        _box(g, 110, 160, y, y + 8)              # الرصيد
        _box(g, 640, 705, y, y + 8)              # التاريخ
        if r.get("credit"):
            _box(g, 240, 290, y, y + 8)
        amount = r.get("amount")
        for x0, x1 in ([amount] if isinstance(amount, tuple) else amount or []):
            _box(g, x0, x1, y + 1, y + 7)
        _box(g, r.get("text_x0", 430), 620, y - 1, y + 8)
        _box(g, 380, 600, y + 15, y + 25)        # سطرُ وصفٍ ثانٍ
        y += 30
    return g


def _rgb(g):
    return Image.fromarray(g).convert("RGB")


def _ink_cols(crop, band):
    g = np.asarray(crop.convert("L"))
    y0, y1 = band.anchor[0] - band.top, band.anchor[1] - band.top + 1
    return np.flatnonzero((g[y0:y1] < 150).any(axis=0))


def _x(units):                                    # عمودُ الوحدة داخل القصاصة
    return int((units - ZONE_X[0]) * K)


def test_the_debit_amount_is_whited_out_and_the_text_kept():
    g = _page([{"amount": (360, 390)}])
    pb = analyze_page(g, DPI)
    band = pb.bands[0]
    out = blank_debit_amount(_zone(_rgb(g), band.top, band.bottom, K), band, K)
    cols = _ink_cols(out, band)
    assert not any(_x(355) <= c <= _x(395) for c in cols), "بقي من المبلغ حبر"
    assert any(c >= _x(430) for c in cols), "مُسح النصّ مع المبلغ"


def test_spaced_zero_dots_are_whited_out_too():
    """الأصفارُ الهندية نقاطٌ متباعدة: فراغٌ ٦ كان يترك «٠.٠٠» (قيس بالعين على صفحاتٍ حقيقية)."""
    dots = [(360, 364), (372, 375), (383, 386), (394, 397)]     # فراغاتٌ ٨ وحدات
    g = _page([{"amount": dots, "text_x0": 440}])
    band = analyze_page(g, DPI).bands[0]
    out = blank_debit_amount(_zone(_rgb(g), band.top, band.bottom, K), band, K)
    assert not any(_x(355) <= c <= _x(400) for c in _ink_cols(out, band))


def test_a_credit_row_is_left_untouched():
    g = _page([{"credit": True, "amount": None, "text_x0": 400}])
    band = analyze_page(g, DPI).bands[0]
    crop = _zone(_rgb(g), band.top, band.bottom, K)
    assert blank_debit_amount(crop, band, K) is crop


def test_a_wide_first_ink_is_text_not_an_amount():
    g = _page([{"amount": None, "text_x0": 340}])
    band = analyze_page(g, DPI).bands[0]
    crop = _zone(_rgb(g), band.top, band.bottom, K)
    assert blank_debit_amount(crop, band, K) is crop


def test_one_numbered_box_per_row_and_the_continuation_rides_on_the_last():
    g = _page([{"amount": (360, 390)}] * 3)
    nxt = _page([{"amount": (360, 390)}], orphan=True)
    pb, npb = analyze_page(g, DPI), analyze_page(nxt, DPI)
    plain, n = stack_image(_rgb(g), pb)
    assert n == 3
    assert plain.height == sum(b.bottom - b.top + 1 for b in pb.bands) + SEP * 4
    assert plain.width == LABEL_W + int((ZONE_X[1] - ZONE_X[0]) * K)
    cont = continuation_for(pb, npb, _rgb(nxt))
    stitched, n2 = stack_image(_rgb(g), pb, cont)
    assert n2 == 3
    assert stitched.height == plain.height + 4 + (npb.orphan[1] - npb.orphan[0] + 1)


def test_a_continuation_only_joins_two_transaction_pages():
    g = _page([{"amount": (360, 390)}] * 2)
    with_orphan = _page([{"amount": (360, 390)}], orphan=True)
    no_orphan = _page([{"amount": (360, 390)}])
    pb = analyze_page(g, DPI)
    assert continuation_for(pb, analyze_page(with_orphan, DPI), _rgb(with_orphan)) is not None
    assert continuation_for(pb, analyze_page(no_orphan, DPI), _rgb(no_orphan)) is None
    assert continuation_for(pb, None, None) is None
    summary = analyze_page(_page([{"amount": None}] * 2), DPI)
    summary.kind = "summary"
    assert continuation_for(summary, analyze_page(with_orphan, DPI), _rgb(with_orphan)) is None


def test_the_answer_must_have_every_box_exactly_once():
    ok = '{"rows": [{"n": 2, "desc": "ب"}, {"n": 1, "desc": "أ"}]}'
    assert parse_descriptions(ok, 2) == ["أ", "ب"], "بترتيب الخانات لا بترتيب الجواب"
    for bad in ('{"rows": [{"n": 1, "desc": "أ"}]}',
                '{"rows": [{"n": 1, "desc": "أ"}, {"n": 2, "desc": "ب"}, {"n": 3, "desc": "ج"}]}'):
        with pytest.raises(ValueError):
            parse_descriptions(bad, 2)


def test_merge_only_when_counts_match_and_the_old_description_is_kept():
    rows = [{"desc": "قديم ١"}, {"desc": "قديم ٢"}]
    assert merge_descriptions(rows, ["جديد ١", ""]) is True
    assert rows[0] == {"desc": "جديد ١", "desc_page": "قديم ١", "desc_source": "column"}
    assert rows[1] == {"desc": "قديم ٢"}, "خانةٌ فارغةٌ لا تمحو بيانًا"
    short = [{"desc": "قديم"}]
    assert merge_descriptions(short, ["أ", "ب"]) is False and short == [{"desc": "قديم"}]


def test_the_summary_names_where_the_page_reading_was_kept():
    rep = {"merged": [1, 2], "stitched": 1, "failed": [3], "unaligned": [4], "skipped": [5]}
    seg = summarize_ar(rep, 5)
    assert "2/5 صفحة" in seg and "تكملاتٌ ملصوقةٌ بصفوفها: 1" in seg
    assert "ص3 (تعذّرت قراءتُه)" in seg and "ص4 (عددُ الصفوف لا يطابق)" in seg and "ص5 (سقفُ الكلفة)" in seg
