"""Exact-crop tests for the footer oracle.

An external audit found the fixed `0.75` fraction sitting BELOW a real page's
printed block (band at y=1662, crop starting at 1753), so the oracle never looked
at it. The rule that fixes this has to hold two properties, and both are tested
here because either one failing makes the change worse than the bug:

  · a measured position may only widen the crop UPWARD — if it could push the top
    down, the oracle would start hiding evidence earlier runs had seen;
  · with no measurement, the answer is byte-for-byte the old behaviour, so
    nothing changes for the 628 pages where the gate measures nothing unusual.

No network, no API key, no real data: the images here are synthetic.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from statement_qa.footer_oracle import (  # noqa: E402
    CROP_TOP, _footer_crop_png, crop_top_px,
)

H, W = 2338, 1654
OLD_TOP = int(H * CROP_TOP)          # 1753 — where the fixed fraction started


def test_no_measurement_is_exactly_the_old_behaviour():
    assert crop_top_px(H) == OLD_TOP
    assert crop_top_px(H, None) == OLD_TOP
    assert crop_top_px(H, 0) == OLD_TOP          # 0 = "not detected", not "top of page"


def test_a_band_above_the_fraction_pulls_the_crop_up():
    """The measured case from the audit: band at 1662 ⇒ the crop must see it."""
    top = crop_top_px(H, 1662)
    assert top < 1662, "القصاصة يجب أن تسبق الإطار لا أن تقع تحته"
    assert top == 1662 - 40


def test_the_crop_never_starts_lower_than_the_fraction():
    """Safety property: the new crop always CONTAINS the old one.

    Measured positions below the fraction (the normal case: y≈1985–2004) must NOT
    move the top down — that would hide rows earlier runs had already read. In
    image coordinates "down" means a LARGER y, so the rule is: never larger.
    """
    for band in (1900, 1985, 2004, 2300):
        assert crop_top_px(H, band) == OLD_TOP, band      # unchanged, deep below
    assert crop_top_px(H, 1753) == 1753 - 40              # at the boundary: widen only
    for band in range(1000, 2338, 7):                     # universal: never lower
        assert crop_top_px(H, band) <= OLD_TOP, band


def test_clamped_inside_the_page():
    assert crop_top_px(H, 10) == 0
    assert crop_top_px(H, 1) == 0


def test_the_actual_crop_contains_the_measured_band(tmp_path):
    """End-to-end on pixels: a band above the fraction must survive the crop.

    Without this, the arithmetic above could be right while the crop still
    dropped the band — the exact failure the audit reported.
    """
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    d.rectangle([100, 1650, 1500, 1700], fill=20)      # the "printed" band
    path = tmp_path / "page.png"
    img.save(path)

    old = Image.open(io.BytesIO(_footer_crop_png(str(path))))
    assert old.size[1] == H - OLD_TOP                  # old band height
    assert old.getpixel((200, 1650 - OLD_TOP + 10)) == 255   # band NOT in old crop

    top = crop_top_px(H, 1662)
    new = Image.open(io.BytesIO(_footer_crop_png(str(path), top)))
    assert new.size[1] == H - top
    assert new.size[1] > old.size[1], "القصاصة الجديدة أوسع لا أضيق"
    assert new.getpixel((200, 1660 - top)) < 128, "الإطار المقيس يجب أن يكون داخل القصاصة"
