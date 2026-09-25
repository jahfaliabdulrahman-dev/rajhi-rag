"""**P-9 — «الشاهدُ يُدفَع قبل أن يُجاب»** (البروتوكول §٢٧ · تبنّاه المدقّق في مراجعة ٥٦).

**العلّةُ المقيسة:** مراجعاتُ ٤٩–٥٥ سكنت قرصَ صاحبها حتى دُفعت بكلمة المالك ⇒ التزاماتُ الطرف الآخر كانت
تُجيب حُكماً **لا يقدر أحدٌ على قراءته من المستودع**. وأخطرُ منه: قبولُ حُكمٍ لا يُعاد إنتاجه.

**وحدُّ هذا الحارس مُعلَن:** يقيس ما **وصل** (ملفٌّ محلّيّ) وليس ما **كُتب** (لا يعلم بشيءٍ لم يُنسَخ هنا
أصلًا) — أي أنّه يمسك «كُتب هنا ولم يُدفع»، لا «كُتب عند غيري ولم يصل». والقرارُ في الثانية للمالك
(`AWAITING_FOUNDER` · §٣). **والفشلُ مُغلَق** عند غياب المرجع، والتخطّي **مُعلَنٌ بسببٍ** لا صامت.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOX = "handoff/claude"
REF = "origin/main"


def landed_files() -> set[str] | None:
    """ما هو موجودٌ فعلاً في `REF` تحت صندوق المدقّق — أو `None` إن تعذّر القياس (يُتخطّى بسببٍ مُعلَن)."""
    r = subprocess.run(["git", "rev-parse", "--verify", REF], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        return None
    ls = subprocess.run(["git", "ls-tree", "-r", "--name-only", REF, BOX],
                        cwd=str(ROOT), capture_output=True, text=True)
    if ls.returncode != 0:
        return None
    return set(ls.stdout.split())


def unlanded(local: set[str], landed: set[str]) -> list[str]:
    """ملفٌّ في الصندوق لم يُدفَع = شاهدٌ لا يُعاد إنتاجُه. (دالّةٌ خالصةٌ ⇒ تُقاس بسمٍّ في الذاكرة.)"""
    return sorted(local - landed)


def test_every_file_in_the_audit_box_is_reachable_from_origin_main():
    """كلُّ ملفٍّ في `handoff/claude/` (ما عدا `STATE.md`) يجب أن يكون في `origin/main`."""
    landed = landed_files()
    if landed is None:
        import pytest
        pytest.skip(f"تعذّر الوصولُ إلى `{REF}` في هذه النسخة ⇒ لا قياس (تخطٍّ مُعلَن، لا نظافة)")
    local = {str(p.relative_to(ROOT)) for p in (ROOT / BOX).rglob("*")
             if p.is_file() and p.name != "STATE.md"}
    missing = unlanded(local, landed)
    assert not missing, (f"ملفّاتٌ في صندوق المدقّق غيرُ مدفوعةٍ إلى `{REF}` (§٢٧): {missing} ⇒ "
                         f"ادفعها بالمسار (فرعٌ → بوّابةٌ خضراء → `HEAD:main` → حذفُ الفرع) قبل أن يُجاب حكمُها. "
                         f"**وإن كانت مدفوعةً فعلًا فتحقّق أنّ `{REF}` هو الالتزامُ المقصود** لا مرجعاً "
                         f"متقادماً (نسخةٌ من المسار المحلّيّ ترث `refs/heads/main` — انظر §٢٧ الخطوةَ الخامسة)")


def test_the_landing_guard_actually_bites():
    """قاعدةٌ لا يُقاس مَن يخالفها ليست قاعدة: ملفٌّ محلّيٌّ غيرُ مدفوعٍ **يُكشَف** باسمه."""
    assert unlanded({f"{BOX}/a.md", f"{BOX}/b.md"}, {f"{BOX}/a.md"}) == [f"{BOX}/b.md"]
    assert unlanded({f"{BOX}/a.md"}, {f"{BOX}/a.md", f"{BOX}/زائد.md"}) == []
