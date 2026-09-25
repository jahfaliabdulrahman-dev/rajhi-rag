"""**سجلُّ البوّابات مُقابَلٌ بمصدره** (P-8 · تبنّاه المدقّق في مراجعة ٥٥).

**لماذا وُجد:** بوّابتان محلّيّتان لا تعملان إلا في نسخةٍ مُهيّأة، وقائمةُ ما يشغّله الـCI كانت أقصرَ ممّا
يظنّ الجميع. ووثيقةُ بوّاباتٍ **لا يُقابَل نصُّها بمصدرها** تصير قائمةً حُرّةً تُتقادم بصمت — وهو ما قاسه
المقاعدُ الثلاثة في نسختها الأولى: السجلُّ أعلن «أربعة ملفّات» وفي الالتزام نفسه صارت ثمانية، وقال
«٦٨٥ ضابطاً» والمقيس ٦٩٥، ونسب إلى ضابطٍ سمَّ بوّابةً لا يمسّها.

**الاتّجاهاتُ الأربعة (كلُّها مقروءةٌ من الملفّات، ولا واحدٌ منها «حضورُ نصّ» وحده):**
1. كلُّ ملفٍّ في `.githooks/` وكلُّ `tools/*.py` يُنادى من خطّافٍ أو من الـworkflow مذكورٌ في السجلّ.
2. **قائمةُ الـCI المُعلَنة = مجموعةُ ملفّات `pytest` في الـworkflow** (تساوياً لا احتواءً).
3. **كلُّ أداةٍ في صفوف السجلّ لها ملفُّ ضابطٍ يذكرها** ⇒ لا ثقةَ غيرَ مكتسَبة في عمود «سمُّها».
4. **أيّ عبارةٍ عدديّة عن الـCI تطابق العددَ المقيس** (الأرقامُ والكلماتُ العدديّة كلتاهما).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "GATES.md"
HOOKS = sorted(p for p in (ROOT / ".githooks").glob("*") if p.is_file())
WORKFLOW = ROOT / ".github" / "workflows" / "publish-guard.yml"
TOOL_RE = re.compile(r"tools/([A-Za-z0-9_]+\.py)")
TEST_RE = re.compile(r"tests/(test_[A-Za-z0-9_]+\.py)")
ROW_TOOL_RE = re.compile(r"^\|\s*\d+\s*\|.*?`tools/([A-Za-z0-9_]+\.py)", re.M)
#: كلماتُ العدد التي وردت فعلًا في النسخة المتقادمة («أربعة ملفّات») — فالحراسةُ تشملها لا الأرقامَ وحدها.
WORD_NUM = {"أربعة": 4, "أربع": 4, "خمسة": 5, "خمس": 5, "ستة": 6, "ستّ": 6, "سبعة": 7, "ثمانية": 8, "ثماني": 8}


def _doc() -> str:
    assert DOC.exists(), "لا سجلَّ بوّابات ⇒ لا مرجعَ يُقابَل (أنشِئه أو لا تدّعِ سجلاً)"
    return DOC.read_text(encoding="utf-8")


def _workflow_tests() -> list[str]:
    return sorted(set(TEST_RE.findall(WORKFLOW.read_text(encoding="utf-8"))))


def _declared_ci_tests() -> list[str]:
    """قائمةُ الـCI كما يُعلنها السجلّ: الكتلةُ المُسيَّجة التي تلي «بالضبط:»."""
    doc = _doc()
    marker = "بالضبط:"
    assert marker in doc, "لا إعلانَ لقائمة الـCI في السجلّ ⇒ لا قابليةَ للتساوي"
    block = doc.split(marker, 1)[1]
    block = block.split("```", 2)[1] if "```" in block else block
    return sorted(set(TEST_RE.findall(block)))


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


def test_the_declared_ci_list_equals_the_workflow_list():
    """**الاتّجاهُ الذي كشف التناقض**: قائمةُ السجلّ والنصُّ يتساويان — لا أن يُشير أحدهما للآخر."""
    ran, declared = _workflow_tests(), _declared_ci_tests()
    assert ran, "لم أقرأ أيّ ملفِّ اختبارٍ من الـworkflow ⇒ فشلٌ مُغلَق"
    assert declared, "لم أقرأ قائمةَ الـCI من السجلّ ⇒ فشلٌ مُغلَق"
    assert set(declared) == set(ran), (
        f"السجلُّ يعلن {sorted(set(declared) - set(ran))} لا يشغّلها الـCI، "
        f"ويُسقط {sorted(set(ran) - set(declared))} يشغّلها ⇒ الوثيقةُ تناقض مصدرَها")


#: **عبارةُ كمٍّ عن الـCI** لا أيُّ رقمٍ في سطرٍ فيه «الـCI» (وإلّا لأوقعنا ترقيمَ القوائم وأرقامَ الصفوف).
#: الصيغة: «الـCI … <كمّ> <اسمُ معدود>» — وهي بعينها صيغةُ الزلّة التي قاسها المقاعد («يشغّل أربعة ملفّات»).
QUANTITY = r"(?:ملفّاتٍ|ملفّات|ملفات|ملفٍّ|ملف|اختباراً|اختبارات|اختبار|ضابطاً|ضوابط|ضابط|أدوات|أداة)"
CLAIM_RE = re.compile(rf"(?:الـCI|الـworkflow|workflow)[^.،|]{{0,40}}?(\d+|{'|'.join(WORD_NUM)})\s*\S{{0,4}}\s*{QUANTITY}")


def test_no_numeric_claim_about_ci_disagrees_with_the_measurement():
    """**صنفُ ما وقع**: السجلُّ قال «الـCI يشغّل أربعة ملفّات» وهي ثمانية ⇒ كلُّ عبارةِ كمٍّ عن الـCI تُقاس."""
    measured = len(_workflow_tests())
    bad = []
    for ln in _doc().splitlines():
        for m in CLAIM_RE.finditer(ln):
            tok = m.group(1)
            n = int(tok) if tok.isdigit() else WORD_NUM[tok]
            if n != measured:
                bad.append((ln.strip()[:90], n))
    assert not bad, (f"عبارةُ كمٍّ عن الـCI تخالف المقيس ({measured} ملفّاً) ⇒ اشتقّ العددَ أو احذفْه: {bad}")


def test_every_registry_tool_has_a_test_that_names_it():
    """عمودُ «سمُّها» **مشتقٌّ لا مكتوب**: كلُّ أداةٍ في صفٍّ لها ضابطٌ يذكرها بالاسم."""
    tools = sorted(set(ROW_TOOL_RE.findall(_doc())))
    assert tools, "لم أقرأ أيَّ أداةٍ من صفوف السجلّ ⇒ فشلٌ مُغلَق (لا أُعلن تغطيةً لم أقرأها)"
    corpus = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "tests").glob("test_*.py")}
    naked = [t for t in tools if not any(t in body for body in corpus.values())]
    assert not naked, (f"أدواتٌ في السجلّ بلا ضابطٍ يذكرها: {naked} ⇒ عمودُ السمِّ بلا سند "
                       f"(كان `static_gate` مُنسوباً لضابطٍ لا يمسّه)")


def test_the_registry_declares_where_each_layer_runs():
    """**الحدُّ المُعلَن**: السجلُّ يقول صراحةً أنّ الخطّافين محلّيّان وأنّ الـCI أضيقُ مدىً."""
    doc = _doc()
    for claim in ("core.hooksPath", "محلّيّ فقط", "قائمةُ الـCI"):
        assert claim in doc, f"السجلُّ لا يُعلن حدَّه: «{claim}» غائبة ⇒ ادّعاءُ تغطيةٍ بلا إعلان"


def test_the_registry_reports_its_own_blind_spot():
    """وسجلٌّ يدّعي الكمال يُناقض غرضه: إعلانُ الحدود إلزاميّ."""
    doc = _doc()
    assert ("حدُّ ذلك مُعلَن" in doc) or ("ما لم يُثبت" in doc), "لا إعلانَ لحدود السجلّ"

# ── الاتّجاهُ الخامس (R56-4 · قاسه المدقّق في مراجعة ٥٦) ────────────────────────────────────────────
#: **ثغرةٌ كانت مفتوحة**: الاتّجاهاتُ الأربعة تمسك خطّافاً غيرَ مسجَّل، **ولا تمسك خطوةَ CI** — أضاف المدقّق
#: خطوةً مصطنعةً في نسخته فمرّت صامتةً (وأداةٌ تُنادى من الخطوة تُمسَك، أمّا خطوةٌ بأمرٍ حرٍّ فلا). ⇒ الحلُّ
#: **معرّفٌ ثابتٌ لكلّ خطوة** (`id: gate_*`) ومقابلةٌ في الاتّجاهين: لا خطوةَ بلا معرّفٍ مُسجَّل، ولا معرّفَ شبح.
STEP_START = re.compile(r"^\s*-\s+(?:name|uses):", re.M)
RUN_RE = re.compile(r"^\s*(?:-\s+)?run:", re.M)
STEP_ID_RE = re.compile(r"^\s*id:\s*(gate_[a-z0-9_]+)\s*$", re.M)
STEP_NAME_RE = re.compile(r"-\s*name:\s*(.+)")


def _steps(wf_text: str) -> list[str]:
    """كلُّ خطوةٍ كنصٍّ مستقلّ (تُقسَم عند بداية خطوة) — **الترويسةُ تُهمَل**."""
    return [p for p in re.split(r"(?m)(?=" + STEP_START.pattern + ")", wf_text)[1:]]


#: موضعُ الإعلان في §٣: قائمةُ المعرّفات **وحدها** تُقابَل (لا كلُّ نصّ الوثيقة — وإلّا لَحُسِبت أسماءُ
#: ملفّاتٍ مثل `test_gate_bites.py` معرّفاتٍ شبحاً، وهي ليست معرّفاتِ خطوات). وهذا نفسُ صنف الحدّ الذي
#: يُقاس: **حضورُ نصّ** ≠ تساوي مجموعة.
DECLARED_MARKER = "مُسجَّلٌ هنا"


def _declared_step_ids() -> list[str]:
    doc = _doc()
    assert DECLARED_MARKER in doc, "لا إعلانَ لمعرّفات خطوات الـCI في السجلّ ⇒ لا قابليةَ للتساوي"
    block = doc.split(DECLARED_MARKER, 1)[1]
    block = block.split("```", 2)[1] if "```" in block else block
    return sorted(set(re.findall(r"gate_[a-z0-9_]+", block)))


def unregistered_ci_steps(wf_text: str, declared: str) -> list[str]:
    """خطواتُ `run:` بلا معرّف — أو بمعرّفٍ ليس في المُعلَن. (دالّةٌ خالصةٌ ⇒ تُقاس بسمٍّ في الذاكرة.)"""
    out: list[str] = []
    for chunk in _steps(wf_text):
        if not RUN_RE.search(chunk):
            continue
        m = STEP_ID_RE.search(chunk)
        if m is None:
            nm = STEP_NAME_RE.search(chunk)
            out.append(f"بلا معرّف: {nm.group(1).strip() if nm else 'خطوةٌ بلا اسم'}")
        elif m.group(1) not in declared:
            out.append(f"غيرُ مسجَّلة: {m.group(1)}")
    return out


def phantom_registered_steps(wf_text: str, declared: str) -> list[str]:
    """معرّفٌ في السجلّ لا وجودَ له في الـworkflow = صفٌّ شبحٌ يُوهم حَرْساً غيرَ قائم."""
    real = set(STEP_ID_RE.findall(wf_text))
    return sorted({i for i in re.findall(r"gate_[a-z0-9_]+", declared) if i not in real})


def test_every_ci_run_step_is_registered_and_no_phantom_is_declared():
    """كلُّ خطوةِ `run:` بمعرّفٍ مُسجَّلٍ في §٣ — والسجلُّ لا يذكر معرّفاً غيرَ موجود."""
    wf, declared = WORKFLOW.read_text(encoding="utf-8"), " · ".join(_declared_step_ids())
    assert declared, "قائمةُ معرّفات الـCI فارغةٌ في السجلّ ⇒ فشلٌ مُغلَق"
    missing = unregistered_ci_steps(wf, declared)
    phantom = phantom_registered_steps(wf, declared)
    assert not missing, f"خطواتُ CI خارج السجلّ: {missing} ⇒ أضِف معرفَها واذكرْها في §٣"
    assert not phantom, f"معرّفاتٌ في السجلّ بلا خطوةٍ في الـworkflow: {phantom}"


def test_the_fifth_direction_actually_bites():
    """**سمٌّ مصنوعٌ في الذاكرة** (نفسُ ما فعله المدقّق في نسخته): خطوةٌ بلا معرّف، وخطوةٌ بمعرّفٍ غريب.

    وبلا هذا الضابط يصير الاتّجاهُ الخامس ادّعاءً: قاعدةٌ لا يُقاس مَن يخالفها ليست قاعدة.
    """
    wf = WORKFLOW.read_text(encoding="utf-8")
    declared = " · ".join(_declared_step_ids())
    stripped = wf.replace("        id: gate_static\n", "", 1)              # خطوةٌ صارت بلا معرّف
    assert unregistered_ci_steps(stripped, declared) == [
        "بلا معرّف: Static gate (names that never resolve, bindings never read)"]
    stranger = wf.replace("id: gate_static", "id: gate_static_new_thing", 1)  # معرّفٌ لم يُسجَّل
    assert unregistered_ci_steps(stranger, declared) == ["غيرُ مسجَّلة: gate_static_new_thing"]
    assert phantom_registered_steps(wf, declared + " · gate_ghost") == ["gate_ghost"]

