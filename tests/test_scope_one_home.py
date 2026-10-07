"""R93-10 — نطاقُ الكشف: **صيغةٌ واحدة، ومصدرٌ واحد، وحزمةٌ تُقاس بما يرسله التطبيق**.

**العطبُ المقيس (مراجعة ٩٣):** أداةُ التقييم (`tools/eval_questions.py`) كانت تنادي `answer_question`
**بلا `scope`**، فالقالبُ يقول «غيرُ مُعلَن» بينما التطبيقُ يرسل «<الاسم> · ٦٢٩ صفحة · <N> حركة مُنظَّمة»
⇒ **الرقمُ المنشور (٤٦/٥٠) يصف تلقينًا لا يراه المستخدم** — وهو صنفُ «نسختين من الحقيقة» في التلقين.

والضوابطُ هنا تقيس الثلاثةَ: الصيغةَ · مَن يُناديها · وما يُمرَّر في كلّ نداء (بالشيفرة لا بالبحث النصّيّ).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytest.importorskip("langchain")

from statement_qa.qa import build_system_prompt, scope_text       # noqa: E402

PROJ = Path(__file__).resolve().parent.parent


def _calls(path: str, func_name: str) -> list[ast.Call]:
    """كلُّ نداءات `func_name` في ملفّ — شجرةُ شيفرةٍ لا بحثٌ نصّيّ (بحثٌ نصّيّ يمرّ على تعليق)."""
    tree = ast.parse((PROJ / path).read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and ((isinstance(n.func, ast.Name) and n.func.id == func_name)
                 or (isinstance(n.func, ast.Attribute) and n.func.attr == func_name))]


def _kw(call: ast.Call) -> set[str]:
    return {k.arg for k in call.keywords if k.arg}


def test_the_scope_has_one_format_and_names_an_unknown_page_count() -> None:
    assert scope_text("slice_629p_v2", 629, 5809, "vlm") == \
        "slice_629p_v2 · 629 صفحة · 5809 حركة مُنظَّمة · قارئ vlm"
    # **وغيابُ العدّ يُسمّى ولا يُطبع صفرًا:** صفرٌ يُقرأ «الكشفُ فارغ» فيُغلق بابَ سؤالٍ صحيح.
    assert "عددُ الصفحات غيرُ معروف" in scope_text("x", 0, 5)
    assert "0 صفحة" not in scope_text("x", 0, 5)
    assert scope_text("", 3, 1) == "الكشف المرفوع · 3 صفحة · 1 حركة مُنظَّمة"


def test_the_app_and_the_harness_build_it_from_the_same_home() -> None:
    """نطاقٌ بصيغتين = رقمان لنفس الشيء ⇒ الاثنان يُناديان `qa.scope_text`."""
    assert "from statement_qa.qa import scope_text" in (PROJ / "app.py").read_text(encoding="utf-8")
    assert _calls("app.py", "_scope_text_of"), "الواجهةُ لا تنادي موضعَ الصيغة الواحد"
    assert _calls("tools/eval_questions.py", "scope_text"), "أداةُ التقييم لا تنادي موضعَ الصيغة الواحد"


def test_the_harness_sends_the_scope_the_app_sends_and_declares_single_turn() -> None:
    """**العضُّ:** النداءُ في الأداة كان بلا `scope` ⇒ يُقاس الآن أنّه يُمرّره، وأنّ غيابَ السجلّ
    **مُعلَنٌ بالبناء** (سؤالٌ واحدٌ في دورةٍ مستقلّة) لا سهوٌ يُقاس عليه رقمٌ تابع."""
    calls = _calls("tools/eval_questions.py", "answer_question")
    assert calls, "لا نداءَ للنموذج في الأداة؟"
    for c in calls:
        kws = _kw(c)
        assert "scope" in kws, "النداءُ بلا نطاق ⇒ الحزمةُ تُقاس بتلقينٍ لا يرسله التطبيق"
        assert "history" not in kws, "الحزمةُ دورةٌ واحدة بالبناء — فلا يُمرَّر سجلّ"


def test_the_app_sends_both_scope_and_history() -> None:
    """والنصفُ الآخر: التطبيقُ يمرّر الاثنين ⇒ فحزمةٌ بنطاقٍ بلا سجلّ تصف **الدورةَ الأولى**،
    وهذا ما يقوله التقريرُ لا أكثر."""
    calls = _calls("app.py", "answer_question")
    assert calls and all({"scope", "history"} <= _kw(c) for c in calls)


def test_the_scope_reaches_the_prompt() -> None:
    """ولا يُكتفى بتمريره: يُقاس أنّه **دخل نصَّ التلقين** فعلًا."""
    text = scope_text("slice_629p_v2", 629, 5809, "")
    prompt = build_system_prompt(scope=text)
    assert text in prompt and "غيرُ مُعلَن" not in prompt
