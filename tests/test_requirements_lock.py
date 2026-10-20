"""The lock file must cover everything the loose requirements ask for.

`requirements.txt` says what may be installed; `requirements.lock` records what
WAS installed when the measured numbers were produced (audit P2-11). Without a
check, a new dependency can be added to one and not the other and nobody
notices until a fresh install produces a different application.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _names(text: str) -> set[str]:
    out = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _NAME.match(line)
        if m:
            out.add(m.group(1).lower().replace("_", "-"))
    return out


def test_every_requirement_is_pinned_in_the_lock():
    req = _names((ROOT / "requirements.txt").read_text(encoding="utf-8"))
    lock_text = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    lock = _names(lock_text)
    assert req, "requirements.txt parsed empty"
    missing = sorted(req - lock)
    assert missing == [], f"غير مقفلة في requirements.lock: {missing}"


def test_lock_pins_exact_versions():
    lock_text = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    pinned = [l for l in lock_text.splitlines()
              if l.strip() and not l.strip().startswith("#")]
    assert pinned, "the lock file is empty"
    loose = [l for l in pinned if "==" not in l]
    assert loose == [], f"أسطر بلا تثبيت دقيق: {loose[:5]}"


# ── **إصلاحُ R131-11: القفلُ الملتزَم يجب أن يُثبَّت فعلًا** ────────────────────────────────────
#: **العِلّة المقيسة (مراجعة ١٣١):** تنقيحُ حارس المبالغ في `c7b5483` أعاد كتابةَ أربعة أرقامِ
#: إصدارٍ تشبه المبالغ (`certifi==1908.5.22` · `fsspec==1908.5.0` · `pytz==6402.2.post1` ·
#: `regex==5561.5.10`) ⇒ `uv pip sync` يرفض القفل. و`hermes-agent==0.21.3` حزمةٌ خاصّةٌ ليست على
#: PyPI ولا يستوردها التطبيق ⇒ تُثبَّت بلا مصدر. والضابطُ هنا يعضّ إن عاد الصنفان:
#: نسخةٌ لا تطابق المُثبَّت (الأربعةُ كانت تُسقطه)، أو حزمةٌ خاصّةٌ باسمها.
_PRIVATE_PACKAGES = {"hermes-agent"}


def _pins() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, ver = line.split("==", 1)
        out[name.strip().lower().replace("_", "-")] = ver.strip()
    return out


def test_no_private_package_is_pinned_in_the_lock():
    """**حزمةٌ خاصّةٌ في القفل = تثبيتٌ يفشل عند أوّل بيئةٍ جديدة** (R131-11)."""
    private = sorted(set(_pins()) & _PRIVATE_PACKAGES)
    assert private == [], f"حزمةٌ خاصّةٌ في القفل: {private} — احذفها (ليست على PyPI)"


def test_every_locked_version_is_a_real_pep440_version():
    """والنسخةُ تُقرأ نسخةً: `1908.5.22` تُقرأ، لكنّها **ليست نسخةَ الحزمة المثبَّتة** ⇒ الضابطُ
    الثاني (المقابلةُ بالمُثبَّت) هو الذي يعضّ عليها. وهذا يقيس الشكلَ وحدَه (حدٌّ مُعلَن)."""
    from packaging.version import InvalidVersion, Version

    for name, ver in _pins().items():
        try:
            Version(ver)
        except InvalidVersion:
            raise AssertionError(f"{name}=={ver} ليست نسخةً صالحةً لـPEP 440") from None
