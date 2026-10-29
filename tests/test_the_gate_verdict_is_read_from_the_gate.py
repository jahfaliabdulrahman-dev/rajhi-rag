"""**R120-1 · R120-2 · وملاحظتا P3 — الحدُّ بين الحاجز والإشارة، والوعدُ بأنّ الوحدةَ تُستورَد بلا pydantic.**

**R120-1 (P2 · مقيس في مراجعة ١٢٠):** `gated = scope != "in_scope" or refused` يقرأ **إشارتين من
حقلٍ واحد**: «منعه الحاجز قبل النموذج» و«أعلن النموذجُ الامتناع». و`refused` صار **مشتقًّا** من
`kind` (قرار `20261014-231500`) ⇒ فجوابٌ أعلن النموذجُ امتناعَه **وحمل مبلغًا بلا سند** يُحسب صحيحًا
بعلّة «بوّابةُ النطاق منعته قبل النموذج» — **وهو ادّعاءٌ لم يقع** (النموذجُ بلغه السؤال)، **وقبولُ
القرار ④ («مبلغٌ بلا سند ⇒ خطأٌ كما كان») مكسور**. والفصلُ: النطاقُ من `scope`، والامتناعُ من `kind`.

**R120-2 (P2):** `ConfigDict` أُضيف إلى `Answer` في R119-1 **ولم يُضَف إلى المسار البديل** (بلا
pydantic) ⇒ `NameError` عند تنفيذ جسم الصنف ⇒ **الوحدةُ لا تُستورَد**، وثلاثةُ ملفّاتٍ تسقط من الجمع
في البيئة الخفيفة. **وقِيس ذلك في نسخةٍ مطابقةٍ لبيئة `ci-claims`: `f3c0a58` ⇒ 943 · `e1cac46` ⇒ 926**
⇒ **فالفرقُ الذي سمّيتُه «انزياحَ بيئة» كان عطبي** (‏−١٩ + ٢ = −١٧) — والسحبُ في موضعٍ منشور بتاريخه.

**وملاحظتا P3:** عدُّ الاختباراتِ يجب أن **يسقط بخطأِ جمع** لا أن يقبله صامتًا؛ ووصفُ `kind` يُرسَل
للنموذج في المخطّط ⇒ فلا يحمل ملاحظةَ هندسةٍ بل تعليمةَ جواب.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tools import eval_questions as ev      # noqa: E402

ROWS: list[dict] = []
#: الملفّاتُ الثلاثةُ التي أسقطها `NameError` في بيئةٍ بلا pydantic (مقيس في المراجعة ١٢٠).
NO_PYDANTIC_FILES = ("tests/test_agent_prompt_memory.py", "tests/test_answer_type.py",
                     "tests/test_the_compound_split_is_measured_not_assumed.py")


def _t(**kw) -> ev._Trace:
    """أثرٌ **بالشكل الذي يُسجّله التشغيل**: `answer_kind` ومعه `refused` المُشتقّ منه.

    **وهذا موضعُ الحرس نفسه:** لو بُني الأثرُ على `answer_kind` وحدَه بلا `refused` لما قِيس
    العطبُ أصلًا (قاسه ضابطُ الطفرة م٨: بلا `refused=True` لا يفرّق الحرسُ بين «الحاجز» و«الإشارة»).
    """
    rec = {"used_row_nos": [], "tools_used": [], "scope": "in_scope", "answer_kind": ""}
    rec.update(kw)
    rec.setdefault("refused", rec["answer_kind"] == "not_found")
    return ev._Trace(rec)


def _q(metric="abstain", expect="abstain", **kw) -> dict:
    q = {"id": "abs-05", "cat": "امتناع", "metric": metric, "expect": expect,
         "derive": {"kind": "x"}}
    q.update(kw)
    return q


# ── ① امتناعٌ مُعلَنٌ ومعه مبلغٌ بلا سند ⇒ خطأٌ في المصحِّحَين ───────────────────────────────
def test_an_abstention_with_an_unsupported_amount_is_wrong_in_both_scorers():
    """**القبولُ الأوّل:** `not_found` مع مبلغٍ بلا سند ⇒ **خطأٌ في المصحِّحين** — وكان الجديدُ
    يعتبره صحيحًا بعلّة الحاجز (`or refused`)، **و٤٤ ضابطًا من ملفّات المصحِّح لم تكشفه**."""
    ans = "لا يظهر في الكشف؛ وأقربُ رقمٍ 2,468.02"
    res = _t(answer_kind="not_found")
    ok_new, why_new = ev.score_answer(_q(), None, ans, res, ROWS)
    ok_old, why_old = ev.score_answer_by_text(_q(), None, ans, _t(answer_kind="not_found"), ROWS)
    assert not ok_new, f"الجديدُ قبِله: {why_new}"
    assert "اختراع" in why_new and "بلا سند" in why_new, why_new
    assert not ok_old, f"القديمُ قبِله: {why_old}"


# ── ② الامتناعُ المُعلَنُ يُنسب إلى الإشارة لا إلى الحاجز ───────────────────────────────────
def test_a_declared_abstention_is_credited_to_the_signal_not_to_the_gate():
    """**القبولُ الثاني:** `not_found` بعبارةٍ ليست في أيّ قائمة ⇒ الجديدُ **صحيحٌ بعلّة
    «امتناعٌ مُعلَن»** (لا بعلّة الحاجز)، **والقديمُ خطأ** (كما في `abs-05` من r108-03)."""
    ans = "لا يَظهر في الكشف رقمُ هويةٍ للمستفيد"
    assert not any(w in ans for w in ev._ABSENCE), "المِثالُ يحمل عبارةً من القائمة ⇒ لا يقيس"
    ok_new, why_new = ev.score_answer(_q(), None, ans, _t(answer_kind="not_found"), ROWS)
    assert ok_new, why_new
    assert "امتناعٌ مُعلَن" in why_new, f"العلّةُ ليست الامتناعَ المُعلَن: {why_new}"
    assert "الحاجز" not in why_new and "النطاق" not in why_new, (
        f"الجوابُ نُسب إلى الحاجز وهو ليس منه: {why_new}")
    ok_old, _ = ev.score_answer_by_text(_q(), None, ans, _t(answer_kind="not_found"), ROWS)
    assert not ok_old, "القديمُ يجب أن يُسقطه (وهو ما يقيس السطرَ المقارِن)"


# ── ③ والحاجزُ يبقى محسوبًا حيث وقع فعلًا ──────────────────────────────────────────────────
def test_a_gate_blocked_question_is_still_credited_to_the_gate():
    """**نقيضٌ في الضابط نفسه:** الفصلُ لا يُلغي الحاجز — سؤالٌ منعه الحاجزُ قبل النموذج يبقى ✓."""
    ok, why = ev.score_answer(_q(), None, "الكشفُ ينتهي عند صفحة ٦٢٩، فلا صفحة ٧٠٠ فيه",
                              _t(scope="out_of_scope", answer_kind=""), ROWS)
    assert ok and "بوّابةُ النطاق" in why, why


# ── ④ الوحدةُ تُستورَد بلا pydantic — كما يعد تعليقُها ─────────────────────────────────────
def _run_blocking_pydantic(code: str) -> subprocess.CompletedProcess:
    """يُشغَّل الكودُ في عمليّةٍ فرعيّة و`pydantic` محجوبٌ من `sys.modules` (‏ImportError مُعلَن)."""
    stub = ("import sys; sys.modules['pydantic'] = None; sys.path.insert(0, "
            f"{str(ROOT / 'src')!r}); sys.path.insert(0, {str(ROOT)!r}); ")
    return subprocess.run([sys.executable, "-c", stub + code],
                          cwd=ROOT, capture_output=True, text=True, timeout=600)


def test_the_module_imports_without_pydantic():
    out = _run_blocking_pydantic(
        "import statement_qa.qa as q; print('PYDANTIC', q._PYDANTIC)")
    assert out.returncode == 0, f"الاستيرادُ بلا pydantic فشل:\n{out.stderr[-400:]}"
    assert "PYDANTIC False" in out.stdout, out.stdout[-200:]


def test_the_three_files_still_import_without_pydantic():
    """**القبولُ بنصّه:** بلا pydantic ⇒ **لا خطأَ جمعٍ** في الملفّات الثلاثة التي سقطت.

    **ويُقاس الاستيرادُ لا تشغيلُ `pytest`:** جمعُ pytest يُشغِّل حزمةَ إضافاتِ البيئة (قِيس في
    هذه الشجرة أنّ حجبَ pydantic يُسقط `langsmith` عبر الإضافات ⇒ العطبُ في مِسبار الجمع لا في
    الوحدة). **والجمعُ == استيرادُ الملفّ:** فمن استورد سليمًا لم يسقط من الجمع.

    **وحدُّ البيئة مُعلَنٌ لا مُقنَّع (قِيس في الـCI):** في بيئةٍ لا تُجمِّع بعضَ الملفّات لتبعيّاتٍ
    غائبة (`pdfplumber` · `polars`) **يُقاس العطبُ المقصودُ وحدَه** (‏`NameError: … ConfigDict`) —
    **وغيره يُعلَن حدًّا ويُتخطّى باسمه**، فلا يُنسب عطبُ بيئةٍ إلى الوحدة ولا العكس.
    """
    code = (
        "import importlib.util as iu, pathlib\n"
        f"files = {list(NO_PYDANTIC_FILES)!r}\n"
        "for f in files:\n"
        "    spec = iu.spec_from_file_location(pathlib.Path(f).stem, f)\n"
        "    m = iu.module_from_spec(spec)\n"
        "    spec.loader.exec_module(m)\n"
        "    print('OK', f)\n"
    )
    out = _run_blocking_pydantic(code)
    text = (out.stdout or "") + (out.stderr or "")
    assert "ConfigDict" not in text and "NameError" not in text, (
        f"عطبُ R120-2 عاد (`ConfigDict` غائبٌ في المسار البديل):\n{text[-400:]}")
    if "ModuleNotFoundError" in text:
        missing = sorted(set(__import__("re").findall(r"No module named '(\w+)'", text)))
        pytest.skip(f"بيئةٌ ناقصةُ تبعيّاتٍ ({' · '.join(missing)}) ⇒ الحدُّ مُعلَنٌ هنا لا مسكوتٌ عنه")
    assert out.returncode == 0, f"استيرادُ الملفّات الثلاثة بلا pydantic فشل:\n{text[-600:]}"
    assert text.count("OK tests/") == len(NO_PYDANTIC_FILES), text[-400:]


# ── ⑥ وصفُ الحقل يذهب للنموذج: تعليمةُ جوابٍ لا ملاحظةُ هندسة ─────────────────────────────
def test_the_kind_description_carries_instructions_only():
    pytest.importorskip("pydantic")     # بلا pydantic لا مخطّطَ يُرسَل أصلًا
    from statement_qa.qa import Answer

    desc = Answer.model_fields["kind"].description or ""
    assert desc.strip(), "الوصفُ فارغ — فلا تعليمةَ للنموذج"
    for note in ("تُعيده المكتبة", "نداءٌ إضافي", "Field required"):
        assert note not in desc, f"ملاحظةُ هندسةٍ تُرسَل إلى النموذج: {note!r}"
    schema = json.dumps(Answer.model_json_schema(), ensure_ascii=False)
    assert "تُعيده المكتبة" not in schema, "المخطّطُ المُرسَل يحمل ملاحظةَ الهندسة"
