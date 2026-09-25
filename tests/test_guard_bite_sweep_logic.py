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


def test_a_skipped_control_is_not_a_bite_and_not_a_false_claim():
    """**R57-5 (قاسه المدقّق في مراجعة ٥٧)**: ضابطٌ يُتخطّى لغياب `data/local_sample` يخرج `rc=0` ⇒ كان
    يُصنَّف «لم تسقط» وتُطبع له **«✗ البوّابةُ تمرّ — دعوى كاذبة»**، وهي **دعوى كاذبةٌ من الأداة نفسها**:
    التخطّي ليس مروراً بل **غيابَ قياس**. والحالةُ الرابعةُ تُصنَّف من المخرَج لا من رمز الخروج.
    """
    m = _load()
    assert m._verdict(0, "s\n1 skipped in 0.31s\n") == "skipped"
    assert m._verdict(0, "SKIPPED [1] tests/x.py:12: لا data/local_sample\n1 skipped in 0.20s\n") == "skipped"
    # والنصُّ نفسُه مقيسٌ لا موعود: «لم يُقَس» لا تُخلط بـ«دعوى كاذبة»، والعكسُ محفوظ.
    assert "لم يُقَس" in m._verdict_label("skipped")
    assert "دعوى كاذبة" not in m._verdict_label("skipped")
    assert "دعوى كاذبة" in m._verdict_label("no_bite")
    # ولا تُبتلع الحالاتُ القديمة: السقوطُ يبقى سقوطاً ولو ظهرت كلمةُ skip في مخرَجٍ مختلط.
    assert m._verdict(1, "1 failed, 1 skipped in 0.4s\n") == "bite"


def test_the_summary_reports_the_environment_beside_the_count():
    """**رقمٌ بلا بيئته ليس رقماً** (R57-5): الأداةُ تطبع البيئةَ (المفسّرُ ووجودُ الأدلّة) مع الحصيلة،
    وإلا قُرئ «١٣/١٤» فشلاً وهو تخطٍّ. والحدُّ المُعلَن: وجودُ `data/local_sample` هو ما يفصل الحالتين."""
    m = _load()
    env = m._environment()
    assert "المفسّر" in env and "data/local_sample" in env, env
    src = (ROOT / "tools" / "guard_bite_sweep.py").read_text(encoding="utf-8")
    assert "لم يُقَس" in src, "شهادةُ التخطّي غابت من مخرَج الأداة ⇒ تعود الدعوى الكاذبة"


def test_the_interpreter_is_resolved_not_hardcoded():
    """**الجذر**: المسارُ لم يكن يُحلّ ⇒ الأداةُ تصلح في نسخةٍ واحدة (وكان المدقّق ينشئ رابطاً ليقيس)."""
    m = _load()
    assert m.PY, "لا مفسّر"
    assert Path(m.PY).exists(), f"المفسّرُ المحلولُ غيرُ موجود: {m.PY}"
    src = (ROOT / "tools" / "guard_bite_sweep.py").read_text(encoding="utf-8")
    assert 'PY = str(ROOT / ".venv/bin/python")' not in src, "المسارُ ما زال مكتوباً ⇒ يسقط خارج هذه النسخة"
