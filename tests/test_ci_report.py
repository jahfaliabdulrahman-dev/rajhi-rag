"""ضوابطُ `tools/ci_report.py` — «ولا يُقال أخضرُ بلا دليل» (مراجعة ٦١ · R61-1).

الملاحظةُ التي وُلدت منها هذه الأداة: تقريرُ دفعٍ قال «CI ناجح» وقِيس مرجعٌ واحدٌ من خمسة،
وفرعان مدفوعان كانا أحمرَين. فالضوابطُ هنا تُثبّت **ما لا يُقبل أن يُقال**: لا أخضرَ لمرجعٍ
أحمر، ولا أخضرَ لتشغيلٍ على التزامٍ **قديم** (درسُ §٢٧)، ولا أخضرَ بلا تشغيل، ولا صمتَ عند تعذّر
القياس — «غيرُ المقروء ليس نظيفاً».
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_report", ROOT / "tools" / "ci_report.py")
assert spec and spec.loader, "لا يُحمَّل الضابطُ على نيّة: الملفُّ يجب أن يوجد"
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)

HEAD = "cbc8f40" + "a" * 33          # شكلُ sha كاملٌ، وقيمةٌ وهميّة
OTHER = "da6403b" + "b" * 33


def _fake(monkeypatch, payload, *, rc=0, sha: str | None = HEAD, local=None):
    """يُستبدَل نداءُ `gh` وقراءةُ الالتزام — فلا شبكةَ ولا GitHub في الضابط."""
    monkeypatch.setattr(cr, "_gh",
                        lambda args: (rc, json.dumps(payload) if rc == 0 else "gh: not found"))
    monkeypatch.setattr(cr, "_pushed_sha", lambda ref: sha)
    monkeypatch.setattr(cr, "_local_sha", lambda ref: local if local is not None else sha)


def _run(conclusion, *, status="completed", head=HEAD, name="publish-guard"):
    return [{"conclusion": conclusion, "status": status, "headSha": head, "workflowName": name}]


def test_a_green_run_on_the_same_commit_passes(monkeypatch, capsys):
    _fake(monkeypatch, _run("success"))
    assert cr.main(["chore/round56-evidence"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_a_red_ref_is_named_and_blocks(monkeypatch, capsys):
    _fake(monkeypatch, _run("failure"))
    assert cr.main(["claude/handoff-execution-196328"]) == 1, \
        "مرجعٌ أحمرُ يجب أن يُسقط — ومن هنا وُلد البندُ (R61-1)"
    out = capsys.readouterr().out
    assert "أحمر" in out and "claude/handoff-execution-196328" in out, "ويُسمّى باسمه لا بجملةٍ عامّة"


def test_a_stale_run_never_blesses_a_new_head(monkeypatch, capsys):
    """**§٢٧ بالآلة:** تشغيلٌ أخضرُ على التزامٍ آخرَ ليس شهادةً لهذا الرأس."""
    _fake(monkeypatch, _run("success", head=OTHER))
    assert cr.main(["chore/round56-evidence"]) == 1
    assert "قديم" in capsys.readouterr().out


def test_no_run_at_all_is_not_green(monkeypatch, capsys):
    _fake(monkeypatch, [])
    assert cr.main(["claude/review-56"]) == 1
    assert "بلا تشغيل" in capsys.readouterr().out


def test_a_run_still_going_is_not_green_yet(monkeypatch, capsys):
    _fake(monkeypatch, _run(None, status="in_progress"))
    assert cr.main(["claude/review-56"]) == 1
    assert "جارٍ" in capsys.readouterr().out


def test_an_unreadable_gh_blocks_with_two(monkeypatch, capsys):
    """«غيرُ المقروء ليس نظيفاً»: تعذّرُ القياس رمزُه 2 — لا صفرٌ ولا صمت."""
    _fake(monkeypatch, [], rc=1)
    assert cr.main(["chore/round56-evidence"]) == 2
    assert "غيرُ مقروء" in capsys.readouterr().out


def test_one_red_among_greens_is_enough_to_block(monkeypatch, capsys):
    """**الدفعةُ كلُّها تُقاس** — وجودُ أخضرَ واحدٍ لا يُبرّئ الدفع (وهو نصُّ الملاحظة)."""
    _fake(monkeypatch, _run("success"))
    states = []

    def gh(args):
        ref = args[args.index("--branch") + 1]
        states.append(ref)
        bad = ref == "claude/handoff-execution-196328"
        return 0, json.dumps(_run("failure" if bad else "success"))

    monkeypatch.setattr(cr, "_gh", gh)
    assert cr.main(["chore/round56-evidence", "claude/handoff-execution-196328"]) == 1
    assert states == ["chore/round56-evidence", "claude/handoff-execution-196328"], \
        "الأداةُ تمرّ على كلِّ مرجعٍ مدفوع — لا على أوّلِه"


def test_the_compared_commit_is_the_pushed_one_not_the_local_one(monkeypatch):
    """**مُثبَتٌ بقياسٍ حيّ:** القياسُ كان على المرجع المحلّيّ، وفرعٌ محلّيٌّ متقدّمٌ على المدفوع
    يُوسَم «قديمًا» وهو **أحمرُ** في الحقيقة ⇒ وسمٌ مضلِّل. المقصودُ صدقُ تقرير الدفع،
    وتقريرُ الدفع يتكلّم عن **المدفوع** ⇒ `origin/<ref>` أوّلًا."""
    calls: list[str] = []

    def run(cmd):
        calls.append(cmd[-1])
        return (0, OTHER) if cmd[-1] == "origin/x" else (0, HEAD)

    monkeypatch.setattr(cr, "_run", run)
    assert cr._pushed_sha("x") == OTHER, "المدفوعُ هو ما يُقاس، لا ما في اليد"
    assert calls[0] == "origin/x", "ويُقرأ `origin/<ref>` أوّلًا"


def test_an_unresolvable_ref_cannot_be_called_green(monkeypatch, capsys):
    """ولا صمتَ: مرجعٌ لا نعرف التزامَه ⇒ «غيرُ مقروء» (رمزٌ 2) لا «أخضر»."""
    _fake(monkeypatch, _run("success"), sha=None)
    assert cr.main(["ghost/ref"]) == 2
    assert "غيرُ مقروء" in capsys.readouterr().out


def test_a_green_push_notes_an_unpushed_local_commit(monkeypatch, capsys):
    """الأخضرُ يبقى أخضرَ، **ويُعلَن** أنّ محلّيًّا متقدّمٌ على المدفوع (لا يُخفى ولا يُسقط)."""
    _fake(monkeypatch, _run("success"), local=OTHER)
    assert cr.main(["chore/round56-evidence"]) == 0
    out = capsys.readouterr().out
    assert "غيرُ مدفوع" in out and "PASS" in out


def test_the_reminder_names_the_command_and_judges_nothing(monkeypatch, capsys):
    """**لماذا تذكيرٌ لا حُكم:** الـCI يعمل **بعد** الدفع، فخطّافُ ما قبل الدفع لا يملك ما يقيسه
    ⇒ يقف التذكيرُ في المسار الذي يُنسى فيه، ويبقى الحُكمُ لأداةٍ تُشغَّل بعده. وشبكةٌ في
    خطّاف الدفع عطبٌ في المسار الحسّاس ⇒ لا نداءَ شبكةٍ هنا."""
    def boom(args):
        raise AssertionError("التذكيرُ لا يستدعي `gh` — لا شبكةَ في مسار الدفع")

    monkeypatch.setattr(cr, "_gh", boom)
    assert cr.main(["--remind", "chore/round56-evidence", "claude/review-56"]) == 0
    out = capsys.readouterr().out
    assert "ci_report.py chore/round56-evidence claude/review-56" in out, "ويُسمّي الأمرَ بمراجعه كما هي"
    assert "PASS" not in out, "ولا يُدّعى حُكم"
