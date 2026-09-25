"""**وحدةُ الصرف المشتركة**: القاعدةُ بالسنتات · والتسامحُ **مُعلَنٌ ومقيس** · والصنفُ يُغلق في المواضع الخمسة.

السياق (مراجعة ٥٢ · R52-4 · مقعدُ البنية F7): كان السقفُ يُقارَن بعائمٍ خامّ في **خمسة** مواضعَ
(`eval_questions` · `compare_prompts` · `page_numbers` · `pos_witness` · `scale_slice`)، والعائمُ يكذب
عند الحدّ: `0.1 + 0.2 == 0.3` ⇒ **False** في بايثون، ومجموعُ قراءتين حقيقيّتين من العدّاد
(`0.3` + `2.27e-14`، ×٢) ⇒ **`> 0.6` ⇒ True** فيُطلق توقّفًا استباقيًّا مبكّرًا.
"""
from __future__ import annotations

import pathlib
import re

from tools.spend import at_or_over, cents, would_exceed

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_the_float_trap_that_started_this():
    """**العلّةُ نفسها في الضابط** — بمقدّماتٍ مقيسةٍ لا منقولة.

    ⚠ **تصحيحٌ ذاتيّ**: نصٌّ كان يقول إنّ `0.3 + 0.3 == 0.6` ⇒ **False**. قِيس الآن ⇒ **True** (المجموعُ
    يُقرَّب إلى تمثيل `0.6` نفسه). فالمقدّمةُ الصحيحةُ ليست «المساواةُ تفشل عند ٠٫٣»، بل: **قراءتان
    حقيقيّتان من العدّاد** مجموعُهما يزيد على السقف بجزءٍ من ١٠ᐨ¹⁴ ⇒ فيبدو تجاوزًا. والقيمةُ مقيسةٌ
    من مسبار السقف على رصيدٍ غير صفريّ (٢٨٩): `0.3` + `2.27e-14` لكلّ نداء.
    """
    assert not (0.1 + 0.2 == 0.3), "المثالُ الكلاسيكيّ: الجمعُ العائمُ لا يحفظ المساواة"
    pair = 0.3 + 2.27e-14 + 0.3 + 2.27e-14                   # ما يُقرأ فعلًا من عدّاد المزوّد
    assert pair > 0.6, "المقدّمةُ المقيسة: مجموعُ قراءتين عند السقف يبدو متجاوزًا بالعائم"
    assert not would_exceed(pair, 0.6), "وبالسنت: ٦٠ ليس أكبرَ من ٦٠ ⇒ لا توقّفَ مبكّرًا"
    assert at_or_over(pair, 0.6) and at_or_over(0.3 + 0.3, 0.6), "٣٠+٣٠ سنتًا = ٦٠ ⇒ بلوغُ السقف واجب"


def test_the_boundary_in_both_directions():
    """**الحدُّ من الجهتين**: تحت السقف لا توقّف، وعنده يتوقّف، وفوقه يُعلَن التجاوز."""
    assert not at_or_over(0.59, 0.60)
    assert at_or_over(0.60, 0.60)
    assert not would_exceed(0.59, 0.60)
    assert not would_exceed(0.60, 0.60), "بلوغٌ ليس تجاوزًا: التسلسلُ يتوقّف مرّةً واحدة"
    assert would_exceed(0.61, 0.60)


def test_the_declared_tolerance_is_one_half_cent():
    """**التسامحُ المُعلَن (≤ ٠٫٥ سنت) يُقاس** — فلا يُدَّعى «من الجذر بلا هامش» ما لم يكن صفرًا."""
    assert not would_exceed(0.6049, 0.60), "٠٫٤٩ سنت فوق السقف لا تُعدّ تجاوزًا (تقريبٌ نصف‑صاعد)"
    assert would_exceed(0.6050, 0.60), "نصفُ سنت يُقرَّب لأعلى ⇒ تجاوز"
    assert cents(0.6049) == 60 and cents(0.6050) == 61


def test_cents_is_exact_on_real_amounts():
    """أرقامٌ من الاستعمال الحقيقيّ (رصيدُ مفتاح · كلفةُ جولة): لا انزياحَ في التمثيل."""
    assert cents(289.0) == 28900 and cents(286.5) == 28650
    assert cents(12345.678) == 1234568 and cents(1000) == 100000
    assert cents(-0.5) == -50 and cents(0.0) == 0


def test_no_tool_compares_a_budget_with_raw_floats():
    """**شبكةٌ للصنف المُسجَّل** (لا برهان): لا مقارنةَ خامّةً بالسقف في أيّ أداة.

    ⚠ حدُّها المُعلَن: تقيس **التهجئة المُسجَّلة** (`>= args.budget` / `>= args.max_cost`) — وهي التي
    وقع بها الصرفُ فعلًا في خمسة مواضع. والبرهانُ على القاعدة نفسها هو ضوابطُ هذه الوحدة أعلاه،
    لا هذه الشبكة؛ فمن كتب مقارنةً بتهجئةٍ أخرى لا تمسكه هذه — تمسكه مراجعةُ البنية (وهذا مُعلَن).
    """
    pat = re.compile(r">=\s*args\.(max_cost|budget)\b")
    offenders = []
    for p in sorted((ROOT / "tools").glob("*.py")):
        if p.name == "spend.py":
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                offenders.append(f"{p.name}:{i}")
    assert not offenders, f"مقارنةُ سقفٍ بعائمٍ خامّ (استعمل `tools.spend`): {offenders}"
