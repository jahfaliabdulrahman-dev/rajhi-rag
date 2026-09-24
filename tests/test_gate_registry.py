"""**سجلُّ البوّابات مُقابَلٌ بمصدره** (P-8 · تبنّاه المدقّق في مراجعة ٥٥).

**لماذا وُجد:** بوّابتان محلّيّتان لا تعملان إلا في نسخةٍ مُهيّأة، والـCI شغّل **أربعة** ملفّاتٍ فقط —
والمدقّق كشف ذلك بنفسه، ولو كان السجلُّ موجوداً لرآه من أوّل نظرة. ووثيقةُ بوّاباتٍ **لا يُقابَل نصُّها
بمصدرها** تتحوّل إلى قائمةٍ حُرّةٍ تُتقادم بصمت — وهو الصنفُ الذي يُولّد الجولةَ التالية.

**القياسُ هنا ثلاثةُ اتّجاهات، كلُّها مقروءةٌ من الملفّات لا من الذاكرة:**
1. كلُّ ملفٍّ في `.githooks/` مذكورٌ في `docs/GATES.md`.
2. كلُّ `tools/<x>.py` يُنادى من خطّافٍ أو من الـworkflow مذكورٌ في السجلّ.
3. كلُّ ملفِّ اختبارٍ يشغّله الـworkflow مذكورٌ في السجلّ (**الاتجاهُ الذي كان يُخفي النقص**).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "GATES.md"
HOOKS = sorted((ROOT / ".githooks").glob("*"))
WORKFLOW = ROOT / ".github" / "workflows" / "publish-guard.yml"
TOOL_RE = re.compile(r"tools/([A-Za-z0-9_]+\.py)")
TEST_RE = re.compile(r"tests/(test_[A-Za-z0-9_]+\.py)")


def _doc() -> str:
    assert DOC.exists(), "لا سجلَّ بوّابات ⇒ لا مرجعَ يُقابَل (أنشِئه أو لا تدّعِ سجلاً)"
    return DOC.read_text(encoding="utf-8")


def test_every_hook_is_registered():
    """خطّافٌ غيرُ مذكورٍ في السجلّ = بوّابةٌ لا يعرف بها إلا كاتبُها."""
    doc = _doc()
    missing = [p.name for p in HOOKS if p.name not in doc]
    assert not missing, f"خطّافاتٌ خارج السجلّ: {missing} ⇒ أضِفْها إلى docs/GATES.md"


def test_every_tool_called_by_a_gate_is_registered():
    """كلُّ أداةٍ تُنادى من خطّافٍ أو من الـCI يجب أن تكون في السجلّ — وإلّا فالسجلُّ ناقص."""
    doc = _doc()
    called: set[str] = set()
    for p in HOOKS + [WORKFLOW]:
        called |= set(TOOL_RE.findall(p.read_text(encoding="utf-8")))
    missing = sorted(t for t in called if t not in doc)
    assert not missing, f"أدواتُ بوّاباتٍ خارج السجلّ: {missing}"


def test_every_test_ci_runs_is_registered():
    """**الاتجاهُ الذي كشف النقص**: ملفُّ اختبارٍ يشغّله الـCI ولم يُذكر ⇒ «لم أكن أعلم أنّه يعمل»."""
    doc = _doc()
    ran = sorted(set(TEST_RE.findall(WORKFLOW.read_text(encoding="utf-8"))))
    assert ran, "لم أقرأ أيّ ملفِّ اختبارٍ من الـworkflow ⇒ فشلٌ مُغلَق (لا أُعلن تطابقاً لم أقرأه)"
    missing = [t for t in ran if t not in doc]
    assert not missing, f"ملفّاتٌ يشغّلها الـCI وليست في السجلّ: {missing}"


def test_the_registry_declares_where_each_layer_runs():
    """**الحدُّ المُعلَن**: السجلُّ يقول صراحةً أنّ الخطّافين محلّيّان وأنّ الـCI أضيقُ مدىً."""
    doc = _doc()
    for claim in ("core.hooksPath", "محلّيّ فقط", "الـCI يشغّل"):
        assert claim in doc, f"السجلُّ لا يُعلن حدَّه: «{claim}» غائبة ⇒ ادّعاءُ تغطيةٍ بلا إعلان"


def test_the_registry_reports_its_own_blind_spot():
    """وضابطُ السجلّ يذكر **ما لم يُثبت** — سجلٌّ يدّعي الكمال يُناقض غرضه."""
    assert "ما لم يُثبت" in _doc(), "لا قسمَ «ما لم يُثبت» في سجلّ البوّابات"
