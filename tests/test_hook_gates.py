"""**بوّابات الانكشاف: توجد · وقابلةٌ للتنفيذ · وتَعَضّ فعلًا** (قاعدة ٧ — سمٌّ لكلّ بوابة).

الحادثةُ التي وُلدت منها: سِرٌّ + أرقامٌ حقيقيّة دخلت **التزامًا**، فنُقّي التاريخُ **ثلاث مرّات**،
ثم قِيس أنّ الكائناتَ لا تزال مرئيّةً عبر `refs/pull/*` (**١١٣** مرجعاً · **٦٥٤** التزاماً · **١٢٣**
شكلاً من مبالغَ حقيقيّة) — وهي **غيرُ قابلةٍ للفكّ من جهة العميل**. ⇒ المنعُ **قبل وجود الكائن**.

وهذه الضوابطُ تقيس **البوّابةَ نفسَها** (لا المنتَج): لو حُذف الخطّاف أو فُقد إذنُ التنفيذ أو
أُفرِغ نصُّه، تسقط هنا — قبل أن تُصدَّق دعوى الحماية.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".githooks"
PRE_COMMIT = HOOKS / "pre-commit"
PRE_PUSH = HOOKS / "pre-push"


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def test_both_hooks_exist_and_are_executable():
    """**بوّابةٌ بلا خطّافٍ مُنفَّذٍ = دعوى حمايةٍ كاذبة** (والخطّافاتُ تُقرأ من `.githooks` بـ`core.hooksPath`)."""
    assert HOOKS.is_dir(), "مجلّدُ الخطّافات مفقود"
    for h in (PRE_COMMIT, PRE_PUSH):
        assert h.is_file(), f"خطّافٌ مفقود: {h.name}"
        assert os.access(h, os.X_OK), f"خطّافٌ غيرُ قابلٍ للتنفيذ: {h.name} (chmod +x)"
    # **والإعدادُ المحلّيّ لا ينتقل مع الاستنساخ** (أمسكه المدقّق في مراجعة ٥٣: نسخةٌ نقيّة ⇒ ضابطٌ يسقط).
    # فالمقصودُ هنا: ألّا يُشير إلى مكانٍ آخر؛ وكونُه غيرَ مضبوطٍ **حالٌ معلومة**: الخطّافاتُ لا تحرس تلك
    # النسخة، وCI وحدَه يعمل عند الجميع (وهذا مكتوبٌ في `docs/QA_CHECKLIST.md` و`docs/OPERATIONS.md`).
    cfg = _git("config", "core.hooksPath", cwd=ROOT).stdout.strip()
    assert cfg in (".githooks", str(HOOKS), ""), \
        f"`core.hooksPath` يشير إلى مكانٍ غير متوقَّع ⇒ الخطّافاتُ لا تُشغَّل (القيمة: {cfg!r})"


def test_each_hook_documents_its_own_install_line():
    """**بوّابةٌ لا تُركَّب لا تحرس**: كلُّ ملفّ خطّافٍ يحمل سطرَ التركيب بنفسه (فيُقرأ من مكانه)."""
    line = "git config core.hooksPath .githooks"
    for h in (PRE_COMMIT, PRE_PUSH):
        assert line in h.read_text(encoding="utf-8"), f"{h.name} لا يوثّق سطرَ التركيب ⇒ يُنسى في نسخةٍ نقيّة"


def test_the_pre_commit_gate_bites_on_a_staged_evidence_file(tmp_path):
    """**السمُّ**: ملفُّ أدلّة/سرٍّ في الفهرس ⇒ الخطّافُ يرفض (rc=1) ويسمّي الصنف.

    (وهو الصنفُ الذي كلّف ثلاثَ تنقيات: `data/.amount-guard-key` والقائمةُ المنشورة.)
    """
    repo = tmp_path / "r"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("config", "user.email", "t@t", cwd=repo)
    _git("config", "user.name", "t", cwd=repo)
    (repo / "data").mkdir()
    (repo / "data" / ".amount-guard-key").write_text("x\n", encoding="utf-8")
    _git("add", "-f", "data/.amount-guard-key", cwd=repo)

    r = subprocess.run([str(PRE_COMMIT)], cwd=str(repo), capture_output=True, text=True)
    assert r.returncode == 1, f"الخطّافُ مرّر ملفَّ أدلّةٍ مُدرَجًا (rc={r.returncode})"
    assert "أدلّة" in r.stdout and "amount-guard-key" in r.stdout


def test_the_pre_commit_gate_passes_an_empty_index(tmp_path):
    """**الضابطُ الموجب**: فهرسٌ فارغٌ ⇒ لا يُعطّل التزامًا (وإلا صار حافزَ `--no-verify`)."""
    repo = tmp_path / "r2"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    r = subprocess.run([str(PRE_COMMIT)], cwd=str(repo), capture_output=True, text=True)
    assert r.returncode == 0, f"الخطّافُ عطّل فهرسًا فارغًا (rc={r.returncode}): {r.stdout[:200]}"


def test_the_pre_commit_gate_fails_closed_when_the_scanner_is_absent(tmp_path):
    """**وضعُه عند الغياب مُعلَن: يفشل مُغلَقًا** — نسخةٌ بلا `tools/amount_guard.py` لا تمرّ بصمت.

    (وهو الفرقُ المقصود عن `pre-push`: الغائبُ هناك **أداةُ تطوير** (`pyflakes`) فلا تُسقِط شيئًا،
    وهنا **ماسحُ أمن**؛ وتمريرُ ما لم يُمسح هو بعينه الفشلُ المفتوح الذي أُمسك في حيّاز الانكشاف.)
    """
    repo = tmp_path / "r3"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("config", "user.email", "t@t", cwd=repo)
    _git("config", "user.name", "t", cwd=repo)
    (repo / "a.txt").write_text("نصٌّ بريء\n", encoding="utf-8")
    _git("add", "a.txt", cwd=repo)
    r = subprocess.run([str(PRE_COMMIT)], cwd=str(repo), capture_output=True, text=True)
    assert r.returncode != 0, "خطّافُ أمنٍ مرّر ملفًّا بلا أن يمسحه ⇒ فشلٌ مفتوح"
