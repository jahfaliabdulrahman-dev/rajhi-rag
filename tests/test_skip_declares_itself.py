"""**التخطّي يُعلن نفسَه — ويُقاس بسلوكٍ لا بوجود نصّ.**

سببُ هذا الملف، وسببُ إعادة كتابته:

1. RCA مُقاس (2026-09-21): ثلاثةُ اختباراتٍ تُخطّى في **worktree** لأن `git worktree`
   لا يحمل المُتجاهَل (`data/local_sample/*`)، وأنّ **تغطيةَ المراجعة دالّةٌ على البيئة
   لا على العدد**.
2. ⚠️ **ومأخذُ المدقّق (الجولة ٢١) على النسخة الأولى:** كانت `assert reason in text`
   ⇒ يكفي أن يكون السببُ **في تعليق** ليمرّ — وهو بعينه العطبُ الذي يقول نصُّ الملف
   إنه يمنعه («تخطيطٌ بلا سببٍ مكتوب = فحصٌ ميت يُقرأ نجاحاً»). ومرّر المدقّق على
   اختباري الأول بأن عطّل جسم السكربت وأبقى رأسه ⇒ `2 passed`.
   **فالحكمُ صار سلوكيّاً:** نُنشئ worktree حقيقيّاً، ونشغّل pytest فيه، ونقرأ سطورَ
   `SKIPPED` من مخرجه — ثم نشغّل السكربت ونتحقّق أن التخطّي **زال**.
   **والدرسُ أوسع من الحالة:** عُلق المثالُ في الحارس ثم في اختباراته — فالطبقةُ
   تُقاس بالأثر لا يُلتمس لها نصّ.

الكلفة: worktree مؤقّت + pytest على ملفّين ⇒ ثوانٍ، بلا شبكة وبلا كلفة.
"""
from __future__ import annotations

from tests._local_evidence import require_local_evidence

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATED = ("tests/test_page_gate.py", "tests/test_text_reader.py")
# نُشغّل **نسخةَ العمل** لا نسخةَ الالتزام: وإلا اختُبر إصدارٌ قديم
# (مأخذ المدقّق · ٢٢: سمُّه في نسخة العمل مرّ، وفي المُلتزمة سقط — فالفرقُ تأخّرٌ لا عمى).
WORKING_COPY = ("tools/link_local_data.sh",) + GATED


def _main_repo() -> Path:
    """المستودعُ الأصلي — من المستودع المشترك، فيعمل من أي worktree."""
    common = Path(_git("rev-parse", "--git-common-dir").strip())
    if not common.is_absolute():
        common = ROOT / common
    return common.resolve().parent


def _python() -> str:
    """المفسّرُ الذي يشغّل هذه الحزمة — **لا** مسارَ venv في المستودع الأصلي.

    ⚠️ مأخذ المدقّق (٢٢): كان `VENV_PY = ROOT/.venv` ⇒ في worktree لا venv
    ⇒ الحارسان **يُخطَّيان في البيئة التي كُتبا للتحقّق منها**. و`sys.executable`
    موجودٌ حيث تُشغَّل الحزمة، دائماً.
    """
    if not sys.executable:
        pytest.skip("لا مفسّرَ متاحاً لتنفيذ الفحص السلوكيّ")
    return sys.executable

# ما يجب أن يذكره سببُ التخطّي (ويجوز أن يزيد عليه)
MUST_MENTION = ("المسحة الحقيقية", "الكشف الرقمي")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout


@pytest.fixture()
def fresh_worktree(tmp_path):
    """worktree نظيفٌ من نفس الالتزام — بلا المُتجاهَل، أي بيئةَ المدقّق بعينها."""
    wt = tmp_path / "auditor-worktree"
    _git("worktree", "add", "--detach", str(wt), "HEAD")
    # نسخةُ العمل تُنقل إلى الـworktree: الحارسُ يقيس ما ستلتزمه لا ما التزمتَه
    for rel in WORKING_COPY:
        shutil.copyfile(ROOT / rel, wt / rel)
    try:
        yield wt
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)],
                       cwd=ROOT, capture_output=True)
        subprocess.run(["git", "worktree", "prune"], cwd=ROOT, capture_output=True)


def _pytest_in(wt: Path) -> tuple[str, list[str]]:
    """يُشغّل الملفّات المحروسة داخل الـworktree ويعيد مخرجه وسطورَ التخطّي."""
    out = subprocess.run([_python(), "-m", "pytest", "-q", "-rs",
                          "-p", "no:cacheprovider", *GATED],
                         cwd=wt, capture_output=True, text=True)
    text = out.stdout + out.stderr
    skipped = [ln for ln in text.splitlines() if ln.strip().startswith("SKIPPED")]
    return text, skipped


def test_a_fresh_worktree_declares_what_is_missing(fresh_worktree):
    """**سلوكٌ لا وجودُ نصّ:** في worktree نظيف تُخطّى الفحوصُ، وكلُّ تخطيطٍ يذكر ما فُقد."""
    wt = fresh_worktree
    assert not (wt / "data" / "local_sample" / "slice_629p").exists(), \
        "الـworktree يجب ألا يحمل المُتجاهَل — وإلا فالفحص لا يقيس شيئاً"
    text, skipped = _pytest_in(wt)
    assert skipped, f"لم يُخطَّ شيءٌ في الـworktree — هل صارت البيانات مُلتزمة؟\n{text[-800:]}"
    assert len(skipped) >= 3, f"الفحوصُ المحروسة ثلاثة على الأقل: {skipped}"
    for line in skipped:
        reason = line.split(":", 1)[1].strip() if ":" in line else ""
        assert len(reason) > 10, f"تخطيطٌ بلا سببٍ مقروء: {line}"
    joined = " ".join(skipped)
    for needle in MUST_MENTION:
        assert needle in joined, f"سببُ التخطّي لا يذكر «{needle}»: {skipped}"


def test_the_script_links_from_inside_a_worktree_and_removes_the_skips(fresh_worktree):
    """**الحالة الوحيدة التي وُجد السكربت لها:** يُشغَّل من **داخل** الـworktree.

    وفيها كان يخرج بـ1 قائلاً «لا مسحة محلية في المستودع الأصلي» — وهو **كذبٌ**
    يُقنع المدقّق أن البيانات غير موجودة فيمضي بتغطيةٍ ناقصة. فالمسارُ يُشتقّ من
    `git rev-parse --git-common-dir`.
    """
    require_local_evidence()
    wt = fresh_worktree
    script = wt / "tools" / "link_local_data.sh"
    assert script.exists(), "السكربت غير موجود في الالتزام"
    # نُشغّل **نسخةَ العمل** لا نسخةَ الالتزام: وإلا لَاختُبر إصدارٌ قديم
    # (وقد وقع: النسخةُ الملتزمة كانت المعطوبة، فسقط هذا الفحص — وهو الصواب).
    import shutil
    shutil.copyfile(ROOT / "tools" / "link_local_data.sh", script)
    run = subprocess.run(["bash", str(script), str(wt)], cwd=wt,
                         capture_output=True, text=True)
    assert run.returncode == 0, f"السكربت فشل من داخل worktree: {run.stdout}{run.stderr}"
    link = wt / "data" / "local_sample" / "slice_629p"
    assert link.exists(), "لم يُنشأ الرابط"
    assert link.is_symlink(), "الوصلُ يجب أن يكون رابطاً (لا نسخةً من بيانات العملاء)"
    # المقابلةُ مع بيانات **المستودع الأصلي** لا شجرة التشغيل: وإلا لطلب الفحصُ
    # أن يكون الوصلُ مُنفَّذاً سلفاً (مأخذ المدقّق · ٢٢).
    assert link.resolve() == (_main_repo() / "data" / "local_sample" / "slice_629p").resolve(), \
        "الرابط لا يشير إلى بيانات المستودع الأصلي"

    text, skipped = _pytest_in(wt)
    assert not skipped, f"التخطّي لم يزل بعد الوصل: {skipped}\n{text[-800:]}"
    assert re.search(r"\d+ passed", text), f"لا نجاحَ بعد الوصل:\n{text[-800:]}"
    print(f"[skip-declares-itself] python {sys.version_info.major}."
          f"{sys.version_info.minor} · {text.strip().splitlines()[-1]}")
