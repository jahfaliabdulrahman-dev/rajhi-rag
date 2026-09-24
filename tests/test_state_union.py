"""**ملفُّ الحالة المشترك: تعارضُه يُحلّ بأداةٍ حتميّة لا بيد** (مراجعة ٥٢ · R52-1).

العيّنةُ في `tests/fixtures/state-conflict-r52.md` **ليست ملفًّا مؤلَّفًا**: هي `handoff/STATE.md`
بعينه في لحظة توقّف `git rebase 51b2e9d` من `9622101` (الالتزامُ `1bb07a8`) — التُقطت بحفظ الملفّ
وقت التعارض. فالضابطُ يقيس حالةً وقعت فعلًا، لا حالةً تخيّلناها.

الضوابط الثلاثة: **لا حذفَ لطرف** · **الحكمُ بمعيارٍ واحد** (أحدثُ تاريخ، ثمّ الوارد) · **حتميّة**.
"""
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests/fixtures/state-conflict-r52.md"
TOOL = ROOT / "tools/render_state.py"


def _tool():
    spec = importlib.util.spec_from_file_location("render_state", TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _marker(x: str) -> bool:
    return x.startswith("<<<<<<<") or x.rstrip() == "=======" or x.startswith(">>>>>>>")


def test_the_real_conflict_resolves_without_losing_a_side():
    """**لا يُحذف سطر** — والفحصُ: كلُّ سطرٍ غيرِ علامةٍ في المدخل يظهر في المخرج (مُعلَّقًا أو فعّالًا)."""
    m = _tool()
    text = FIXTURE.read_text(encoding="utf-8")
    out = m.resolve(text)
    assert m.has_conflict(text), "العيّنةُ يجب أن تحمل تعارضًا — وإلا فالضابطُ بلا مجتمع"
    assert not m.has_conflict(out), "الخرجُ ما زال يحمل علامةَ تعارض"
    out_lines = out.splitlines()
    missing = []
    for x in text.splitlines():
        if _marker(x) or not x.strip():
            continue
        if not any(x == y or y == m.LOSER_PREFIX + x for y in out_lines):
            missing.append(x[:70])
    assert not missing, f"سطورٌ ضاعت في الحلّ: {missing}"


def test_the_winner_is_the_newest_and_the_loser_is_marked():
    """**الحكمُ بمعيارٍ واحد**: الفعّالُ هو صاحبُ أحدث تاريخ (٢٠٢٦-٠٩-٢٤ > ٠٩-٢٣)، والخاسرُ مُعلَّقٌ بالوسم."""
    m = _tool()
    out = m.resolve(FIXTURE.read_text(encoding="utf-8"))
    live = [x for x in out.splitlines() if x.startswith("status:")]
    assert len(live) == 1, f"سطرُ حالةٍ فعّالٌ واحدٌ متوقّع، وُجد {len(live)}"
    assert "REVIEW-51" in out and "APPROVE WITH FIXES" in live[0]
    assert m.LOSER_PREFIX + "status: **REQUEST CHANGES" in out, "سطرُ الطرف الخاسر يجب أن يبقى مُعلَّقًا"
    assert "(claude) **REVIEW-51**" in out, "السطرُ السجلّيُّ للطرفَين يُجمع"


def test_the_resolution_is_deterministic():
    """**حتميّة**: تشغيلتان ⇒ مخرَجٌ واحد بايتًا بايتًا (وإلا صار الحلُّ ذاكرةً في رأس من حلّ)."""
    m = _tool()
    text = FIXTURE.read_text(encoding="utf-8")
    assert m.resolve(text) == m.resolve(text)


def test_an_unclosed_conflict_is_refused_not_swallowed():
    """**السمّ**: تعارضٌ بلا إغلاق ⇒ استثناءٌ صريح (لا ملفٌّ صالحٌ مزيّف)."""
    m = _tool()
    with pytest.raises(ValueError):
        m.resolve("# STATE\n\n<<<<<<< HEAD\nstatus: س\n")


def test_the_cli_checks_writes_and_leaves_a_backup(tmp_path):
    """البوّابةُ كما تُستعمل فعلاً: `--check` يفشل على متعارضٍ، و`--union --write` يُصلح ويحفظ النسخة."""
    p = tmp_path / "STATE.md"
    p.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    r1 = subprocess.run([sys.executable, str(TOOL), "--path", str(p), "--check"],
                        capture_output=True, text=True)
    assert r1.returncode == 1 and "تعارضًا غيرَ محلول" in r1.stderr
    r2 = subprocess.run([sys.executable, str(TOOL), "--path", str(p), "--union", "--write"],
                        capture_output=True, text=True)
    assert r2.returncode == 0, r2.stderr
    assert (tmp_path / "STATE.md.bak").exists(), "لا نسخةَ احتياطيّة قبل الكتابة"
    r3 = subprocess.run([sys.executable, str(TOOL), "--path", str(p), "--check"],
                        capture_output=True, text=True)
    assert r3.returncode == 0 and "بلا تعارض" in r3.stdout


def test_a_clean_file_is_not_rewritten(tmp_path):
    """**الضابطُ الموجب**: ملفٌّ سليمٌ لا يُلمس (وإلا صارت الأداةُ محرّكًا يعيد كتابةَ ما لا يحتاج)."""
    p = tmp_path / "STATE.md"
    clean = "# STATE\n\nstatus: سليم\n"
    p.write_text(clean, encoding="utf-8")
    r = subprocess.run([sys.executable, str(TOOL), "--path", str(p), "--union"],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "لا شيءَ يُحلّ" in r.stdout
    assert p.read_text(encoding="utf-8") == clean

def test_an_unclosed_conflict_is_a_named_verdict_not_a_traceback(tmp_path):
    """**على سطر الأوامر**: تعارضٌ بلا إغلاق ⇒ سببٌ ورمزُ خروجٍ مميّز (لا أثرُ بايثون) — مقعدُ المعايير."""
    p = tmp_path / "STATE.md"
    p.write_text("# STATE\n\n<<<<<<< HEAD\nstatus: س\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(TOOL), "--path", str(p), "--union", "--write"],
                       capture_output=True, text=True)
    assert r.returncode == 2, f"رمزُ خروجٍ مميّزٌ متوقّع (2)، صار {r.returncode}"
    assert "Traceback" not in r.stderr, "لا أثرَ بايثون على سطر الأوامر"
    assert "بلا إغلاق" in r.stderr and "لم يُكتب شيء" in r.stderr
    assert p.read_text(encoding="utf-8").startswith("# STATE"), "الملفُّ لم يُلمس"


def test_the_winner_is_decided_by_the_judged_line_not_by_any_line():
    """**المعيارُ من السطر المحكوم** (مقعدُ البنية): تاريخٌ أحدثُ في سطر **سجلّ** لا يقلب الحكم إن كان
    سطرُ الحالة أقدم — وهذا ما كان يقع فعلًا في العيّنة الحقيقيّة."""
    m = _tool()
    text = (
        "# STATE\n\n"
        "<<<<<<< HEAD\n"
        "status: حالٌ أقدم 2026-09-20\n"
        "=======\n"
        "(claude) سطرُ سجلٍّ بتاريخ 2026-09-30\n"
        "status: حالٌ أحدث 2026-09-24\n"
        ">>>>>>> x\n"
    )
    out = m.resolve(text)
    live = [x for x in out.splitlines() if x.startswith("status:")]
    assert len(live) == 1 and "أحدث" in live[0], f"سطرُ الحالة الأحدث هو الفعّال: {live}"
    assert m.LOSER_PREFIX + "status: حالٌ أقدم 2026-09-20" in out, "الخاسرُ يبقى مُعلَّقًا"


def test_a_date_on_a_log_line_does_not_decide(tmp_path):
    """**الضابطُ الموجب للمعيار**: لو حمل الطرفُ الأسفلُ تاريخًا أحدثَ في **سطر سجلّه فقط** فالحكمُ
    لا يتبدّل (وإلا لكان المعيارُ يقرأ ما لا يُحكَم به)."""
    m = _tool()
    text = (
        "# STATE\n\n"
        "<<<<<<< HEAD\n"
        "status: حالٌ أحدث 2026-09-24\n"
        "=======\n"
        "(claude) سجلٌّ بتاريخ 2026-12-31\n"
        "status: حالٌ أقدم 2026-09-20\n"
        ">>>>>>> x\n"
    )
    out = m.resolve(text)
    live = [x for x in out.splitlines() if x.startswith("status:")]
    assert len(live) == 1 and "أحدث" in live[0], f"سطرُ الحالة يحكم لا سطرُ السجلّ: {live}"
