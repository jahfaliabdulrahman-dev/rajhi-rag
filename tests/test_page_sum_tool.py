"""**R108-1 — مجموعُ صفحةٍ واحدة صار أداةً (بلا نموذجٍ لغويّ · بلا كلفة).**

**العطبُ المقيس في مراجعة ١٠٨ (P2 · قائمٌ على `main` قبل جولة الاسترجاع):** صنفُ `page_sum_all`
(«ما مجموعُ مبالغ الحركات في الصفحة N؟») لم يكن يُجاب صوابًا إلّا **بخرق القاعدة الثانية من تعليمات الوكيل**: الأدواتُ لا
تُخرج مجموعَ صفحةٍ واحدة — `page_summary` تُخرج إجماليَّ المدين وإجماليَّ الدائن **منفصلين**،
و`sum_movements` لا تقبل صفحة، و`page_rows` تسرد الصفوفَ بلا مجموع.

**والمقيس قبل الإصلاح:** في القياسات الخمسة (r93 · r100 · r103 · r105 · r107) **كلُّ جوابٍ صحيحٍ في
هذا الصنف (١٦ جوابًا: `num-02` ×٥ · `num-04` ×٢ · `num-06` ×٥ · `num-08` ×٤) حمل المجموعَ الذي لا
وجودَ له في مخرَج أيّ أداة** ⇒ جمعه النموذجُ بيده. وفي r107 التزم النموذجُ قاعدتَه (`num-08` حمل
الإجماليَّين بلا مجموعهما) **فخسر السؤال** — فالرقمُ المنشور كان يقوم جزئيًّا على حسابٍ يدويّ.

**والعلاجُ في الجذر لا في العَرَض:** القدرةُ تُضاف إلى أداة الجمع القائمة بمعامَل `page`
(كما تأخذه `search_rows`) ⇒ فالجمعُ يجري في الكود، والقاعدةُ الثانيةُ تصير قابلةً للاحترام بلا خسارة.

**ونصفا الضابط (قاعدةُ التخطّي الصامت):**
  · **النصفُ الأوّلُ يعمل في الـCI**: صفوفٌ مصنوعةٌ بلا بياناتٍ ولا نموذج ولا `langchain` ثقيل —
    ويقيس أن مجموعَ الصفحة **يخرج من الأداة**، وأن المُرشِّحَ لا يتسرّب إلى «الكلّ»، وأن صيغةَ
    النداء القديمة (الموضعيّة) لم يتغيّر معناها.
  · **والنصفُ الثاني يقيس الأسئلةَ الأربعةَ الحقيقية** على الكشف، ويُعلن تخطّيه بالاسم حيث لا كشف
    (`require_local_evidence` · `require_run`) — فالقياسُ على الكوربوس لا يُدَّعى في نسخةٍ نقيّة.
"""
from __future__ import annotations

import inspect
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from tests._local_evidence import ROOT, require_local_evidence, require_run

#: نفسُ العيّنة التي تبنيها أداةُ القياس بالافتراض (`tools/eval_questions.py --run`).
RUN = ROOT / "data/local_sample/slice_629p"
QUESTIONS = ROOT / "docs/eval_pack/questions.json"


def _rows() -> list[dict]:
    """صفحتان بمجموعَين **مختلفين عن كلّ بديل** يُقاس عليه.

    الفخُّ المقيس في تصميم الضابط: صفحةٌ مجموعُها يساوي مجموعَ اتجاهٍ فيها، أو يساوي مجموعَ الكشف،
    **لا تكشف** أداةً تُسقط المُرشِّح أو تتجاهل الاتجاه (تعود أخضرَ وهي معطوبة) ⇒ فالصفحة ١:
    مدين 100 + دائن 300 = 400 (ولا واحدٌ من 100 · 300 · 120 · 305.50 · 425.50)،
    والصفحة ٢: 20 + 5.50 = 25.50.
    """
    return [
        {"page": 1, "kind": "opening", "balance": Decimal("0.00"), "movement": None,
         "side": "", "ok": True, "desc": "الرصيد الافتتاحى", "date": None},
        {"page": 1, "kind": "txn", "balance": Decimal("100.00"), "movement": Decimal("100.00"),
         "side": "debit", "ok": True, "desc": "سحب الصراف الآلي", "date": None},
        {"page": 1, "kind": "txn", "balance": Decimal("400.00"), "movement": Decimal("300.00"),
         "side": "credit", "ok": True, "desc": "تحويل وارد", "date": None},
        {"page": 2, "kind": "opening", "balance": Decimal("400.00"), "movement": None,
         "side": "", "ok": True, "desc": "رصيد سابق", "date": None},
        {"page": 2, "kind": "txn", "balance": Decimal("380.00"), "movement": Decimal("20.00"),
         "side": "debit", "ok": True, "desc": "مشتريات (نقاط بيع)", "date": None},
        {"page": 2, "kind": "txn", "balance": Decimal("374.50"), "movement": Decimal("5.50"),
         "side": "credit", "ok": True, "desc": "تحويل وارد", "date": None},
    ]


def _tool():
    from statement_qa.qa_tools import make_qa_tools

    return {t.name: t for t in make_qa_tools(_rows())}["sum_movements"]


# ── النصفُ الأوّل: يعمل في الـCI (بلا بياناتٍ ولا نموذج) ──────────────────────────────────────────
def test_a_single_page_total_comes_out_of_the_tool():
    """**المجموعُ المطلوبُ يخرج من الأداة** — لا يُجمع في الرأس."""
    call = _tool()
    out1 = call.invoke({"page": 1})
    assert "المجموع = 400.00" in out1, out1          # 100 + 300
    assert "عدد الحركات = 2" in out1, out1
    out2 = call.invoke({"page": 2})
    assert "المجموع = 25.50" in out2, out2           # 20 + 5.50


def test_the_page_filter_does_not_leak_into_the_whole_bank():
    """**وضابطُ النقيض:** لولا هذان السطران لمرّت أداةٌ تتجاهل `page` وتُعيد مجموعَ الكشف."""
    call = _tool()
    assert "المجموع = 425.50" in call.invoke({}), call.invoke({})                 # الكشف كلُّه
    assert "المجموع = 120.00" in call.invoke({"side": "مدين"}), call.invoke({"side": "مدين"})
    assert "المجموع = 305.50" in call.invoke({"side": "دائن"}), call.invoke({"side": "دائن"})
    # **والفلتران معًا:** صفحةٌ واتجاهٌ — لا صفًّا من صفحةٍ أخرى ولا اتجاهًا آخر
    both = call.invoke({"page": 1, "side": "مدين"})
    assert "المجموع = 100.00" in both and "عدد الحركات = 1" in both, both


def test_a_page_without_movements_is_declared_not_invented():
    """صفحةٌ لا حركاتَ فيها **تُعلن** — لا صفرٌ مُخترَع ولا مجموعُ الكشف."""
    out = _tool().invoke({"page": 9})
    assert "لا توجد حركات مطابقة" in out, out


def test_page_is_keyword_only_so_the_old_positional_calls_keep_their_meaning():
    """**حدُّ التوافق** (نفسُ ما تُعلنه `search_rows`): `page` لفظيٌّ وحدَه ⇒ نداءٌ موضعيٌّ قديم
    بأربعة أوسِطة يحمل معناه السابق ولا يقع على المعامَل الجديد."""
    sig = inspect.signature(_tool().func)
    assert "page" in sig.parameters, "الأداةُ لا تقبل `page` ⇒ القدرةُ لم تُضَف"
    assert sig.parameters["page"].kind is inspect.Parameter.KEYWORD_ONLY, \
        "`page` ليس لفظيًّا ⇒ نداءٌ موضعيٌّ قديمٌ قد يقع عليه بصمت"
    tool = _tool()
    assert "المجموع = 120.00" in tool.func("مدين"), "النداءُ الموضعيُّ القديم تغيّر معناه"
    with pytest.raises(TypeError):
        tool.func("الكل", "", "", None, 1)


# ── النصفُ الثاني: الأسئلةُ الأربعةُ الحقيقية — يُقاس حيث يوجد الكشف ─────────────────────────────
def _questions() -> list[dict]:
    d = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    return d["questions"] if isinstance(d, dict) and "questions" in d else d


def test_every_real_page_sum_question_is_answerable_by_one_tool_call():
    """**لكلّ سؤالٍ من الأربعة: مخرَجُ الأداة يحمل المتوقَّعَ المشتقَّ نفسَه.**

    والمتوقَّعُ يُشتقّ **بمُشتقّ الحزمة نفسِه** (`tools/eval_questions.derive` ⇒ مجموعُ `movement`
    لكلّ صفوف الصفحة، وقارئُه `Corpus` = قارئُ الحزمة) — فلا حاكمَ ثانٍ ولا رقمٌ بيد.
    """
    require_local_evidence()
    require_run(RUN)
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))
    from tools.eval_questions import Corpus, num
    from tools.refusal_test import build_rows

    from statement_qa.qa_tools import make_qa_tools

    rows, _n_pages = build_rows(RUN)
    tool = {t.name: t for t in make_qa_tools(rows)}["sum_movements"]
    corpus = Corpus(RUN, [])
    four = [q for q in _questions() if (q.get("derive") or {}).get("kind") == "page_sum_all"]
    assert len(four) == 4, f"عائلةُ `page_sum_all` ليست ٤ بل {len(four)}"

    bad: list[tuple] = []
    for q in four:
        page = q["derive"]["page"]
        vals = [num(r.get("movement")) for r in corpus.rows(page)]
        expected = round(sum(v for v in vals if v is not None), 2)
        out = str(tool.invoke({"page": page}))
        got = num(out.split("المجموع =", 1)[-1].split("ريال", 1)[0])
        if got is None or round(got, 2) != expected:
            bad.append((q["id"], page, expected, got, out[:90]))
    assert not bad, f"مخرَجُ الأداة لا يحمل المتوقَّعَ المشتقّ: {bad}"
    print(f"\nصفحاتٌ مجموعُها من الأداة: {len(four)} سؤالًا ⇒ كلُّها تطابق مشتقَّ الحزمة")


def test_the_fourth_page_sum_question_is_not_the_one_that_flipped():
    """**لا يُنسَب الانقلابُ إلى السؤال الخطأ (درسُ R108-2):** `num-08` (الصفحة ٤٨٦) هو الذي سقط في
    r107 بسبب غياب هذه القدرة — وحدُّ الضابط أن الأربعةَ **كلَّها** في العائلة، فلا يُصلَح واحدٌ
    ويُترك ثلاثة (وهو ما يكشفه العددُ المشتقّ أعلاه لا العين)."""
    ids = {q["id"] for q in _questions() if (q.get("derive") or {}).get("kind") == "page_sum_all"}
    assert ids == {"num-02", "num-04", "num-06", "num-08"}, ids
    assert Path(QUESTIONS).exists()
