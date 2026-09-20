"""اختبارات قارئ الكشوف الرقمية (نصّ المصرف) — بلا نموذج وبلا شبكة.

ثلاثة أشياء تُختبَر، وكلٌّ منها يُخفي عطلاً صامتاً إن سقط:
  · **التطبيع العربي**: النصّ يخرج بصور العرض مُرتَّباً بصرياً؛ وتطبيعٌ يقلب
    الترتيب خطأً يُنتج كلماتٍ غير موجودة — وهو أسوأ من عدم التطبيع لأنه يُقرأ
    كأنه صحيح (وقع فعلاً: «الإلقفال» بخانتين بدل ثلاث).
  · **تجميع السطور**: تقريب الخانة (`round(top/tol)`) يفصل سطراً واحداً إلى
    سطرين حين تقع كلمتاه على حدّ الخانة ⇒ صفُّ مبلغٍ يُقرأ ناقصاً.
  · **الصفّ المالي**: المبلغ والرصيد **كما طُبعا**، والاتجاه لا يُستنتج هنا.

والقياس على الكشف الحقيقي يُشغَّل محليّاً فقط (الملف لا يدخل المستودع).
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from statement_qa.text_reader import (  # noqa: E402
    _lines, normalize_arabic_visual, read_rows,
)

APP_PDF = PROJ / "data" / "local_sample" / "digital" / "app_statement.pdf"


# ── التطبيع العربي ────────────────────────────────────────────────────────
def test_presentation_forms_become_letters_in_logical_order():
    assert normalize_arabic_visual("ﻲﻠﺴﻠﺴﺘﻟﺍ ﻢﻗﺮﻟﺍ") == "الرقم التسلسلي"
    assert normalize_arabic_visual("ﻝﺎﻔﻗﻹﺍ") == "الإقفال"
    assert normalize_arabic_visual("ﻥﺎﺒﻳﻵﺍ") == "الآيبان"
    assert normalize_arabic_visual("ﺕﺎﻋﺍﺪﻳﻹﺍ") == "الإيداعات"


def test_normalisation_never_touches_amounts_or_latin():
    assert normalize_arabic_visual("1,234.50") == "1,234.50"
    assert normalize_arabic_visual("PAYROLL-996CT2") == "PAYROLL-996CT2"


def test_the_lam_alef_fix_is_three_characters_not_two():
    """تطبيعٌ يُنتج كلمةً غير موجودة عطل: «الإلقفال» كانت نتيجة إصلاحٍ بخانتين."""
    out = normalize_arabic_visual("ﻝﺎﻔﻗﻹﺍ")
    assert "الإلقفال" not in out, "الإصلاح بخانتين يعيد الكلمة مقلوبة"
    assert out == "الإقفال"


# ── تجميع السطور ─────────────────────────────────────────────────────────
class _Page:
    def __init__(self, words):
        self._words = words

    def extract_words(self):
        return self._words


def test_words_on_one_line_are_not_split_by_bucket_rounding():
    """كلمتان على السطر نفسه (379.8 و378.9) كانتا تقعان في خانتين فتَنفصلان."""
    page = _Page([
        {"text": "Number", "top": 379.8, "x0": 40},
        {"text": "93", "top": 378.9, "x0": 292},
    ])
    lines = _lines(page)
    assert len(lines) == 1, "سطرٌ واحد انقسم إلى سطرين"
    assert [w["text"] for w in lines[0]] == ["Number", "93"]


# ── القياس على الكشف الحقيقي (محليّ فقط) ─────────────────────────────────
@pytest.mark.skipif(not APP_PDF.exists(),
                    reason="الكشف الرقمي محليّ لا يدخل المستودع")
def test_the_real_app_statement_parses_and_its_chain_closes():
    rows = read_rows(APP_PDF)
    assert len(rows) == 440, "عدد الصفوف تغيّر عن المقيس على هذا الكشف"
    assert [r for r in rows if not r["date"]] == [], "صفٌّ بلا تاريخ"
    prev = Decimal("0")
    breaks = 0
    for r in rows:
        # الاتجاه يُستنتج من الرصيدين هنا للاختبار فقط — وفي المنظومة تثبته السلسلة
        if r["balance"] != prev + (r["movement"] if r["balance"] >= prev else -r["movement"]):
            breaks += 1
        prev = r["balance"]
    assert breaks == 0, f"{breaks} كسراً في سلسلة الرصيد على كشفٍ رقميّ"
