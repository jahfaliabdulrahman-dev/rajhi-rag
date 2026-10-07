"""البوّابةُ التي تمنع عودةَ «الميزةُ معلَّنةٌ وخاملة» (R92 · البند ١).

**العلّةُ التي تمنعها:** دالّةُ `ask_followup` في الواجهة تحمل سجلَّ المحادثة بيدها ثمّ **لا تمرّره**
إلى `answer_question` ⇒ الوكيلُ يُسأل كأنّه مبتدأ، والميزةُ موجودةٌ في المسار **وغيرُ مستدعاةٍ من
الواجهة**. فتُقاس هنا **بالـAST** (بلا استيراد Gradio) **وسلوكيًّا** على الدالّة النقيّة.

**وما لا تقيسه:** أن يجيب النموذجُ أحسن — تقيس أنّ المُدخَل **يصل**، لا أن الأثرَ بلغ. ولذلك
يُقاس الأثرُ في جولةٍ مدفوعة، لا هنا.
"""

from __future__ import annotations

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[1] / "app.py"
TREE = ast.parse(APP.read_text(encoding="utf-8"))


def _fn(name: str) -> ast.FunctionDef:
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} غابت من الواجهة — البوّابةُ تفشل معلنةً لا صامتة")


def test_the_ui_passes_history_and_scope_to_the_agent() -> None:
    """**المُدخَلُ يصل:** نداءُ `answer_question` في `ask_followup` يحمل الكلمتين صراحةً."""
    call = None
    for node in ast.walk(_fn("ask_followup")):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "answer_question":
            call = node
    assert call is not None, "الواجهةُ لا تنادي answer_question إطلاقًا"
    kwargs = {k.arg for k in call.keywords}
    assert {"history", "scope"} <= kwargs, f"مُدخَلٌ ناقص: {sorted(kwargs)} — الوكيلُ يُسأل بلا ذاكرة"


def test_the_current_question_is_not_fed_back_as_history() -> None:
    """**لا يُغذّى السؤالُ نفسُه كسجلّ:** `history[:-1]` — والسؤالُ يُضاف في `prepare_ask:953`."""
    src = ast.get_source_segment(APP.read_text(encoding="utf-8"), _fn("ask_followup")) or ""
    assert "history_pairs(history[:-1])" in src, "passes the whole log, so the question feeds itself"
    prep = ast.get_source_segment(APP.read_text(encoding="utf-8"), _fn("prepare_ask")) or ""
    assert '{"role": "user", "content": q}' in prep, "تغيّر موضعُ إضافة السؤال — راجع [:-1]"


def test_the_scope_never_raises_on_a_missing_key() -> None:
    """**النطاقُ لا يُسقط الجواب:** لا اشتراكَ (`STATE["x"]`) داخل `_scope_text` — كلُّها `.get`."""
    bad = [n for n in ast.walk(_fn("_scope_text"))
           if isinstance(n, ast.Subscript) and getattr(n.value, "id", "") == "STATE"]
    assert not bad, f"قراءةٌ بلا حماية في النطاق (سطر {bad[0].lineno})"


def test_history_pairs_pairs_and_ignores_the_dangling() -> None:
    """**الدالّةُ النقيّة:** المستخدمُ يفتح والمساعدُ يُغلق — والناقصُ يُهمَل لا يُخمَّن."""
    from statement_qa.qa import history_pairs
    log = [{"role": "user", "content": "س١"}, {"role": "assistant", "content": "ج١"},
           {"role": "user", "content": "س٢"}, {"role": "assistant", "content": "ج٢"},
           {"role": "user", "content": "س٣"}]
    assert history_pairs(log) == [("س١", "ج١"), ("س٢", "ج٢")], "زوجٌ زائدٌ أو نقصٌ"
    assert history_pairs([{"role": "assistant", "content": "ج"}]) == [], "جوابٌ بلا سؤالٍ لا يُنسب"
    assert history_pairs(None) == [] and history_pairs([]) == []


def test_the_pairs_flow_through_the_bounded_window() -> None:
    """**ومن الأزواج إلى القالب:** النافذةُ تُطبَّق (آخرُ `MEMORY_TURNS`) والإسقاطُ يُعلَن."""
    from statement_qa.qa import MEMORY_TURNS, build_system_prompt, history_pairs
    log = []
    for i in range(MEMORY_TURNS + 2):
        log += [{"role": "user", "content": f"س{i}"}, {"role": "assistant", "content": f"ج{i}"}]
    prompt = build_system_prompt(scope="كشفُ الاختبار", history=history_pairs(log))
    assert prompt.count("سؤالٌ سابق") == MEMORY_TURNS
    assert "أُسقطت" in prompt and "كشفُ الاختبار" in prompt


def test_the_read_button_clears_the_question_surfaces() -> None:
    """**R93-2 (AST):** حدثٌ على زرّ القراءة مخرجاتُه أسطحُ السؤال الأربعة.

    **العلّةُ التي يمنعها:** صارت المحادثةُ مُدخَلًا للنموذج (R92)، فبقاؤها عند قراءة كشفٍ جديد يحمل
    سؤالَ الكشف السابق وجوابَه باستشهاده إلى أسئلة الجديد — وهو الصنفُ الذي أُغلق قبل ٩٢.
    """
    calls = [n for n in ast.walk(TREE)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "click"
             and any(getattr(a, "id", "") == "_reset_qa_surfaces" for a in n.args)]
    assert calls, "لا مسحَ لأسطح السؤال عند القراءة — الذاكرةُ تحمل كشفًا سابقًا إلى كشفٍ جديد"
    wanted = {"chat", "src", "raw", "raw_note"}
    got: set[str] = set()
    for c in calls:
        for kw in c.keywords:
            if kw.arg == "outputs":
                got |= {getattr(e, "id", "") for e in getattr(kw.value, "elts", [])}
    assert wanted <= got, f"أسطحٌ خارج المسح: {sorted(wanted - got)}"


def test_the_reader_records_the_scope_the_prompt_reads() -> None:
    """**R93-1 (AST):** `_process_pdf_locked` تكتب `n_pages` و`source_name` — المفتاحَين الذين يقرأهما
    `_scope_text`. (والقياسُ السلوكيُّ على حالة القارئ في `tests/test_intake.py`.)"""
    body = _fn("_process_pdf_locked")
    written = {n.slice.value for n in ast.walk(body)
               if isinstance(n, ast.Subscript) and getattr(n.value, "id", "") == "STATE"
               and isinstance(n.ctx, ast.Store) and isinstance(n.slice, ast.Constant)}
    assert {"n_pages", "source_name"} <= written, f"مفتاحٌ لا يُكتب: {sorted(map(str, written))}"
