"""The house PDF pipeline, tested on synthetic markdown.

Skipped where Chrome is absent (CI runners): the point of the test is to prove the
post-pass and its readback work, and a test that silently passes without running
would prove the opposite. Everything it writes is thrown away, and the source
markdown is built here — no statement data anywhere.

What is asserted is what actually breaks in a real deliverable:
  · the contents page numbers equal the bookmark outline (they disagreed once:
    the printed page said 4 while the sidebar said 3)
  · no navigation button points at its own page (a button that does nothing)
  · no page is left blank by a layout overflow
  · the house font is embedded (a fallback face is invisible in HTML, obvious in
    print)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.to_pdf import CHROME, FONTS_CSS, house_finish, house_html, print_pdf  # noqa: E402

pytestmark = pytest.mark.skipif(
    not Path(CHROME).exists() or not FONTS_CSS.exists(),
    reason="Chrome أو خطوط البيت غير متوفرة على هذا الجهاز/الـCI")

# صفحة غلاف + محتويات + صفحتان ⇒ مستند قصير يُختبر كاملاً في ثوانٍ
MD = """# رسالة تدقيق داخلية

> مصدرها ملف اختبار، لا بيانات كشوف.

## القسم الأول

نصّ عادي يشرح الفكرة باختصار.

## القسم الثاني

نصّ آخر.
"""


def test_house_pipeline_builds_and_verifies(tmp_path):
    """Two phases, because that is the real contract:

    phase 1 — placeholder numbers: the gate must DETECT that the printed contents
              disagrees with the outline (a gate that cannot fail is decoration);
    phase 2 — numbers taken from the measured outline: the document must verify
              clean, with the font embedded, no self-links and no blank pages.
    """
    import pymupdf

    headings = [(1, "رسالة تدقيق داخلية"), (2, "القسم الأول"), (2, "القسم الثاني")]
    body = (
        "<h1>رسالة تدقيق داخلية</h1>"
        "<h2>القسم الأول</h2><p>نصّ عادي يشرح الفكرة باختصار.</p>"
        "<h2>القسم الثاني</h2><p>نصّ آخر.</p>"
    )

    def build(entries, name: str) -> Path:
        html = tmp_path / f"{name}.html"
        html.write_text(house_html("رسالة تدقيق داخلية", "عنوان فرعي", "سطر المشروع",
                                   body, entries, "مُعدّ للاختبار"), encoding="utf-8")
        pdf = tmp_path / f"{name}.pdf"
        done = print_pdf(html, pdf)
        assert done.returncode == 0 and pdf.exists()
        return pdf

    placeholders = [(t, 0) for _l, t in headings]
    first = build(placeholders, "phase1")
    detected = house_finish(first, headings, contents_page=1)
    assert detected["contents_mismatch"], "الفهرس المطبوخ يجب أن يُكشف انزياحه"

    fixed = [(text, page) for (text, _), page in
             zip(placeholders, detected["outline_pages"])]
    second = build(fixed, "phase2")
    info = house_finish(second, headings, contents_page=1)
    assert info["pages"] >= 3        # غلاف + محتويات + صفحة محتوى واحدة على الأقل
    assert info["embedded_plex"], info["fonts"]
    assert info["self_links"] == 0
    assert info["contents_mismatch"] == [], info["contents_mismatch"]
    assert info["contents_unreadable"] is None
    assert info["blank_pages"] == [], info["blank_pages"]
    assert info["toc"] >= len(headings)

    doc = pymupdf.open(second)
    assert doc.get_toc()[0][1] == "الغلاف"
    for page in doc:
        for link in page.get_links():
            if link.get("kind") == pymupdf.LINK_GOTO:
                assert 0 <= link.get("page", -1) < doc.page_count
    doc.close()
