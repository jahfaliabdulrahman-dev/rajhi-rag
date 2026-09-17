"""اختبارات بوابة جودة المسح — كل الصور **اصطناعية** (لا كشوف حقيقية في git).

القاعدة الحاكمة هنا: **لا عتبة بلا اختبار يُثبت أنها تعضّ.**
لكل حدّ في `tools/page_gate.py` تدهورٌ مزروع يجب أن يُطلقه — وإلا فهو زينة لا حارس.
والمقابل مُختبَر أيضاً: **صفحة سليمة يجب ألّا تُرفض** (حارس يرفض الصحيح أسوأ من غيابه).

الجزء الأخير (إن وُجدت المسحة المحلية) يعيد إنتاج النتيجة المقيسة على 629 صفحة:
ثلاث صفحات **فارغة فعلاً** (172 · 484 · 602) ⇒ تُرفض، وصفحة **رقيقة** واحدة
(`pg-628.png` = المطبوعة ٦٢٩: صفّان وإطار مطبوع مقروء) ⇒ **لا تُرفض**.
الرقيقة ليست فارغة، ورفضها كان يُسقط من الدفع صفحةً قابلة للإثبات.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFilter

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.page_gate import (  # noqa: E402
    R_BLANK, R_BLUR, R_LANDSCAPE, R_NO_REFEREE, R_SIZE_VARIANCE, R_SKEW,
    R_SMALL_TEXT, R_SPARSE, TH, check_page, modal_page_size, verdict,
)

W, H = TH.ref_w, TH.ref_h
CORPUS_PAGES = PROJ / "data" / "local_sample" / "slice_629p" / "pages"
needs_corpus = pytest.mark.skipif(
    not CORPUS_PAGES.exists(),
    reason="المسحة الحقيقية غير موجودة على هذا الجهاز (لا تسري في CI)")


# ————————————————— مجسّم الصفحة الاصطناعية —————————————————

def page(w: int = W, h: int = H, *, footer: bool = True, body_h: int = 20,
         glyph_w: int = 13, rows: int = 40) -> Image.Image:
    """صفحة كشف اصطناعية: ترويسة + متن أسطر + سطر إطار بمقاطع أرقام."""
    img = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(img)
    d.rectangle([100, 80, 1200, 100], fill=40)                  # ترويسة الفترة
    for i in range(rows):
        y = 300 + i * 45
        d.rectangle([100, y, 1500, y + body_h], fill=60)        # أسطر المتن
    if footer:
        y, x = h - 220, 120
        for _ in range(13):                                    # مقاطع أرقام الإطار
            d.rectangle([x, y, x + glyph_w, y + 26], fill=30)
            x += 110
    return img


def saved(tmp_path: Path, name: str, im: Image.Image) -> Path:
    p = tmp_path / f"{name}.png"
    im.save(p)
    return p


# ————————————————— الحدود: كل تدهور يُطلق سببه —————————————————

def test_clean_page_is_accepted(tmp_path):
    r = check_page(saved(tmp_path, "clean", page()))
    assert r["verdict"] == "accept", r["reasons"]
    assert r["reasons"] == []
    assert r["referee_present"] and r["referee_segments"] >= 8


def test_landscape_page_is_rejected(tmp_path):
    p = saved(tmp_path, "rot90", page().transpose(Image.Transpose.ROTATE_90))
    r = check_page(p)
    assert r["verdict"] == "reject"
    assert R_LANDSCAPE in r["reasons"]


def test_blur_is_rejected_and_threshold_bites(tmp_path):
    blurred = page().filter(ImageFilter.GaussianBlur(3))
    r = check_page(saved(tmp_path, "blur", blurred))
    assert r["verdict"] == "reject"
    assert R_BLUR in r["reasons"]
    assert r["sharpness"] < TH.lapvar_min          # العتبة نفسها تقيس ما تدّعيه
    assert check_page(saved(tmp_path, "clean", page()))["sharpness"] > TH.lapvar_min


def test_skew_is_rejected_and_measured_correctly(tmp_path):
    rotated = page().rotate(5, resample=Image.Resampling.BICUBIC, fillcolor=255)
    r = check_page(saved(tmp_path, "skew", rotated))
    assert r["verdict"] == "reject"
    assert R_SKEW in r["reasons"]
    # المقصود ليس «وجدنا ميلاً» بل «قدّرناه بإشارته ومقداره» — وإلا فالمقياس أعمى
    assert abs(r["skew_deg"]) > TH.skew_max_deg
    assert -7.0 < r["skew_deg"] < -3.0


def test_missing_referee_is_a_warning_not_a_block(tmp_path):
    """بلا إطار ⇒ لا إثبات — لكنه **ليس** سبب حجب: في المسحة المرجعية 4 صفحات
    بلا إطار مطبوع أصلاً وهي مشروعة، فالحجب هنا كان سيصادر ورقاً صحيحاً."""
    r = check_page(saved(tmp_path, "no_footer", page(footer=False)))
    assert r["verdict"] == "warn"
    assert R_NO_REFEREE in r["reasons"]


def test_small_body_text_triggers_small_text(tmp_path):
    r = check_page(saved(tmp_path, "tiny_body", page(body_h=8)))
    assert r["verdict"] == "warn"
    assert R_SMALL_TEXT in r["reasons"]
    assert r["body_band_h_median"] < TH.body_h_min


def test_downscaled_page_triggers_small_text(tmp_path):
    small = page().resize((W // 2, H // 2), Image.Resampling.LANCZOS)
    r = check_page(saved(tmp_path, "half", small))
    assert r["verdict"] == "warn"
    assert R_SMALL_TEXT in r["reasons"]


def test_sparse_page_is_not_blank_and_is_payable(tmp_path):
    """صفّان أو ثلاثة على ورقة مشروعة: الحبر قليل، لكن الصفحة **ليست فارغة**.

    الفرق ليس تجميلاً: الفارغة تُرفض فتُسقط من الدفع (وهذا غرضها)، والرقيقة
    تُدفع فتُقرأ. الخلط بينهما يدفن صفوفاً مدفوعةً لا تُقرأ أبداً.
    القياس الفاصل: ورقة بيضاء = 0.0001 · صفحة حقيقية بصفّين (pg-628) = 0.0082.
    """
    def sparse_marks(ticks: int = 16):
        img = Image.new("L", (W, H), 255)
        d = ImageDraw.Draw(img)
        x, y = 120, H - 220
        for _ in range(ticks):
            d.rectangle([x, y, x + 25, y + 30], fill=30)
            x += 60
        return img

    r = check_page(saved(tmp_path, "sparse", sparse_marks()))
    assert TH.empty_ink_max < r["ink_ratio"] < TH.ink_ratio_min, r["ink_ratio"]
    assert R_BLANK not in r["reasons"], r["reasons"]   # ليست فارغة
    assert R_SPARSE in r["reasons"], r["reasons"]      # لكنها رقيقة ⇒ تُعلَّم

    blank = check_page(saved(tmp_path, "white", Image.new("L", (W, H), 255)))
    assert blank["verdict"] == "reject" and blank["reasons"] == [R_BLANK]
    assert r["ink_ratio"] > blank["ink_ratio"]


def test_blank_page_reports_only_blankness(tmp_path):
    """الصفحة الفارغة تُحسم أولاً: حدّة وميل لوح أبيض **ضجيج** لا عيوب.
    الاختبار يقفل السلوك: سبب واحد، لا ثلاثة."""
    r = check_page(saved(tmp_path, "blank", Image.new("L", (W, H), 255)))
    assert r["verdict"] == "reject"
    assert r["reasons"] == [R_BLANK]


def test_size_variance_needs_the_file_context(tmp_path):
    """الشذوذ يُقاس **داخل الملف** لا مقابل رقم صلب: نفس الصفحة تُقبل وحدها،
    وتُنبَّه حين تكون شاذة بين أخواتها."""
    odd = saved(tmp_path, "odd", page(w=int(W * 0.8), h=int(H * 0.8)))
    alone = check_page(odd)                                # بلا سياق ملف
    assert R_SIZE_VARIANCE not in alone["reasons"]
    in_file = check_page(odd, modal_size=(W, H))            # بين صفحات المرجع
    assert R_SIZE_VARIANCE in in_file["reasons"]
    assert in_file["verdict"] in ("warn", "reject")


# ————————————————— التجميع والحكم على الملف —————————————————

def test_verdict_aggregates_and_names_the_rejected(tmp_path):
    rows = [
        check_page(saved(tmp_path, "a", page())),
        check_page(saved(tmp_path, "b", page(footer=False))),
        check_page(saved(tmp_path, "c", Image.new("L", (W, H), 255))),
    ]
    v = verdict(rows)
    assert v["pages"] == 3
    assert v["counts"] == {"accept": 1, "warn": 1, "reject": 1}
    assert v["rejected_pages"] == ["c.png"]
    assert v["warned_pages"] == ["b.png"]
    assert v["reasons"][R_NO_REFEREE] == 1 and v["reasons"][R_BLANK] == 1
    assert v["payable_ratio"] == pytest.approx(2 / 3, abs=1e-3)


def test_modal_size_picks_the_file_majority(tmp_path):
    rows = [check_page(saved(tmp_path, f"p{i}", page())) for i in range(3)]
    rows.append(check_page(saved(tmp_path, "odd", page(w=800, h=1200))))
    assert modal_page_size(rows) == (W, H)


# ————————————————— المرجع الحقيقي (محلي فقط) —————————————————

@needs_corpus
def test_real_reference_pages_are_never_rejected():
    """صفحات سليمة من مسحة الركيزة (629 ورقة) — الحارس لا يصادر ورقاً صحيحاً."""
    for i in (1, 151, 301, 481, 561, 629):
        p = CORPUS_PAGES / f"pg-{i:03d}.png"
        if not p.exists():
            continue
        r = check_page(p)
        assert r["verdict"] != "reject", (p.name, r["reasons"])


@needs_corpus
def test_blanks_are_rejected_mechanically_and_a_sparse_real_page_is_not():
    """النتيجة المقيسة: 625 مقبول · 1 منبَّه (رقيقة) · 3 مرفوضة (فارغة).

    المرفوضة الثلاث (172 · 484 · 602) **صور بيضاء قياساً**: حبر 0.0000 ولا إطار
    مكشوف، وفي تقرير التشغيل لها صفر صفوف و`footer: absent` ⇒ الرفض صدق.

    و`pg-628.png` (= المطبوعة ٦٢٩) ليست منهنّ: كاش التشغيل المقبوض يثبت لها
    **صفّين** و`footer: ok` (مدين 300.00 = مجموع الصفّين) وكلفة مقبوضة 0.0077$.
    كانت تُرفض قبل الإصلاح بسبب حبر 0.0082 < 0.010 ⇒ صفحة مدفوعة تسقط من الدفع.
    """
    expected_blank = {"pg-172.png", "pg-484.png", "pg-602.png"}
    blank, sparse = set(), set()
    for name in expected_blank | {"pg-628.png", "pg-001.png", "pg-300.png"}:
        p = CORPUS_PAGES / name
        if not p.exists():
            continue
        r = check_page(p)
        if r["verdict"] == "reject":
            assert r["reasons"] == [R_BLANK], (p.name, r["reasons"])
            blank.add(name)
        if R_SPARSE in r["reasons"]:
            sparse.add(name)
    assert blank == expected_blank, f"مرفوض: {blank}"
    assert "pg-628.png" not in blank, "صفحة رقيقة مدفوعة لا تُرفض"
    assert sparse == {"pg-628.png"}, f"رقيق: {sparse}"
