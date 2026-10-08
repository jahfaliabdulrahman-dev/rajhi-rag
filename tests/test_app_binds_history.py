"""البوّابةُ التي تمنع عودةَ «الميزةُ معلَّنةٌ وخاملة» (R92 · وقرار 98ب).

**العلّةُ التي تمنعها:** دالّةُ `ask_followup` كانت تحمل سجلَّ المحادثة بيدها ثمّ **لا تمرّره** إلى
`answer_question` ⇒ الوكيلُ يُسأل كأنّه مبتدأ. فتُقاس هنا **بالـAST** (بلا استيراد Gradio):
المدخلُ يصل (المفتاحُ = بصمةُ الكشف، والنطاق)، والسؤالُ لا يُغذّى نفسه سجلًّا، والقراءةُ تمسح
**ذاكرةَ المحادثة** لا أسطحَ العرض وحدها.

**وما لا تقيسه:** أن يجيب النموذجُ أحسن — تقيس أنّ المُدخَل **يصل**، لا أن الأثرَ بلغ. ولذلك
يُقاس الأثرُ في جولةٍ مدفوعة، لا هنا. (والدالّةُ اليدويّة `history_pairs` محذوفةٌ بقرار 98ب —
فما كان يقيس اقترانَها من ضابطٍ هنا قد **تقاعد مع صاحبته**، ومحلُّه مذكورٌ في تقرير النقل.)
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


def test_the_ui_passes_the_memory_key_and_scope_to_the_agent() -> None:
    """**المُدخَلُ يصل:** نداءُ `answer_question` في `ask_followup` يحمل المفتاحَ والنطاق صراحةً."""
    call = None
    for node in ast.walk(_fn("ask_followup")):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "answer_question":
            call = node
    assert call is not None, "الواجهةُ لا تنادي answer_question إطلاقًا"
    kwargs = {k.arg for k in call.keywords}
    assert {"thread_id", "scope"} <= kwargs, f"مُدخَلٌ ناقص: {sorted(kwargs)} — الوكيلُ يُسأل بلا ذاكرة"


def test_the_current_question_is_not_fed_back_as_history() -> None:
    """**لا يُغذّى السؤالُ نفسُه سجلًّا:** المُدخلُ الوحيدُ للنموذج هو سؤالُ هذه اللحظة (رسائلُ
    الخيط تحمل القديم وحده)، والسؤالُ يُضاف في `prepare_ask` للعرض لا للتلقين."""
    call = next(n for n in ast.walk(_fn("ask_followup"))
                if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "answer_question")
    kwargs = {k.arg for k in call.keywords}
    assert "history" not in kwargs, "سجلٌّ يدويٌّ رجع — والقرار: رسائلُ الحافظة لا نصٌّ يُمرَّر"
    src = ast.get_source_segment(APP.read_text(encoding="utf-8"), _fn("ask_followup")) or ""
    assert "history_pairs(" not in src, "الدالّةُ اليدويّةُ استُدعيت (محذوفةٌ بقرار 98ب)"
    prep = ast.get_source_segment(APP.read_text(encoding="utf-8"), _fn("prepare_ask")) or ""
    assert '{"role": "user", "content": q}' in prep, "تغيّر موضعُ إضافة السؤال — راجع prepare_ask"


def test_the_scope_never_raises_on_a_missing_key() -> None:
    """**النطاقُ لا يُسقط الجواب:** لا اشتراكَ (`STATE["x"]`) داخل `_scope_text` — كلُّها `.get`."""
    bad = [n for n in ast.walk(_fn("_scope_text"))
           if isinstance(n, ast.Subscript) and getattr(n.value, "id", "") == "STATE"]
    assert not bad, f"قراءةٌ بلا حماية في النطاق (سطر {bad[0].lineno})"


def test_the_memory_key_is_the_statement_fingerprint() -> None:
    """**شرط ٢ (قرار 98ب):** معرّفُ المحادثة = **بصمةُ الكشف** (`_ledger_key` ⇒ `statement_key`) —
    مصدرُها واحدٌ مع مفتاح الدفتر، فيقرأ الكشفُ نفسُه المفتاحَ نفسَه."""
    read = APP.read_text(encoding="utf-8")
    ask = ast.get_source_segment(read, _fn("ask_followup")) or ""
    assert "thread_id=_ledger_key()" in ask, "المعرّفُ ليس بصمةَ الكشف — والذاكرةُ تلتصق بغير صاحبها"
    key = ast.get_source_segment(read, _fn("_ledger_key")) or ""
    assert "statement_key(" in key, "مفتاحُ البصمة انقطع عن مصدره (`statement_key`)"


def test_the_read_wipes_the_conversation_too() -> None:
    """**R93-2 (جهةُ الحافظة · شرط ٢):** القراءةُ تمسح **ذاكرةَ المحادثة** لا أسطحَ العرض وحدها
    (`clear_conversation(_ledger_key())`) — وكلُّ سيناريوهات العودة تبدأ نظيفة."""
    reset = ast.get_source_segment(APP.read_text(encoding="utf-8"), _fn("_reset_qa_surfaces")) or ""
    assert "clear_conversation(_ledger_key())" in reset, \
        "القراءةُ لا تمسح ذاكرةَ المحادثة — والقديمُ يعود في كشفٍ جديد (R93-2)"


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
