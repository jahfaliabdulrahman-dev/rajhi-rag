"""Public numbers must be derived from the run, not remembered (audit P2-5).

Four drifts were caught by a human reading two files at once; this test is the
mechanism that replaces that. It skips where the evidence does not exist (CI
has no statement cache), which is stated plainly rather than hidden.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def test_public_documents_match_the_measured_report():
    import render_claims as rc

    if not rc.REPORT.exists():
        # CI has no statement cache. Instead of skipping — a gate that guards
        # nothing — it reads the DERIVED snapshot committed with the repo:
        # written by tools/render_claims.py from the measured report, so the
        # numbers stay a product of the run and not of anyone's memory.
        snapshot = ROOT / "docs" / "claims.json"
        if not snapshot.exists():
            pytest.skip("لا تقرير ولا لقطة مشتقّة — لا شيء يُحرَس")
        derived = json.loads(snapshot.read_text(encoding="utf-8"))
        assert rc.check(derived) == [], "الوثيقة تخالف لقطتها المشتقّة"
        # **والقسمةُ لا تُفقَد بحذف مفتاحها (مقعدا الجولة الثالثة · P2 · ثقبٌ مُثبت):** دعوتا
        # القسمة مشروطتان بوجود المفتاح، فحذفُهما من اللقطة يُسقط الحارسَ بصمتٍ ويمرّ `check`
        # أخضرَ. والحارسُ اسمٌ في الأداة (`snapshot_split_missing`) فيُقاس هنا على اللقطة الملتزمة
        # وعلى الحالات المشروعة معًا:
        assert rc.snapshot_split_missing(derived) == [], "لقطةٌ تُعلن حكمًا بلا قسمةٍ مشتقّة ⇒ حارسٌ ساقط"
        # **ولا يُحمرّ على طرفٍ لا مجتمعَ له** — وهو ما أخطأتُه أوّلًا (شرطٌ طلب الطرفين معًا:
        # كوربوسٌ نظيفٌ · `legacy` وحدَه · تعارضٌ وحدَه · تقرير `v1` بطرفٍ واحد — كلُّها مشروعة):
        assert rc.snapshot_split_missing({**derived, "split_unstamped": None}) == [], \
            "طرفٌ واحدٌ مشتقٌّ يكفي (لا يُطالَب طرفٌ لا مجتمعَ له)"
        assert rc.snapshot_split_missing({**derived, "corpus_declaration": None}) == [], \
            "بلا حكمٍ لا دعوى قسمة أصلًا ⇒ لا مطالبة"
        # **وإذا سقط الطرفان معًا فالحارسُ يعضّ** (وهو ما يمنع الحذفَ الصامت).
        assert rc.snapshot_split_missing({**derived, "split_unstamped": None, "split_stamped": None}), \
            "لقطةٌ بحكمٍ وبلا أيّ طرفٍ مشتقّ يجب أن تُحمرّ"
        return
    derived = rc.derive()
    assert derived is not None
    drifts = rc.check(derived)
    assert drifts == [], f"انزياح بين الوثيقة ومصدرها: {drifts}"


def test_claims_lists_every_metric_it_promises():
    import render_claims as rc

    fake = {"pages": 629, "rows": 5793, "clean": 5770, "clean_pct": "99.6%",
            "ok": 621, "mismatch": 0, "gap": 2, "absent": 4, "unchecked": 2,
            "documented_ratio": "621/629", "clean_ratio": "5770/5793",
            "recoveries": 23, "rereads": 15, "arbitrations": 3,
            "median_page_s": 22.18, "gate3_price_cap_pages": 133}
    pairs = rc.claims(fake)
    assert len(pairs) >= 8
    assert any(n == "621/629" for _f, n, _l in pairs)
    assert any("مرساة" in n for _f, n, _l in pairs)
    # **وسقفُ القرار له مقابلةٌ في الوثائق** (review-60): يُشتقّ من كائن القرار ويُقابَل في موضعين.
    caps = [(f, n) for f, n, _l in pairs if "سقفُ ثمنِ الإفراج" in n]
    assert len(caps) == 2 and all("133" in n for _f, n in caps), caps


def test_the_withdrawn_gate3_license_is_not_restated_in_public_docs():
    """**مفتاحُ الرخصة المسحوبة لا يعود** (review-60 · R60-1): كان القرارُ يُرخي **التقاطعَ نفسَه**
    بمفتاح `accepted_pages` ⇒ رخصةُ إدخال صفحةٍ من الحزمة إلى بيانات التدريب والحكمُ `PASS`.
    فالمصدرُ الواحدُ (`GATE3_DECISION`) يحرس مفتاحَه في اختبار الأداة، **والوثائقُ المعلَنةُ** تحرس
    ألّا تُعيد الرخصةَ بآليّتها (وقد شرحناها مؤرَّخةً في `docs/EVAL_PACK.md` — الشرحُ ليس إعادةَ تفعيل).
    """
    for rel in ("docs/GATES.md", "README.md", "PLAN.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "accepted_pages" not in text, \
            f"{rel}: مفتاحُ الرخصة المسحوبة رجع ⇒ البوابةُ (٣) تُرخى بقرارٍ من جديد (R60-1)"
    # **و`docs/EVAL_PACK.md` خارجَ القائمة عن قصد**: هو الموضعُ الوحيد الذي **يشرح** الرخصةَ المسحوبة
    # بتاريخها (والمذيَّلُ «التصحيحُ الحاكم») ⇒ فيه اسمُ المفتاح اقتباسًا لا تعليمًا. والحكمُ عليه محروسٌ
    # من جهة الشيفرة (`tests/test_eval_pack.py`: المفتاحُ ممنوعٌ في `GATE3_DECISION` نفسِه).


def test_a_mixed_corpus_is_not_published_under_one_stamp():
    """**البند ٧ (R89-7 · FM-1 «يُعلن ولا يُجمَع تحت رقمٍ واحد»):** تقريرٌ يحمل صفحاتٍ غيرَ مختومة
    لا يُنشر بختمٍ واحد — فالختمُ الواحدُ ينسب الكوربوسَ كلَّه إلى قارئٍ لم تُقرأ به تلك الصفحات.

    والاتّجاهان مقيسان: مختلطٌ ⇒ الإعلانُ بعدده وقسمته (والقسمةُ تُشتقّ من فرق عدد الصفحات لا تُكتب
    بيد)، ومختمٌ كلُّه ⇒ الختمُ وحدَه (فلا نصٌّ ثابتٌ يُضاف بلا مقتضى).
    """
    import render_claims as rc

    single = {"model": "google/gemini-3.7-flash", "prompt_version": "v2:fa91de52"}
    mixed = {"reader_stamp": single, "slice": {"pages_done": 629},
             "corpus_provenance": {"legacy_unstamped_pages": 624, "stamp_conflict_pages": 3,
                                   "declaration": "مختلط/غير مختم — يُعلن ولا يُجمَع تحت رقمٍ واحد"}}
    out = rc.reader_declaration(mixed)
    assert "624" in out and "v2:fa91de52" in out, out
    assert "5 مختومة" in out, f"قسمةُ الصفحات تُشتقّ من الفرق (629 − 624): {out}"
    # **والشكلُ الذي كان يُنشر (الختمُ وحدَه) يُرفض صريحًا** — وهو نصُّ العلّة بعينه.
    assert out != rc._stamp_label(single), "الإعلانُ رجع ختمًا واحدًا لكوربوسٍ بنسبين"

    clean = {**mixed,
             "corpus_provenance": {"legacy_unstamped_pages": 0, "stamp_conflict_pages": 0,
                                   "declaration": "كوربوسٌ بنسبٍ واحد"}}
    assert rc.reader_declaration(clean) == "google/gemini-3.7-flash:v2:fa91de52", \
        "كوربوسٌ مختمٌ كلُّه يُنشر بختمه وحدَه (لا إعلانَ بلا مقتضى)"

    # **ومسندُ «الاختلاط» واحدٌ في المُنتِج والقارئ (مقعدُ المعايير · سقوطٌ مُثبت):** تقريرٌ
    # اختلاطُه من **تعارض ختم** وحدَه (`legacy_unstamped_pages == 0`) كان يُنشر منه **ختمٌ واحد**
    # بينما `corpus_declaration` المنقولُ من التقرير يقول «مختلط» ⇒ حقلان يتناقضان في اللقطة.
    conflict_only = {**mixed,
                     "corpus_provenance": {"legacy_unstamped_pages": 0, "stamp_conflict_pages": 3,
                                           "declaration": "مختلط/غير مختم — يُعلن ولا يُجمَع تحت رقمٍ واحد"}}
    out2 = rc.reader_declaration(conflict_only)
    assert out2 != rc._stamp_label(single), "اختلاطُ التعارض رجع ختمًا واحدًا (مخالفًا لإعلان التقرير)"
    assert "3" in out2 and "تعارض" in out2, out2

    # **وغيابُ الختم لا يُركَّب نصًّا يناقض نفسَه:** «٥ مختومة، بختم غير مختم» — كان يُنتج بلا شرط.
    no_stamp = {**mixed, "reader_stamp": None}
    out3 = rc.reader_declaration(no_stamp)
    assert "غيرُ مُعلَن" in out3 and "بختم" not in out3, out3

    # **ولا دعوى على مقامٍ معدوم:** بلا سجلاتِ صفحات (= بيئةُ الـCI) تُعيد القسمة `None` ⇒ فلا
    # يُشترط رقمُ القسمة في الوثيقة، ولا تُقابَل قيمةٌ بمقامٍ لا وجودَ له.
    assert rc._split_by_stamp({"per_page": [], "slice": {"pages_done": 629}},
                              Path("/nonexistent-results")) == (None, None)

    # **وحكمُ المُنتِج واحدٌ لا اثنان (مقعدُ البنية P2):** القارئُ يقرأ نصَّ الكوربوس النظيف من
    # `tools/scale_slice.py` ولا يعيد كتابتَه ⇒ فالنسختان مُقابَلتان هنا، وسببٌ ثالثٌ في المُنتِج
    # يُقرأ مختلطًا عند القارئ بلا تعديلٍ في موضعين.
    import scale_slice as ss
    assert rc.CLEAN_DECLARATION == ss.CLEAN_DECLARATION, \
        "نصُّ الكوربوس النظيف في نسختين ⇒ الافتراقُ صامتٌ إذا تغيّر أحدُهما"

    # **وغيابُ الحكم يقع إلى العدّادات — ولا يُسكَت عن الاختلاط:** تقريرٌ مصنوعٌ بلا `declaration`
    # (أو بأرشيفٍ قديم) يُقرأ عدّادُه؛ والتقريرُ الحقيقيّ لا يبلغ هذه الحال (المُنتِج يكتب الحكم دائمًا).
    no_verdict = {"reader_stamp": "google/gemini-3.7-flash:v2:fa91de52",
                  "slice": {"pages_done": 629},
                  "corpus_provenance": {"legacy_unstamped_pages": 624, "stamp_conflict_pages": 3}}
    out4 = rc.reader_declaration(no_verdict)
    assert "624" in out4 and out4 != rc._stamp_label(no_verdict["reader_stamp"]), out4

    # **وختمٌ بصيغة سلسلةٍ مُعلَنٌ لا غائب (مقعدُ البنية P3):** كان الوجودُ يُفحص بالنوع
    # (`isinstance(raw, dict)`) فيُنشر «غيرُ مُعلَن» عن ختمٍ مُعلَنٍ نصًّا — نظيرُ العطب الذي أُغلق.
    str_stamp = {**conflict_only, "reader_stamp": "google/gemini-3.7-flash:v2:fa91de52"}
    assert "غيرُ مُعلَن" not in rc.reader_declaration(str_stamp), rc.reader_declaration(str_stamp)


def test_the_group_guide_renders_its_numbers_and_names_langchain() -> None:
    """**R93-5:** دليلُ المجموعة (١) يصوغ أرقامَه فعلًا — لا `{V['pages']}` حرفًا — و(٢) فيه فصلُ LangChain.

    **العطبُ المقيس:** ثلاثةُ أجسادٍ في `SECTIONS` كانت نصوصًا بلا `f` ⇒ خرج الرمزُ **حرفًا** في PDF
    يُسلَّم للمجموعة (١٣ رمزًا)، ولم يكن في المستودع ضابطٌ يقرؤه — وبوّابةُ البناء كانت تفحص `**` و`##`
    ولا تفحص `{V[`. وهذا الضابطُ يقرأ **المصدر** (لا الـPDF: بناؤه يحتاج Chrome)، فيمسك الصنفَ نفسَه
    بلا تبعيّة، ويسقط على النسخة التي وُلد فيها العطب.
    """
    import ast
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[1] / "tools" / "build_explainer.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    sections = None
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", "") == "SECTIONS" for t in node.targets)):
            sections = node.value
    assert isinstance(sections, ast.List), f"شكلُ SECTIONS غيرُ متوقَّع: {type(sections).__name__}"
    listed = list(getattr(sections, "elts", []))      # نوعٌ من AST ⇒ يُقرأ بلا افتراض شكل

    bodies = [e.elts[1] for e in listed]
    titles = [ast.literal_eval(e.elts[0]) for e in listed]
    raw = [b for b in bodies
           if isinstance(b, ast.Constant) and ("{V[" in str(b.value) or "{T." in str(b.value))]
    assert not raw, ("قسمٌ يحمل رقمًا وليس f-string ⇒ يخرج الرمزُ خامًّا في ملفٍّ يُسلَّم: "
                     f"{str(raw[0].value)[:60]}")
    assert any("LangChain" in str(t) for t in titles), f"لا فصلَ LangChain في الدليل: {titles}"


def test_the_slides_name_the_four_missing_topics_and_source_their_numbers() -> None:
    """**R93-6:** الشرائحُ تحمل الأربعةَ الغائبة (أهداف · معماريّة · تقنيات · LangChain)، ولا رقمَ
    كلفةٍ بلا مصدرٍ في المستودع. **وزمنُ القراءة مُعلَنٌ في مُنتِج الأرقام** (`render_claims._rehearsal_read_s`)
    ومربوطٌ برقَمَي السيناريو بحارس `--check` — وموضعُه في المستهلك **مقيسٌ هنا**: لا رقمَ حرفيًّا
    ولا ثانيَ نسخةٍ، وقراءتُه من اللقطة وحدها (وكان الزمنُ قبل ذلك ≈ 4:21 مشتقًّا من وسيط الصفحة،
    فاستُبدل بالمقيس من البروفة — ومراجعة ٩٨ صحّحت مرجعَه إلى صورِ الصفحات).

    **العطبُ المقيس:** كانت عشرَ شرائحَ: صفرُ ذكرٍ لـLangChain وGradio وSQLite وFAISS،
    وفيها كلفةٌ **بلا مصدر** ($0.2492)، وزمنٌ مكتوبٌ «١:٣٠» لعشر صفحات — والقياسُ (وسيطُ الصفحة
    26.13 ث) يقول ~٤٫٤ دقائق ⇒ كان العرضُ يَعِد بما لا يقيسه شيء.
    """
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[1] / "tools" / "build_slides.py"
    text = src.read_text(encoding="utf-8")
    for topic in ("الأهداف", "المعمارية", "التقنيات", "LangChain"):
        assert topic in text, f"شريحةٌ غائبة عن العرض: {topic}"
    assert "0.2575" in text, "الكلفةُ المقيَّدة بمصدرها لم تُكتب"
    # **والقاعدةُ لا العدّ (وقد قاسها الضابطُ على نفسي أوّلًا):** الرقمُ بلا مصدرٍ يجوز أن يبقى
    # **داخل جملةِ سحبٍ مُعلَنة** (يُسمّى ثمّ يُسحب) — ولا يجوز أن يُستعمل رقمًا في شريحة.
    used = [ln for ln in text.splitlines()
            if "0.2492" in ln and "سُحبت" not in ln and "بلا مصدر" not in ln]
    assert not used, f"رقمُ كلفةٍ بلا مصدر يُستعمل بلا سحبٍ معلن: {used[:2]}"
    # **والقاعدةُ نفسُها للزمن (قاسها الضابطُ عليّ ثانيةً):** «١:٣٠» يجوز أن يُسمّى **رقمًا مسحوبًا**،
    # ولا يجوز أن يكون زمنَ خطوةٍ في الشريحة.
    stale = [ln for ln in text.splitlines()
             if "١:٣٠" in ln and "كانت" not in ln and "القياس" not in ln]
    assert not stale, f"زمنٌ مكتوبٌ عاد إلى خطوات العرض: {stale[:2]}"
    assert "{{READ_MMSS}}" in text and "{{MEDIAN_S}}" in text, "الحاملُ المشتقّ غاب"
    assert '"{{"' in text, "بوّابةُ الرموز الخامّة لا تفحص الحوامل ({{) ⇒ يمرّ حاملٌ فارغ للمجموعة"
    # **ولا نسخةَ ثانيةَ من الزمن في المستهلك (مقيسٌ لا موعود — توجيهُ المدقّق 2026-10-08):**
    # القيمةُ تُقرأ من اللقطة وحدها؛ وأيُّ `346` أو «5:46» حرفيٍّ هنا نسخةٌ يفرّقها النسيان — وهي
    # عينُ العلّة التي كان التعليقُ يَعِد بسقوطها بينما كانت تمرّ (الرقمُ كان مكتوبًا في مستهلك
    # لا يقرأه حارس).
    assert "346" not in text and "5:46" not in text, "نسخةٌ يدويةٌ من زمن القراءة عادت إلى المستهلك"
    assert 'c["rehearsal_read_s"]' in text, \
        "المستهلكُ لا يقرأ الزمنَ من اللقطة ⇒ قيمتُه مكتوبةٌ في مستهلك (لا يُحرَس بالـ`--check`)"


def test_the_test_count_stays_unpublished():
    """**قرارُ المالك (2026-10-28 · الخيار (أ)): عدّادُ الاختبارات لا يُنشر ولا يُحرَس.**

    كان عددًا لكلّ بيئةٍ يُحمرّ عند كلّ اختبارٍ جديد حتى يُعاد كتابتُه في ثلاث وثائق ولقطة. فأُزيل الرقمُ
    وحارسُه معًا. وهذا الضابطُ يحرس **الحدَّ نفسَه**: عودةُ الرقم إلى اللقطة، أو عودةُ عدّاده إلى الأداة،
    أو عودةُ كتابته في الـCI، تُسقطه بالاسم — فلا يرجع الاحتكاكُ صامتًا بلا قرارٍ جديد.
    """
    import render_claims as rc

    snap = json.loads((ROOT / "docs" / "claims.json").read_text(encoding="utf-8"))
    assert not {"tests", "tests_by_env"} & set(snap), "عدّادُ الاختبارات عاد إلى اللقطة"
    assert not hasattr(rc, "_test_count"), "عدّادُ الاختبارات عاد إلى أداة الدعاوى"
    wf = (ROOT / ".github" / "workflows" / "publish-guard.yml").read_text(encoding="utf-8")
    assert "render_claims.py --write" not in wf, "الـCI عاد يكتب اللقطةَ من قياسه"
    assert "RAJHI_CLAIMS_ENV" not in wf, "مفتاحُ بيئة العدّاد عاد إلى الـCI"
