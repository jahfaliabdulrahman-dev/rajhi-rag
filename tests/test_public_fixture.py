"""The public fixture must actually exercise the layers the project sells.

It is the only statement a stranger ever runs. It used to be a one-page PDF with
a text layer, no printed totals row, no page number and western digits — so the
footer oracle answered «absent», the page-order check had nothing to read, and
the demo showed a table reader instead of a verifier (audit P3-10). These are the
properties that make it a demonstration; they are asserted here so a future edit
cannot quietly take them away.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "sample" / "statement_sample.pdf"

pytestmark = pytest.mark.skipif(not FIXTURE.exists(),
                                reason="الفيّكسترة غير مولَّدة على هذه الآلة")


def _page_images(dpi: int = 100):
    try:
        from pdf2image import convert_from_path

        return convert_from_path(str(FIXTURE), dpi=dpi)
    except Exception as exc:  # poppler missing (CI) — the check is local
        pytest.skip(f"لا مُصيّر PDF هنا: {type(exc).__name__}")


def _ink(pil_image, box) -> float:
    """Fraction of dark pixels inside a (left, top, right, bottom) ratio box."""
    from PIL import Image  # noqa: F401  (PIL ships with pdf2image)

    w, h = pil_image.size
    crop = pil_image.convert("L").crop((int(w * box[0]), int(h * box[1]),
                                        int(w * box[2]), int(h * box[3])))
    hist = crop.histogram()
    dark = sum(hist[:128])
    return dark / max(1, crop.size[0] * crop.size[1])


def test_fixture_has_no_text_layer():
    """A text layer would let a reader — and a reviewer — believe the pipeline
    is doing something it is not: the real inputs are scans."""
    from pypdf import PdfReader

    text = "".join((p.extract_text() or "") for p in PdfReader(str(FIXTURE)).pages)
    assert text.strip() == "", "الفيّكسترة تحمل طبقة نصية — ليست محاكية لمسح ضوئي"


def test_fixture_is_multi_page():
    from pypdf import PdfReader

    assert len(PdfReader(str(FIXTURE)).pages) >= 2, "صفحة واحدة لا تُظهر عبور الصفحات"


def test_every_page_carries_a_printable_page_number():
    for i, img in enumerate(_page_images(), 1):
        assert _ink(img, (0.03, 0.02, 0.20, 0.10)) > 0.0005, \
            f"ص{i}: لا حبر في موضع رقم الصفحة"


def test_every_page_has_a_totals_row_in_the_footer_band():
    """The oracle reads the bottom band (footer_oracle CROP_TOP = 0.75).

    A totals row floating straight after the last transaction looks equivalent
    on screen and is invisible to the checker.
    """
    for i, img in enumerate(_page_images(), 1):
        assert _ink(img, (0.0, 0.75, 1.0, 1.0)) > 0.002, \
            f"ص{i}: شريط الإجماليات السفلي فارغ — لا شيء يقارنه الأوراكل"
