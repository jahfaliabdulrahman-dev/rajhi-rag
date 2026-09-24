"""**مشغّلُ سمّ البوّابات: تمييزُ «سقط» عن «تعذّر التشغيل»** — ضابطٌ على التصنيف نفسه.

العطبُ (مراجعة ٥٣، قِيس من المدقّق): كان المشغّل يُعدّ **أيَّ رمزٍ غيرِ صفر** «بوّابةً عَضّت»؛ ومسارُ
المفسّر كان `.venv/bin/python` مكتوباً ⇒ في أيّ نسخةٍ أخرى تسقط الأداةُ بمخرج **1** وتشهد لبوّاباتٍ لم
تُقَس، أو يعود `python3 -m pytest` بـ«No module named pytest» بمخرج **1** أيضاً. ⇒ التصنيفُ هنا من
**علامة pytest الصريحة** (`FAILED` / `N failed`)، وما عداها «تعذّر تشغيل» يُحسب عطباً لا شهادة.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("bite_sweep", ROOT / "tools" / "guard_bite_sweep.py")
    assert spec is not None and spec.loader is not None, "تعذّر تحميلُ المشغّل ⇒ لا قياس"
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_a_real_failure_is_a_bite():
    m = _load()
    out = "F\n=================================== FAILURES ===================================\n1 failed, 2 passed in 0.12s\n"
    assert m._verdict(1, out) == "bite"


def test_a_green_run_is_not_a_bite():
    m = _load()
    assert m._verdict(0, "3 passed in 0.05s\n") == "no_bite"


def test_an_environment_failure_is_not_a_bite():
    """**القلبُ**: عطبُ بيئةٍ يخرج 1، لكنّه ليس شهادةً لأنّ البوّابةَ لم تُقَس."""
    m = _load()
    assert m._verdict(1, "/usr/bin/python3: No module named pytest\n") == "unrunnable"
    assert m._verdict(2, "ERROR: file or directory not found: tests/x.py\n") == "unrunnable"
    assert m._verdict(127, "sh: python: command not found\n") == "unrunnable"


def test_the_interpreter_is_resolved_not_hardcoded():
    """**الجذر**: المسارُ لم يكن يُحلّ ⇒ الأداةُ تصلح في نسخةٍ واحدة (وكان المدقّق ينشئ رابطاً ليقيس)."""
    m = _load()
    assert m.PY, "لا مفسّر"
    assert Path(m.PY).exists(), f"المفسّرُ المحلولُ غيرُ موجود: {m.PY}"
    src = (ROOT / "tools" / "guard_bite_sweep.py").read_text(encoding="utf-8")
    assert 'PY = str(ROOT / ".venv/bin/python")' not in src, "المسارُ ما زال مكتوباً ⇒ يسقط خارج هذه النسخة"
