"""**قرار المالك `20261014-231500` — المصحِّحُ يقرأ نوعَ الجواب لا عباراتِه.**

**العطبُ المقيس (مراجعة ١١٨ · بلا كلفة):** كان الحكمُ بالامتناع والتعادل يُقرأ من **قائمتَي عبارات**
في أداة القياس (`_ABSENCE` · `_AMBIG`) ⇒ فقِيس أنّ `abs-05` في `answers-r108-03.json`
**امتنع بـ«لا يظهر» فحُسب خطأً**، وأنّ `abs-05` نفسه حمل `refused=False` (الحقلُ المُهيكلُ الذي
وُجد لهذا، ولم يملؤه النموذجُ لأنّه **افتراضيّ**). ⇒ والقائمةُ لا تصلح شاهدًا، **والإصلاحُ ليس
إضافةَ عبارةٍ إليها** (وذلك ترقيعٌ).

**والثوابتُ (قرار المالك):** ① الإشارةُ **مُهيكلةٌ** يحملها الجواب (`Answer.kind` من تعدادٍ صريح)
② ومصدرُها **واحدٌ** في التطبيق والقياس (نفسُ مسار `answer_question`) ③ والخمسون تُصحَّح
بالمصحِّحَين ويُطبعان في سطرٍ واحد، ويُسمّى كلُّ اختلافٍ بسببِه ④ والانقلابُ في الرقم يُعلَن
⑤ وتغييرُ المخطّط/التلقين يُرجع الخليّة إلى **«قيد إعادة التأهيل»** (`docs/product-journey.md` §٦).

**والأحمرُ أوّلًا:** ضابطٌ ١ و٢ و٣ أدناه **يُسقطه المصحِّحُ القديمُ على `13fb534`** (ويُقاس في
الجولة بأمرٍ واحد: `git stash` للوحدة ثمّ تشغيلُ هذا الملفّ).
"""
from __future__ import annotations

import ast
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tools import eval_questions as ev  # noqa: E402


def _trace(**kw) -> ev._Trace:
    """أثرُ جوابٍ محفوظ — الشكلُ الذي يقرؤه المصحِّحُ (بلا نداءِ نموذج)."""
    rec = {"used_row_nos": [], "tools_used": [], "scope": "in_scope", "answer_kind": ""}
    rec.update(kw)
    return ev._Trace(rec)


def _q(metric="abstain", expect="abstain", **kw) -> dict:
    q = {"id": "abs-05", "cat": "امتناع", "metric": metric, "expect": expect,
         "derive": {"kind": "x"}}
    q.update(kw)
    return q


ROWS: list[dict] = []


# ── ① امتناعٌ بعبارةٍ ليست في أيّ قائمة، ويحمل الإشارة ⇒ صحيح ─────────────────────────────
def test_a_novel_abstention_phrase_with_the_signal_is_correct():
    ans = "لا يَظهر في الكشف رقمُ هوية للمستفيد، ولن أخترع رقمًا."
    assert not any(w in ans for w in ev._ABSENCE), "المِثالُ يحمل عبارةً من القائمة ⇒ لا يقيس الجديد"
    ok, why = ev.score_answer(_q(), None, ans, _trace(answer_kind="not_found"), ROWS)
    assert ok, f"امتناعٌ مُعلَنٌ بالإشارة حُسب خطأً: {why}"
    assert "not_found" in why, "الحكمُ لا يسمّي الإشارة التي قرأها"
    # **والنقيضُ الذي يعضّ:** المصحِّحُ القديمُ على الجواب نفسِه يُسقطه (وهو عطبُ مراجعة ١١٨)
    ok_old, _why_old = ev.score_answer_by_text(_q(), None, ans, _trace(answer_kind="not_found"), ROWS)
    assert not ok_old, "المصحِّحُ القديم لم يُسقط الامتناعَ بعبارةٍ جديدة ⇒ فالضابطُ لا يعضّ"


# ── ② عبارةٌ في القائمة والإشارةُ تقول «رقم» ⇒ الإشارةُ هي الحاكمة ───────────────────────
def test_the_list_phrase_does_not_override_the_signal():
    ans = "غير موجود في الكشف"
    assert any(w in ans for w in ev._ABSENCE), "المِثالُ ليس من عبارات القائمة ⇒ لا يقيس النقيض"
    ok_new, why_new = ev.score_answer(_q(), None, ans, _trace(answer_kind="figure"), ROWS)
    ok_old, _ = ev.score_answer_by_text(_q(), None, ans, _trace(answer_kind="figure"), ROWS)
    assert not ok_new, f"عبارةُ القائمة غلبت الإشارة ⇒ الحكمُ ما زال نصّيًّا: {why_new}"
    assert ok_old, "القديمُ يجب أن يمرّ على العبارة (وهو ما يقيس السطرَ المقارِن)"


# ── ③ تعادلٌ مُعلَنٌ بالإشارة ⇒ صحيح · وجزمٌ بصفٍّ واحدٍ ⇒ خطأ ──────────────────────────
def test_a_declared_tie_is_read_from_the_signal():
    ans = "أكبرُ مبلغٍ في الصفحة ٢ هو 2,468.02 في الصف 12."      # بلا ألفاظ التعادل
    q = _q(expect="ambiguous")
    ok, why = ev.score_answer(q, None, ans, _trace(answer_kind="tie"), ROWS)
    assert ok, f"تعادلٌ مُعلَنٌ بالإشارة حُسب خطأً: {why}"
    ok_old, _ = ev.score_answer_by_text(q, None, ans, _trace(answer_kind="tie"), ROWS)
    assert not ok_old, "القديمُ ما زال يقرأ النصّ ⇒ الضابطُ يقيس فرقًا حقيقيًّا"
    # **والنقيض:** جزمٌ بصفٍّ واحد (بلا إشارة تعادل) ⇒ خطأ كما كان
    ok_bad, why_bad = ev.score_answer(q, None, ans, _trace(answer_kind="figure"), ROWS)
    assert not ok_bad and "التعادل" in why_bad, why_bad


# ── ④ ادّعاءُ مبلغٍ بلا سندٍ ⇒ خطأٌ كما كان ──────────────────────────────────────────────
def test_a_claim_without_evidence_is_still_wrong():
    ans = "المبلغُ 2,468.02 في الصف 12."
    ok, why = ev.score_answer(_q(), None, ans, _trace(answer_kind="figure"), ROWS)
    assert not ok and "اختراع" in why, why
    assert "بلا سند" in why, why


# ── ⑤ لا حكمَ يقرأ القائمتين — والقراءةُ الوحيدةُ في القديم ───────────────────────────────
def _enclosing(src: str, name: str) -> set[str]:
    tree = ast.parse(src)
    found: set[str] = set()
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and node.id == name:
                found.add(fn.name)
    return found


def test_no_verdict_reads_the_phrase_lists():
    src = pathlib.Path(ev.__file__).read_text(encoding="utf-8")
    for name in ("_ABSENCE", "_AMBIG"):
        readers = _enclosing(src, name)
        assert readers == {"score_answer_by_text"}, (
            f"`{name}` تُقرأ في {sorted(readers)} — والحكمُ المنشورُ لا يقرأ قائمةَ عبارات "
            "(قرار 231500؛ والقديمُ وحدَه يقيسها في السطر المقارِن)")
        assert name not in _enclosing(src, name).union(
            {f.name for f in ast.walk(ast.parse(src)) if isinstance(f, ast.FunctionDef)
             and f.name == "score_answer"}), f"`{name}` عادت إلى الحكم المعمول به"


# ── ⑥ الإشارةُ مطلوبةٌ في المخطّط (فلا يتركها النموذجُ فارغة) ─────────────────────────────
def test_the_signal_is_required_by_the_answer_schema():
    from statement_qa.qa import Answer

    assert "kind" in Answer.model_fields, "لم يبقَ حقلُ النوع في مخطّط الجواب"
    assert Answer.model_fields["kind"].is_required(), (
        "النوعُ افتراضيّ ⇒ يُترك فارغًا كما كان `refused` (وهو عطبُ r108-03)")
    schema = Answer.model_json_schema()
    kinds = str(schema)
    for value in ("figure", "not_found", "tie"):
        assert value in kinds, f"التعدادُ لا يعرض `{value}` للنموذج"


def test_the_refusal_boolean_is_derived_not_stored_twice():
    """**مصدرٌ واحدٌ للإشارة (قرار 231500 البند ٢):** لا حقلَ `refused` يُخزَّن إلى جانب النوع."""
    import dataclasses

    from statement_qa.qa import QAResult

    fields = {f.name for f in dataclasses.fields(QAResult)}
    assert "answer_kind" in fields and "refused" not in fields, (
        f"حقلان لنفس المعنى: {sorted(fields)}")
    assert QAResult(answer="x", sources=[], answer_kind="not_found").refused is True
    assert QAResult(answer="x", sources=[], answer_kind="figure").refused is False


# ── ⑦ السطرُ المقارِنُ يُطبع (وكلُّ اختلافٍ يُسمّى بسببِه) ────────────────────────────────
def test_the_comparator_line_is_printed_with_reasons():
    src = pathlib.Path(ev.__file__).read_text(encoding="utf-8")
    assert "بالجديد" in src and "وبالقديم" in src, "لا سطرَ مقارِنًا للمصحِّحَين (قرار 231500)"
    assert "why_by_text" in src, "الاختلافُ لا يُسمّى بسببٍ من القديم"
    assert "why_by_text" in src.split("def _print_metrics")[1][:4000], \
        "السطرُ المقارِنُ في الطباعة لا يسمّي سببَ الاختلاف"


# ── ⑧ السطرُ المقارِنُ يُقاس بمخرَجه لا بقراءة نصّه ────────────────────────────────────────
def test_the_comparator_line_reports_both_and_names_the_reason(capsys):
    """**القبولُ البند ٣:** يُطبعان في سطرٍ واحد، **وكلُّ سؤالٍ اختلف حكمُه يُسمّى بسببه**."""
    def rec(qid, metric, ok, ok_text, why, why_text):
        return {"id": qid, "metric": metric, "expect": "number", "kind": "footer",
                "ok": ok, "ok_by_text": ok_text, "why": why, "why_by_text": why_text}

    rows = [rec("num-01", "number", True, True, "المتوقَّع وُجد", "المتوقَّع وُجد"),
            rec("cit-01", "citation", True, True, "أصابت الصفحة", "أصابت الصفحة"),
            rec("abs-05", "abstain", True, False,
                "امتناعٌ مُعلَن بلا مبلغٍ مُخترع ✓ (إشارةُ الجواب: not_found)",
                "**لم يُعلن امتناعاً** ✗ (ولا ادّعى مبلغاً · مطابقةُ عبارات)")]
    ev._print_metrics(rows)
    out = capsys.readouterr().out
    line = next((ln for ln in out.splitlines() if "بالجديد" in ln), "")
    assert line, f"لا سطرَ مقارِنًا للمصحِّحَين: {out[-400:]}"
    assert "وبالقديم" in line, f"السطرُ لا يحمل القديم: {line!r}"
    assert "3/ 3" in line and "2/ 3" in line, (
        f"العددان في السطر نفسِه غائبان (الجديد ٣/٣ والقديم ٢/٣): {line!r}")
    tail = out.split("اختلف الحكم", 1)[-1]
    assert "abs-05" in tail, f"السؤالُ المختلف لم يُسمَّ: {tail[:200]}"
    assert "إشارةُ الجواب" in tail and "مطابقةُ عبارات" in tail, \
        f"السببُ من كلّ مصحِّح غائب: {tail[:300]}"
    assert "num-01" not in tail and "cit-01" not in tail, \
        "سؤالٌ متّفقٌ عليه دخل قائمةَ الاختلاف (والقائمةُ تُقرأ عددًا)"


# ── ⑨ سجلٌّ قبل المخطّط الجديد لا يُحكم عليه بالإشارة (بل يُسمّى عطبَ مرسًى) ───────────────
def test_a_record_from_before_the_schema_is_not_judged_by_the_signal():
    """سجلُّ r93..r108 لا يحمل `answer_kind` ⇒ فحكمُه بالمصحِّح الجديد ادّعاءٌ لما لم يُسجَّل."""
    old_record = {"used_row_nos": [], "tools_used": [], "scope": "in_scope"}      # بلا الحقل
    res = ev._Trace(old_record)
    assert res.answer_kind_recorded is False
    ok, why = ev.score_answer(_q(), None, "لا يظهر في الكشف", res, ROWS)
    assert not ok and "عطبُ مرسًى" in why and "قبل إشارة" in why, why
    # **والجديدُ يحمل الحقل ⇒ يُحكم:** الفرقُ بين «فارغةٍ معلَنة» و«غيرِ محفوظةٍ أصلًا»
    fresh = ev._Trace({"used_row_nos": [], "tools_used": [], "scope": "in_scope", "answer_kind": ""})
    assert fresh.answer_kind_recorded is True


# ── ⑩ الإشارةُ تُسجَّل بقيمتها لا باسم صنفها — **مقيسةً من مسار التحليل الحقيقيّ** ─────────────
def test_the_field_holds_the_value_not_the_enum_member():
    """**R119-1 (P1 · مراجعة ١١٩):** العضوُ في تعدادٍ مُختلطٍ بـ`str` يُصيغ نفسَه باسم صنفه
    (‏`str(AnswerKind.NOT_FOUND)` = `'AnswerKind.NOT_FOUND'` · قِيس في ٣٫١١ و٣٫١٣) ⇒ فالقيمةُ
    لا تبلغ أحدًا. وهذه الضابطةُ تسقط إن أُزيل `use_enum_values` (ولا بديلَ صامتَ في موضع القراءة)."""
    from statement_qa.qa import Answer, AnswerKind

    a = Answer(kind=AnswerKind.NOT_FOUND, answer="لا يظهر في الكشف", cited_row_ids=[])
    assert a.kind == "not_found", f"الحقلُ يحمل العضوَ لا القيمة: {a.kind!r}"
    assert type(a.kind) is str, f"نوعُ الحقل ليس نصًّا: {type(a.kind)}"
    b = Answer(kind="tie", answer="متعادلان", cited_row_ids=[])
    assert b.kind == "tie" and type(b.kind) is str
    # **وما يراه المستهلكُ من موضع القراءة نفسِه** (لا بتعبيرٍ مُعاد كتابتُه في الضابط):
    assert str(getattr(a, "kind", "") or "") == "not_found"


def _typed_model(kind: str):
    """نموذجٌ مُبرمَج يسلّم `Answer` بالنوع المطلوب — كما يفعله النموذجُ الحقيقيّ."""
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    class _M(BaseChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kw):
            if any(isinstance(x, ToolMessage) for x in messages):
                return ChatResult(generations=[ChatGeneration(message=AIMessage("تم"))])
            call = {"name": "Answer", "id": "a1", "type": "tool_call",
                    "args": {"kind": kind, "answer": "لا يظهر في الكشف", "cited_row_ids": []}}
            return ChatResult(generations=[ChatGeneration(message=AIMessage("", tool_calls=[call]))])

        def bind_tools(self, tools, **kw):
            return self

        def with_structured_output(self, schema, **kw):
            return self

        @property
        def _llm_type(self):
            return "typed-r119"

    return _M()


def test_a_typed_answer_from_a_scripted_model_reaches_the_scorer():
    """**القبولُ بنصّه (R119-1):** جوابٌ مُنوَّعٌ من نموذجٍ مُبرمَج ⇒ `answer_question` ⇒
    `answer_kind == "not_found"` و`refused is True` ⇒ والمصحِّحُ يحكم «امتناعٌ مُعلَن». قِيس على
    `f3c0a58` **`'AnswerKind.NOT_FOUND'` و`refused=False`** (فالإشارةُ كانت تُسجَّل باسم الصنف).

    **والسؤالُ غيرُ رقميّ عن قصد:** سؤالٌ رقميٌّ يُجاب بجوابٍ مُنوَّعٍ بلا نداءِ أداة ٍيُشعل بوّابةَ
    «لا رقمَ بلا أداة» (وهي تُصفّر `parsed` لأنّ الجوابَ لم يُحسَب) — فتُقاس الإشارةُ حيث تمرّ.
    """
    import pytest as _pytest

    _pytest.importorskip("langchain")
    _pytest.importorskip("langgraph")
    from statement_qa.qa import answer_question

    class _NoStore:
        def similarity_search_with_score(self, *_a, **_k):
            return []

    rows = [{"page": 1, "row": 1, "page_row": 1, "date": "2026-01-02", "movement": "100.00",
             "balance": "4,321.00", "debit": "100.00", "credit": None, "description": "رسوم",
             "desc": "رسوم", "kind": "txn"}]
    res = answer_question(_NoStore(), "ما عنوانُ الفرع الذي نُفِّذت فيه حركة الصفحة ١؟",
                          rows=rows, llm=_typed_model("not_found"))
    assert res.answer_kind == "not_found", f"الإشارةُ المُسجَّلة: {res.answer_kind!r} (R119-1)"
    assert res.refused is True, "الامتناعُ لم يُشتقّ من الإشارة"
    ok, why = ev.score_answer(_q(), None, res.answer, _trace(answer_kind=res.answer_kind), ROWS)
    assert ok and "إشارةُ الجواب" in why, f"المصحِّحُ لم يرَ الامتناعَ المُعلَن: {why}"

    tie = answer_question(_NoStore(), "ما عنوانُ الفرع الذي نُفِّذت فيه حركة الصفحة ١؟",
                          rows=rows, llm=_typed_model("tie"))
    assert tie.answer_kind == "tie" and tie.refused is False, (tie.answer_kind, tie.refused)
    ok_tie, _ = ev.score_answer(_q(expect="ambiguous"), None, tie.answer,
                                _trace(answer_kind=tie.answer_kind), ROWS)
    assert ok_tie, "تعادلٌ أعلنه النموذجُ لم يُقرأ"


# ── R121-3: مسارُ الجولة يُحكَم بالأثر الذي يكتبه — والإشارةُ تُحمَل من ناتج التحليل ─────────
class _Result:
    """ناتجُ تحليلٍ بشكلٍ حقيقيّ (‏`QAResult`) — بلا نداءِ نموذج."""

    def __init__(self, kind: str = "not_found"):
        self.answer = "لا يَظهر في الكشف رقمُ هويةٍ للمستفيد"
        self.used_row_nos = [1, 2]
        self.tools_used = ["page_rows"]
        self.scope = "in_scope"
        self.answer_kind = kind
        self.refused = kind == "not_found"


def test_the_box_carries_the_signal_the_analysis_produced():
    """**عطبٌ مقيسٌ في مسار الجولة (R121-3):** كان الصندوقُ يُبنى بيده في `_ask` **بلا `answer_kind`**
    ⇒ فكلُّ سؤالٍ يُحكم «عطبَ مرسًى» **والمصحِّحُ الجديدُ لا يعمل في الجولة أصلًا**، والسجلُّ يُكتب
    بـ`answer_kind=""` ⇒ **تُفقد الإشارةُ من الدليل** (قِيس: جولتان `kind=''` ثمّ أُوقفت الجولة).
    **والحرسُ يقيس الحدَّ من جانبه الصحيح:** ناتجُ تحليلٍ ⇒ `box_of` ⇒ `trace_of` ⇒ حكمٌ بالامتناع."""
    box = ev.box_of(_Result())
    assert box["answer_kind"] == "not_found", box
    tr = ev.trace_of(box)
    assert tr is not None and tr.answer_kind_recorded is True, "الإشارةُ غيرُ مسجّلةٍ في أثر الجولة"
    assert tr.answer_kind == "not_found", tr.answer_kind
    ok, why = ev.score_answer(_q(), None, box["answer"], tr, ROWS)
    assert "عطبُ مرسًى" not in why, f"الجولةُ تُحكم عطبَ مرسًى: {why}"
    assert ok and "امتناعٌ مُعلَن" in why, why


def test_the_trace_a_run_judges_is_the_one_it_writes():
    """**والمسارُ الذي يُحكَم به هو المسارُ الذي يُكتب** — السجلُّ يُبنى من الأثر نفسه لا من نسخةٍ ثانية."""
    box = ev.box_of(_Result(kind="tie"))
    tr = ev.trace_of(box)
    rec = {"used_row_nos": tr.used_row_nos, "tools_used": tr.tools_used, "scope": tr.scope,
           "answer_kind": tr.answer_kind, "refused": tr.refused}
    assert "answer_kind" in rec and rec["answer_kind"] == "tie", rec
    assert ev._Trace(rec).answer_kind_recorded is True
    ok, why = ev.score_answer(_q(metric="abstain", expect="ambiguous"), None, box["answer"],
                              ev._Trace(rec), ROWS)
    assert ok and "التعادل" in why, why


def test_the_run_path_has_one_home_for_the_box_and_the_trace():
    """**ولا يُبنى الصندوقُ في مكانين (P2: كودٌ يكرّر مكوّنًا متاحًا عيبٌ):** يُقاس بالـAST أنّ `_ask`
    يستدعي `box_of(` وأنّ أثرَ الجولة يُبنى بـ`trace_of(` — فلا يعود العطبُ بصمتٍ في موضعٍ آخر."""
    tree = ast.parse((ROOT / "tools/eval_questions.py").read_text(encoding="utf-8"))
    calls = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "box_of" in calls, "لا دالّةَ `box_of` في الوحدة ⇒ الصندوقُ يُبنى بيده"
    assert "trace_of" in calls, "لا دالّةَ `trace_of` ⇒ الأثرُ يُبنى بيده"
    src = (ROOT / "tools/eval_questions.py").read_text(encoding="utf-8")
    assert src.count("out_box.update(box_of(") == 1, "بناءُ الصندوق ليس في موضعٍ واحد"
    assert src.count("res = trace_of(msg)") == 1, "أثرُ الجولة ليس من الموضع الواحد"
    # والمطبوعاتُ القديمة لم تبقَ: لا أثرَ مبنيًّا بيدٍ في مسار الجولة
    legacy = 'msg.get("refused")}) if "answer" in msg else None'
    assert legacy not in src, "ما زال الأثرُ يُبنى بيدٍ في مسار الجولة"
