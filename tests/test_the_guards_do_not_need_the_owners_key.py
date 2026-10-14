"""**R118-3 — الضوابطُ لا تسحب مفتاحَ المالك، والملفّاتُ الجديدةُ في قائمة الـCI.**

**العطبُ المقيس (مراجعة ١١٨ · P2 · بلا كلفة):** سبعةُ ضوابط (أربعةٌ في
`test_the_price_limit_reaches_the_request` · وثلاثةُ حالاتٍ في `test_the_refusal_is_read_from_its_type`)
كانت تبني `build_llm()` **بلا `api_key`** ⇒ فيقرأ `get_api_key()` مفتاحَ المالك من `~/.hermes/.env`
⇒ فتمرّ عنده وحدَه، **وتسقط في بيتٍ نظيف**، **وتُسلّم مفتاحَ المالك الحقيقيّ للكود المختبَر**
(النقلُ المُقلَّد يحجبه اليوم، وأيُّ خطأٍ في التقليد يُرسله). **والملفّاتُ الستّةُ الجديدة كانت خارج
قائمة الـCI** ⇒ فالـ«أخضر» لم يُشغّلها، و«١٢١٦ · ٠ فاشلة» صحيحٌ على جهاز المالك وحدَه.

**والقبولُ بنصّه:** بيتٌ مزيّفٌ بلا مفتاح ⇒ **صفرُ سقوط** من الملفّات الستّة، **ومسحٌ لا يجد
`build_llm()` بلا `api_key` في `tests/`**.

**وهذا الملفّ لا يُشغِّل نفسَه:** قائمتُه الستّةُ لا تشمله (وإلّا دار بلا نهاية).
"""
from __future__ import annotations

import ast
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
WORKFLOW = ROOT / ".github" / "workflows" / "publish-guard.yml"

#: الملفّاتُ الستّةُ التي وُلدت في جولتَي ١١٧ و١١٨ — وهي التي يجب أن تمرّ في بيتٍ نظيف.
SIX = (
    "tests/test_the_price_limit_reaches_the_request.py",
    "tests/test_the_refusal_is_read_from_its_type.py",
    "tests/test_the_scope_gate_speaks_only_what_it_read.py",
    "tests/test_the_tools_refuse_unknown_inputs.py",
    "tests/test_the_compound_split_is_measured_not_assumed.py",
    "tests/test_the_estimate_reads_the_newest_run.py",
)


# ── ① مسحٌ بنيويّ: لا `build_llm()` بلا مفتاحٍ في `tests/` ────────────────────────────────
def test_no_test_builds_a_client_without_a_key():
    offenders: list[str] = []
    for path in sorted(TESTS.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                                # ملفٌّ يكسر التجميع يمسكه حارسٌ آخر
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if name != "build_llm":
                continue
            if not any(kw.arg == "api_key" for kw in node.keywords):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, (
        "بناءُ عميلٍ بلا `api_key` في اختبار ⇒ يقرأ مفتاح المالك، ويسقط في بيتٍ نظيف: "
        f"{offenders}")


# ── ② القبولُ السلوكيّ: بيتٌ مزيّفٌ بلا مفتاح ⇒ صفرُ سقوط ───────────────────────────────────
def _pytest_interpreter() -> str | None:
    """أوّلُ مفسّرٍ يستطيع `import pytest` — **والحدُّ مُعلَن:** في بعض المهامّ `sys.executable`
    ليس هو مفسّرَ الخطوة (قِيس في الـCI: `/usr/bin/python3` بلا `pytest` ⇒ سقوطٌ كاذب يقرأ
    «الضوابطُ تعتمد مفتاحَ المالك» وهو عطبُ أداةٍ لا عطبُ ضابط).
    """
    import shutil

    for exe in (sys.executable, shutil.which("python3") or "", shutil.which("python") or ""):
        if not exe:
            continue
        try:
            ok = subprocess.run([exe, "-c", "import pytest"], capture_output=True, timeout=180)
        except OSError:
            continue
        if ok.returncode == 0:
            return exe
    return None


def test_the_six_files_pass_in_a_home_without_a_key(tmp_path):
    """يُشغَّل الملفّاتُ الستّة في عمليّةٍ فرعيّة بـ`HOME` مزيّفٍ ومفتاحٍ منزوعٍ من البيئة.

    **وحدُّ هذا الفحص مُعلَن:** يقيس ملفّات الجولة الستّة، لا `tests/` كلَّها (وهو ما يقرؤه
    العدّاد). والباقي محروسٌ بالمسح البنيويّ أعلاه. **وإن لم تكن البيئةُ قادرةً على تشغيل
    `pytest` في عمليّةٍ فرعيّة يُتخطّى بتسميةٍ صريحة** — ولا يُقرأ التخطّي نجاحًا.
    """
    if os.environ.get("RAJHI_NO_SUBPROCESS_GUARD"):         # مهربٌ مُعلَن لبيئةٍ لا تُشغّل عمليّات
        pytest.skip("مُعطَّلٌ بمتغيّر بيئةٍ صريح")
    exe = _pytest_interpreter()
    if exe is None:
        pytest.skip("لا مفسّرَ في هذه البيئة يشغّل `pytest` في عمليّةٍ فرعيّة ⇒ يُقاس عند المالك")
    env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
    env["HOME"] = str(tmp_path)                            # بيتٌ بلا `~/.hermes/.env`
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([exe, "-m", "pytest", *SIX, "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
    out, tail = (proc.stdout or ""), (proc.stdout or "")[-1200:]
    if "passed" not in out and "failed" not in out:         # شغّل شيئًا آخر: لا يُقرأ حكمًا
        pytest.skip(f"العمليّةُ الفرعيّةُ لم تُشغّل pytest فعلًا: {(proc.stderr or '')[-200:]}")
    assert proc.returncode == 0, (
        f"سقطت ضوابطُ الجولة في بيتٍ نظيف (rc={proc.returncode}) — أي أنّها تمرّ بمفتاح المالك "
        f"وحدَه:\n{tail}")


# ── ③ الملفّاتُ الستّةُ في قائمة الـCI (فالعدّادُ والتشغيلُ من مصدرٍ واحد) ─────────────────
#: **وكلُّ ملفّات جولتَي ١١٧ و١١٨** — تُقاس قائمةُ الـCI عليها (وهذا الملفُّ نفسُه فيها،
#: ولذلك هو **ليس** في `SIX`: تشغيلُه على نفسه في عمليّةٍ فرعيّة يدور بلا نهاية).
ROUND_FILES = SIX + (
    "tests/test_the_guards_do_not_need_the_owners_key.py",
    "tests/test_the_scorer_reads_the_answer_kind.py",
)


def test_every_round_file_is_in_the_ci_list():
    assert WORKFLOW.exists(), "لا ملفَّ CI — والقائمةُ تُقرأ منه"
    text = WORKFLOW.read_text(encoding="utf-8")
    missing = [name for name in ROUND_FILES if name not in text]
    assert not missing, (
        f"ملفّاتٌ تُعدّ ولا تُشغَّل في الـCI ({missing}) — أضِفها إلى قائمة خطوة الاختبارات "
        "أو اكتب سببَ غيابها")
    # **ولماذا `ROUND_FILES` لا `SIX`:** الأخيرةُ تُشغَّل في بيتٍ مزيّف (وهذا الملفُّ خارجَها
    # لأنّه يشغّل نفسه)، والأولى تحرس القائمةَ كلَّها — فملفٌّ جديدٌ لا ينجو من الحارس بلا قرارٍ مكتوب.
