"""**R117-2 (= R115-7) — حاجزُ النطاق يصدق بما يملك، ويُمرَّر إليه ما ينقصه.**

**العطبُ المقيس (مراجعة ١١٧ · P2 · بلا كلفة):** شقّان من بند القرار:

1. **`n_pages` لا يمرّره أحدٌ في المسار الحيّ** (لا التطبيقُ ولا القياس) ⇒ فالفرعُ الوحيدُ الذي
   يعمل هو «أقصى صفحةٍ فيها سطورٌ مقروءة» (٦٢٨)، فيقرأ المستخدمُ عن الصفحة ٧٠٠: «…ولم تُقرأ سطورُ
   ٧٠٠ **بعد**» — **نصٌّ يوهم بوجودها**، وعن الصفحة ٦٢٩ (وهي موجودة): «**غيرُ موجود في الكشف**».
2. **صفحةٌ بلا سطورٍ داخل المدى** (‏١٧٢ · ٤٨٤ · ٦٠٢) **لا تصل الفرعَ أصلًا** (`p > max_page`)
   ⇒ فيجيب عنها النموذج، وأدواتُه لا ترى فيها شيئًا ⇒ «لا حركات» عن صفحةٍ لم تُقرأ سطورُها.

**وثلاثةُ الأصناف — لكلٍّ قولُه الصادقُ وحدَه:** ① خارجَ المستند (يُعلَن انتهاؤه) · ② داخلَه
وفوق أقصى صفحةٍ فيها سطورٌ (تُسمّى داخلةً ولم تُقرأ سطورُها) · ③ داخلَ مدى ما قُرئ وبلا سطورٍ
(تُسمّى كذلك، **ولا يُقال إنّ الكشف خلا منها**).

**وضابطُ الرجوع:** إرجاعُ `scope.py` إلى `main` ছিল ٣٨/٣٨ خضراء — أي لا ضابطَ للتغيير. وهذا الملفُّ
هو ذاك الضابط: يقرأ التصنيفَ الثلاثيّ صراحةً، ويقيس الوصلَ في المستهلكَين، **ويشترط ألّا تُبتلع
سؤالٌ حقيقيّ** (الصفحةُ المقروءةُ تمرّ) — فالبوّابةُ التي تأكل سؤالًا صحيحًا أسوأُ من العطب الذي بُنيت له.
"""
from __future__ import annotations

import pathlib
import re
import sys
from decimal import Decimal


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from statement_qa import scope  # noqa: E402

YEARS = {2025, 2026}
AMOUNTS = frozenset({Decimal("9001.00"), Decimal("250.00")})
DOC_PAGES = 629                      # **عددُ صفحات الكشف المقيس (قائمةُ الصفحات)**
MAX_READ = 628                       # **أقصى صفحةٍ فيها سطورٌ** (الثلاثُ الباقية بلا سطور)
ROW_READ_PAGES = frozenset(set(range(1, MAX_READ + 1)) - {172, 484, 602})


def _say(q, *, max_page: int | None = MAX_READ, n_pages: int | None = DOC_PAGES,
         pages_read=ROW_READ_PAGES):
    return scope.classify(q, YEARS, max_page, AMOUNTS, n_pages=n_pages, pages_read=pages_read)


# ── ① خارجَ المستند ──────────────────────────────────────────────────────────────────────
def test_a_page_outside_the_document_is_named_as_outside():
    s = _say("ما مجموعُ المبالغ المدينة في تذييل الصفحة ٧٠٠؟")
    assert s.kind == "no_such_data"
    assert "700" in s.answer and "629" in s.answer, "لا يُعلن انتهاءَ المستند عند صفحته الحقيقيّة"
    assert "لم تُقرأ سطورُ 700 بعد" not in s.answer, \
        "النصُّ يوهم بوجود صفحة ٧٠٠ (وهو عطبُ مراجعة ١١٧ المقيس)"


def test_the_five_pack_questions_about_missing_pages_are_named_outside():
    """نطاقُ الحزمةِ المُعلَن قبل الخمسين: `abs-01` · `abs-07` · `abs-09` · `abs-10` · `abs-11`."""
    qs = {"abs-01": "ما مجموعُ المبالغ المدينة في تذييل الصفحة ٧٠٠؟",
          "abs-07": "هل يتّصل رصيدُ الصفحة ٧٠٠ بما بعدها؟",
          "abs-09": "كم صفًّا مطبوعًا في الصفحة ٨٠٠؟",
          "abs-10": "ما أكبرُ مبلغ حركة في الصفحة ٩٠٠؟",
          "abs-11": "ما الرصيدُ الأخير في الصفحة ١٠٠٠؟"}
    for qid, q in qs.items():
        s = _say(q)
        assert s.kind == "no_such_data", f"{qid}: الصفحةُ خارج المستند ولم تُرفض"
        assert "629" in s.answer, f"{qid}: النصُّ لا يسمّي آخرَ صفحةٍ في المستند"


# ── ② داخلَ المستند وبلا سطورٍ (فوق أقصى صفحةٍ فيها سطورٌ) ────────────────────────────────
def test_a_page_inside_the_document_is_never_called_absent():
    """`abs-02`: الصفحة ٦٢٩ **موجودة** (الكشف ٦٢٩ صفحة) وبلا سطورٍ ⇒ تُسمّى داخلةً، لا «غيرَ موجودة»."""
    s = _say("كم صفًّا مطبوعًا في الصفحة ٦٢٩؟")
    assert s.kind == "no_such_data"
    assert "داخلةٌ في الكشف" in s.answer, "لا يُسمّى أنّها داخلٌ في الكشف"
    assert scope.REFUSAL not in s.answer, \
        f"«{scope.REFUSAL}» عن صفحةٍ موجودة — التناقضُ الذي قِيس في ١١٧"
    assert "629" in s.answer


# ── ③ داخلَ المدى وبلا سطورٍ (لا تصل النموذج) ─────────────────────────────────────────────
def test_a_rowless_page_inside_the_range_is_refused_and_named():
    for page in (172, 484, 602):
        s = _say(f"ما أكبرُ مبلغ حركة في الصفحة {page}؟")
        assert s.kind == "no_such_data", f"الصفحة {page}: تمرّ إلى النموذج وهي بلا سطور"
        assert scope.REFUSAL not in s.answer, \
            f"الصفحة {page}: يُقال إنّ الكشف خلا منها — والجدولُ هو ما لا سطورَ فيه"


def test_a_read_page_still_passes():
    """**النقيضُ في الضابط نفسه:** البوّابةُ التي تأكل سؤالًا حقيقيًّا أسوأُ من العطب."""
    for page in (52, 53, 242, 628):
        s = _say(f"ما أكبرُ مبلغ حركة في الصفحة {page}؟")
        assert s.kind == "in_scope", f"الصفحة {page} مقروءةٌ ورُفضت — البوّابةُ ابتلعت سؤالًا"


def test_without_the_document_count_the_gate_stays_honest():
    """**حدُّ المعرفة مُعلَن:** بلا `n_pages` لا يُقال «الكشف ينتهي عند…» ولا «غيرُ موجود»."""
    s = scope.classify("ما الرصيدُ الأخير في الصفحة ١٠٠٠؟", YEARS, MAX_READ, AMOUNTS,
                       pages_read=ROW_READ_PAGES)
    assert s.kind == "no_such_data"
    assert "ينتهي عند" not in s.answer, "ادّعاءُ انتهاءِ الكشف بلا معرفة عدد صفحاته"
    assert scope.REFUSAL not in s.answer


def test_the_three_classes_say_three_different_things():
    outside = _say("ما الرصيدُ الأخير في الصفحة ١٠٠٠؟")
    inside_above = _say("ما الرصيدُ الأخير في الصفحة ٦٢٩؟")
    inside_mid = _say("ما أكبرُ مبلغ حركة في الصفحة ٤٨٤؟")
    kinds = {outside.reason, inside_above.reason, inside_mid.reason}
    assert len(kinds) == 3, f"الأصنافُ الثلاثةُ تُقرأ صنفًا واحدًا: {kinds}"
    answers = {outside.answer, inside_above.answer, inside_mid.answer}
    assert len(answers) == 3, "الثلاثةُ تُقال بالجملة نفسها ⇒ لا يُفرَّق بينها"


# ── ④ الوصل: عددُ الصفحات يصل الحاجزَ من المستهلكَين ──────────────────────────────────────
class _PoisonLLM:
    """**سُمٌّ يُقاس:** إن وصل الحاجزُ إلى النموذج فالاختبارُ يسقط بنصٍّ صريح."""

    def __getattr__(self, name):
        raise AssertionError(f"وصل السؤالُ إلى النموذج (`{name}`) والحاجزُ كان يجب أن يمنعه")


ROWS = [{"page": 1, "date": "2026-01-02", "movement": "100.00", "balance": "4,321.00",
         "side": "debit", "desc": "رسوم"},
        {"page": 3, "date": "2026-01-04", "movement": "50.00", "balance": "950.00",
         "side": "credit", "desc": "تحويل"}]


def test_answer_question_carries_the_page_count_to_the_gate():
    """بلا تمريرِ `n_pages` **لا تُعرَف** الصفحة ٢ (بلا سطورٍ داخل المدى) ⇒ يفوت الحاجزُ إلى النموذج."""
    from statement_qa.qa import answer_question

    res = answer_question(None, "ما أكبرُ مبلغ حركة في الصفحة ٢؟", rows=ROWS,
                          n_pages=4, llm=_PoisonLLM())
    assert res.scope == "no_such_data" and res.answer, "الحاجزُ لم يمنع صفحةً بلا سطور"
    assert "داخلةٌ" in res.answer or "لا سطورَ" in res.answer


def test_the_two_consumers_pass_the_page_count():
    """**الوصلُ مقروءٌ من الملفّين:** التطبيقُ والقياسُ يمرّران عددَ الصفحات — وهو الشقُّ
    الذي قِيس غائبًا (`grep` لـ`n_pages` في المُنادين = صفر)."""
    for rel in ("app.py", "tools/eval_questions.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        calls = [m.start() for m in re.finditer(r"answer_question\(", text)]
        assert calls, f"{rel}: لا نداءَ لـ`answer_question`"
        assert any("n_pages=" in text[i:i + 400] for i in calls), \
            f"{rel}: النداءُ لا يمرّر `n_pages` ⇒ الشقُّ الأوّلُ من البند غائب (R117-2)"
