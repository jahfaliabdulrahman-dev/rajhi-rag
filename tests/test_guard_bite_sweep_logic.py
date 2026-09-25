"""**مشغّلُ سمّ البوّابات: تمييزُ «سقط» عن «تعذّر التشغيل»** — ضابطٌ على التصنيف نفسه.

العطبُ (مراجعة ٥٣، قِيس من المدقّق): كان المشغّل يُعدّ **أيَّ رمزٍ غيرِ صفر** «بوّابةً عَضّت»؛ ومسارُ
المفسّر كان `.venv/bin/python` مكتوباً ⇒ في أيّ نسخةٍ أخرى تسقط الأداةُ بمخرج **1** وتشهد لبوّاباتٍ لم
تُقَس، أو يعود `python3 -m pytest` بـ«No module named pytest» بمخرج **1** أيضاً. ⇒ **ورمزُ الخروج يُحكم
أوّلًا** (ST-2 · مقعدُ البنية: مخرَجُ عطبِ **الجمع** `rc=2` يحمل «1 error in 0.04s» فكان يُقرأ «عَضّاً»)،
ثمّ تُقرأ **علامةُ pytest الصريحة** (`FAILED` / `N failed`) في رمز 1 وحدَه، وما عدا ذلك «تعذّر تشغيل» أو
«لم يُقَس» — يُحصى عطباً لا شهادة. **والحصيلةُ تُقاس بدالّتين خالصتين** (`_summary` · `_exit_code`؛ S-1/ST-1).
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
    التخطّي ليس مروراً بل **غيابَ قياس**. والحالةُ الرابعةُ تُقرأ من مخرَج pytest **في رمز الخروج 0**
    (ورمزُ الخروج يُحكم أوّلًا — ST-2).
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


def test_a_collection_error_is_not_a_bite():
    """**ST-2 (مقعد البنية)**: عطبُ الجمع يخرج `rc=2` ومخرَجُه يحمل «1 error in 0.04s» ⇒ كان يُصنَّف
    **«عَضّ»**، أي شهادةً لبوّابةٍ **لم تُجمَع** أصلًا (أخطرُ الأصناف في المستودع). والرمزُ يُحكم قبل النصّ،
    ورمزُ 1 بلا فشلٍ **مُسمّى** ليس شهادةً أيضاً.
    """
    m = _load()
    out = "ERROR tests/x.py\n!!!! Interrupted: 1 error during collection !!!!\n1 error in 0.04s\n"
    assert m._verdict(2, out) == "unrunnable", "عطبُ الجمع صار «عَضّاً» ⇒ شهادةٌ بلا قياس"
    assert "تَعَضّ" not in m._verdict_label(m._verdict(2, out))
    assert m._verdict(1, "") == "unrunnable", "«عَضّ» بلا فشلٍ مُسمّى"
    assert m._verdict(1, "1 error in 0.04s\n") == "bite", "فشلٌ مُسمّى برمز 1 يبقى عَضّاً"


def test_the_summary_counts_each_state_in_its_own_slot():
    """**S-1/ST-1 (مقعدان قاساه، وأكّدتُه في نسخةٍ نقيّة):** كان التخطّي يُطرح **مرّتين** — `bad` يزيده
    ثمّ `total - bad - len(unmeasured)` تخصمه ⇒ العددُ المطبوع (١٢) أقلُّ من صفوفِ «تعضّ» في المخرَج نفسِه
    (١٣)؛ و«⛔ دعاوى بلا حماية!» تُطبع على **تخطٍّ** لا يدّعي شيئاً. والدالّتان خالصتان الآن ⇒ تُقاسان في
    الذاكرة: العددُ من خانة العَضّ وحدَها، والتحذيرُ على الدعاوى، وتخطٍّ في **بيئةٍ مُهيّأة** عطبٌ (وإلّا
    صار فقدانُ البيانات باباً يُخضِرّ المسح).
    """
    m = _load()
    clean = {"bite": 13, "no_bite": 0, "skipped": 1, "unrunnable": 0}
    line = m._summary(clean, 14, equipped=False)
    assert "13/14" in line, f"العددُ لا يطابق صفوفَ العَضّ: {line}"
    assert "1 لم يُقَس" in line
    assert "دعاوى بلا حماية" not in line, f"إنذارٌ كاذبٌ على تخطٍّ لا يدّعي: {line}"
    assert m._exit_code(clean, equipped=False) == 0, "تخطٍّ في بيئةٍ ناقصةٍ ليس فشلاً"
    assert m._exit_code(clean, equipped=True) == 1, "تخطٍّ في بيئةٍ مُهيّأة ليس عذراً"
    assert "عطبُ قياس" in m._summary(clean, 14, equipped=True)

    claim = {"bite": 12, "no_bite": 2, "skipped": 0, "unrunnable": 0}
    assert "دعاوى بلا حماية!" in m._summary(claim, 14, equipped=False)
    assert m._exit_code(claim, equipped=False) == 1

    dead = {"bite": 14, "no_bite": 0, "skipped": 0, "unrunnable": 1}
    assert m._exit_code(dead, equipped=False) == 1, "تعذّرُ التشغيل مرورٌ مقنّع"
    assert "تعذّر تشغيل" in m._summary(dead, 15, equipped=False)


def test_every_named_expectation_points_at_a_real_case():
    """**الاسمُ المتوقَّع لا يُصبح ميتًا بصمت** (مقعدُ البنية · مراجعة ٦١).

    كان `MUST_NAME` خريطةً **مستقلّةً** عن `CASES` تُقابَل بالاسم نصًّا: فإعادةُ تسمية حالةٍ في `CASES`
    (أو تصحيحُ حرفٍ في مفتاح) تُبقي المدخلةَ حيّةً في القاموس **وميتةً في القياس** ⇒ يتحوّل «عضّةٌ
    مُسمّاة» إلى «عضّةٍ عابرةٍ» بلا ضابطٍ يُنبّه. وهذا الضابطُ يجعل إعادةَ التسمية **حمراء**.

    وحدُّه المُعلَن: يمنع المدخلةَ الميتة، **ولا** يكشف حالةً جديدةً كان ينبغي أن تُسمّى فلم تُسمَّ
    (لا سبيلَ للآلة أن تعرف نيّةَ الكاتب) — يُراجَع في المقعد.
    """
    m = _load()
    names = [c[0] for c in m.CASES]
    assert len(names) == len(set(names)), f"اسمُ حالةٍ مكرّر ⇒ قياسٌ يبتلع آخر: {names}"
    dead = sorted(set(m.MUST_NAME) - set(names))
    assert not dead, f"اسمٌ متوقَّعٌ لا حالةَ له في CASES (إعادةُ تسميةٍ صامتة؟): {dead}"
    for name, want in m.MUST_NAME.items():
        assert want.startswith("tests/"), f"{name}: الاسمُ المتوقَّع ليس ضابطاً: {want}"


def test_the_command_kind_is_explicit_not_sniffed_from_text():
    """**نوعُ الأمر صريحٌ لا مُستنتَجٌ من النصّ** (مقعدُ البنية · مراجعة ٦١).

    كان `_run` يقرأ النوعَ بـ`".py" in test and not test.startswith("tests/")` ⇒ ضابطٌ يحمل `.py` في
    وسيطه كان يُشغَّل **سكربتًا** بلا pytest فيُصنَّف «تعذّر تشغيل» (أي «لم تُقَس») بلا أن يعرف أحد.
    والآن: **قائمةٌ ⇒ أمرٌ** بمفسّر الشجرة · **نصٌّ ⇒ ضابطُ pytest**. ويُقاس هنا أنّ كلَّ حالةٍ على
    أحد الشكلين، وأنّ `_command_for` تفصل بينهما فعلًا.
    """
    m = _load()
    pytest_cmd = m._command_for("tests/test_x.py::test_y")
    script_cmd = m._command_for(["tools/landing_probe.py", "--from-worktree"])
    assert pytest_cmd[1:3] == ["-m", "pytest"], pytest_cmd
    assert pytest_cmd[-1] == "tests/test_x.py::test_y", pytest_cmd
    assert script_cmd == [m.PY, "tools/landing_probe.py", "--from-worktree"], script_cmd
    kinds = {}
    for name, _target, _old, _new, test in m.CASES:
        kinds[name] = "أمر" if isinstance(test, list) else "ضابطُ pytest"
        assert isinstance(test, (list, str)), f"{name}: شكلُ حالةٍ غيرُ معروف: {type(test)}"
        if isinstance(test, str):
            assert test.startswith("tests/"), (
                f"{name}: نصٌّ لا يبدأ بـ`tests/` ⇒ `_command_for` ستُشغّله كضابطٍ ولن يجد ملفًّا")
    assert sum(1 for k in kinds.values() if k == "أمر") == 2, f"عددُ الحالات الأمريةّ تغيّر: {kinds}"
