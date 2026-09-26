"""ضوابطُ `tools/ci_report.py` — «ولا يُقال أخضرُ بلا دليل» (مراجعة ٦١ · R61-1).

الملاحظةُ التي وُلدت منها هذه الأداة: تقريرُ دفعٍ قال «CI ناجح» وقِيس مرجعٌ واحدٌ من خمسة،
وفرعان مدفوعان كانا أحمرَين. فالضوابطُ هنا تُثبّت **ما لا يُقبل أن يُقال**: لا أخضرَ لمرجعٍ
أحمر، ولا أخضرَ لتشغيلٍ على التزامٍ **قديم** (درسُ §٢٧)، ولا أخضرَ بلا تشغيل، ولا صمتَ عند تعذّر
القياس — «غيرُ المقروء ليس نظيفاً».
"""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

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
    monkeypatch.setattr(cr, "_pushed_sha", lambda ref, remotes_list=None: sha)
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
    وتقريرُ الدفع يتكلّم عن **المدفوع** ⇒ `<remote>/<branch>` أوّلًا (والريموتُ يُسأل git).
    (والترتيبُ يُقاس بين **قراءتَي الالتزام** لا على أوّل نداءٍ خارجيّ: الأداةُ تسأل `git remote`
    قبلَهما ⇒ كان الشرطُ يقيس النداءَ الأوّل لا القاعدة.)"""
    calls: list[str] = []
    monkeypatch.setattr(cr, "_git_remotes", lambda: "origin\n")

    def run(cmd):
        calls.append(cmd[-1])
        return (0, OTHER) if cmd[-1] == "origin/x" else (0, HEAD)

    monkeypatch.setattr(cr, "_run", run)
    assert cr._pushed_sha("x") == OTHER, "المدفوعُ هو ما يُقاس، لا ما في اليد"
    assert calls == ["origin/x"], f"وحين يُوجَد المدفوع لا يُقرأ المحلّيّ (يُختصر): {calls}"

    # **والعكسُ يُقاس كذلك:** بلا مرجعٍ متعقَّبٍ يُقرأ المحلّيّ ولا يُترك الفرعُ بلا مرساة.
    monkeypatch.setattr(cr, "_run", lambda cmd: (0, HEAD))
    assert cr._pushed_sha("x") == HEAD


def test_a_git_style_ref_resolves_to_the_pushed_commit_not_the_local_one(monkeypatch):
    """**مقيسٌ في مقعد البنية:** `refs/heads/main` كان يُنتج `origin/refs/heads/main` (لا وجودَ له)
    ⇒ يسقط إلى **المرجع المحلّيّ** فيُوسَم الرأسُ المدفوع «قديمًا» كذبًا. والآن يُطبَّع في الموضعين."""
    reads: list[str] = []

    def local(ref):
        reads.append(ref)
        return OTHER if ref == "origin/main" else HEAD

    monkeypatch.setattr(cr, "_local_sha", local)
    monkeypatch.setattr(cr, "_git_remotes", lambda: "origin\n")
    assert cr._pushed_sha("refs/heads/main") == OTHER
    assert reads[0] == "origin/main", f"يُبنى من **اسم الفرع** لا من المرجع: {reads}"


def test_every_configured_remote_is_tried_and_unknown_names_are_not_stripped(monkeypatch):
    """قائمةُ الريموتات **تُسأل git** لا تُكتب بيد (مقعد المعايير): ريموتٌ غيرُ `origin`/`upstream`
    كان يمرّ بلا تحويل ⇒ `BLOCK` الكاذبُ يعود في ذلك الشكل. ومع اسمٍ ليس ريموتًا **لا نصّ**
    (لا نخترع تطبيعًا)."""
    monkeypatch.setattr(cr, "_git_remotes", lambda: "origin\nfork\n")
    assert cr.branch_of("fork/main") == "main"
    assert cr.branch_of("refs/remotes/fork/main") == "main"
    assert cr.branch_of("refs/heads/main") == "main"
    assert cr.branch_of("feature/x") == "feature/x"


def test_an_explicitly_empty_remote_list_is_never_overridden_by_asking_git(monkeypatch):
    """**وعقدُ المعامَل واحد (مقعدُ البنية · مراجعة إغلاق ٦٤):** `None` ⇒ «اسأل git» · و`[]` ⇒ «هذه هي
    الريموتات — لا تسأل». وكان `or` في `_pushed_sha` يجعل `[]` تُسقط إلى السؤال، بينما `branch_of` تعتبر
    القائمةَ المُمرَّرة نهائيّةً ⇒ عقدان مختلفان لمعامَلٍ واحدٍ في ملفٍّ يعلن توحيدَ الموضع."""
    calls = []
    monkeypatch.setattr(cr, "_run", lambda cmd: (calls.append(cmd), (0, ""))[1])
    cr._pushed_sha("main", [])
    asked = [c for c in calls if c[:2] == ["git", "remote"]]
    assert not asked, f"قائمةٌ فارغةٌ مُعلَنة لا تُستبدَل بسؤال git (قِيس: {asked})"


def test_the_remote_list_is_asked_fresh_and_never_cached_globally(monkeypatch):
    """**إغلاقُ ملاحظة مقعد البنية:** التخزينُ العالميُّ (`lru_cache`) كان يُبطل سِمَةَ `_run` التي
    يُعلنها هذا الملفّ على أنّها **نقطةُ الاستبدال الوحيدة**: بعد نداءٍ حقيقيّ يصير تبديلُها بلا أثر
    (قِيس عند المقعد: `remotes()` ⇒ `['origin']` والمتوقَّع `['upstream']`). فالضابطُ يعضّ على إعادة
    أيّ تخزين: يستهلك نداءً حقيقيًّا أوّلًا، ثمّ يُبدّل `_run` ويسأل."""
    cr.remotes()                        # يستهلك أيَّ حالةٍ مخزَّنةٍ محتملة (نداءٌ حقيقيّ إلى git)

    def run(cmd):
        return (0, "upstream\n") if cmd[:2] == ["git", "remote"] else (0, "")

    monkeypatch.setattr(cr, "_run", run)
    assert cr.remotes() == ["upstream"], "القائمةُ تُسأل طازجةً من `_run` لا من حالةٍ مخزَّنة"


def test_a_remote_that_is_not_origin_is_tried_when_it_holds_the_pushed_commit(monkeypatch):
    """**طَفرةٌ قِيست على إغلاق F7 (مقعد المعايير):** إبدالُ الدورة على `remotes()` بقائمةٍ مغلقة
    `["origin"]` **لم يُسقط شيئًا** (29 passed) ⇒ فالضابطُ القائمُ يقيس **تطبيعَ الأسماء** في `branch_of`
    لا **دورانَ الريموتات** في `_pushed_sha`. فالمَشهدُ هنا يجعل المدفوعَ على ريموتٍ غير `origin` **وحدَه**."""
    reads: list[str] = []
    monkeypatch.setattr(cr, "_git_remotes", lambda: "upstream\norigin\n")

    def local(ref):
        reads.append(ref)
        return OTHER if ref == "upstream/main" else HEAD

    monkeypatch.setattr(cr, "_local_sha", local)
    assert cr._pushed_sha("main") == OTHER, "يُجرَّب **كلُّ** ريموتٍ مُهيَّأ لا `origin` وحدَه"
    assert "upstream/main" in reads, f"وإلّا ما كان الريموتُ الثاني يُقرأ أصلًا: {reads}"

    # **والعكسُ مُقاسٌ كذلك:** بريموتٍ واحدٍ لا يملك المدفوعَ يُقرأ المرجعُ المحلّيّ (فيُعَلن التقادم).
    monkeypatch.setattr(cr, "_git_remotes", lambda: "origin\n")
    assert cr._pushed_sha("main") == HEAD


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


# ---------------------------------------------------------------------------------------------
# R62: مُحلِّلُ سطور `pre-push` — **والأشكالُ هنا مقيسةٌ حيًّا من git نفسِه** لا من ظنّ
# (نسخةٌ اختباريّةٌ محليّة: دفعُ فرعٍ · وسمٌ · حذفُ مرجع · رأسٌ مفصول). ومن هذه الأشكال وُلد
# الحاجبُ الأوّل في مراجعة الجولة ٦٢: `awk '{print $1}'` كان يقرأ `(delete)`/`HEAD`/`refs/tags/…`
# كأنّها أسماءُ فروع ⇒ تذكيرٌ بلا معنى، وسطرٌ يُسقط دفعاً مشروعاً صامتاً.
# ---------------------------------------------------------------------------------------------
Z = "0" * 40          # sha الوجهة لمرجعٍ جديد — يُبنى ولا يُكتب (قاعدةُ الأرقام الطويلة)
SHA_A = "f191a935c6ebe3536337678e91104ca5e2310c40"
SHA_B = "17fc94a76958d96b385dfdcdd01b56c88a1a45a3"

MEASURED_STDIN = (
    ("update", f"refs/heads/main {SHA_A} refs/heads/main {Z}", ["main"], 0, 0),
    ("tag", f"refs/tags/v1 {SHA_A} refs/tags/v1 {Z}", [], 1, 0),
    ("delete", f"(delete) {Z} refs/heads/old {SHA_A}", [], 0, 1),
    ("detached-head", f"HEAD {SHA_B} refs/heads/new {Z}", ["new"], 0, 0),
    ("rename", f"refs/heads/a {SHA_B} refs/heads/b {Z}", ["b"], 0, 0),
    ("empty", "", [], 0, 0),
)


@pytest.mark.parametrize("name,line,refs,non_branch,deleted", MEASURED_STDIN)
def test_pushed_refs_are_read_by_destination_not_by_field_one(name, line, refs, non_branch, deleted):
    """**وجهةُ الدفع هي المقصودة** (الحقلُ الثالث): `HEAD:refs/heads/new` يُقاس عليه `new`،
    والوسمُ والحذفُ لا يُقاسان كأنّهما فرعان (ويُعلَن عدُّهما)."""
    assert cr.parse_pushed_refs(line) == (refs, non_branch, deleted), name


def test_a_mixed_push_counts_every_ref_and_declares_what_is_not_measured():
    """دفعةٌ مختلطة: فرعٌ يُقاس، ووسمٌ يُعلَن أنّه ليس فرعاً (لا يُسقَط ولا يُوسَم فرعاً)."""
    line = (f"refs/heads/main {SHA_A} refs/heads/main {Z}\n"
            f"refs/tags/v1 {SHA_A} refs/tags/v1 {Z}\n")
    assert cr.parse_pushed_refs(line) == (["main"], 1, 0)


@pytest.mark.parametrize("name,line,refs,non_branch,deleted", MEASURED_STDIN)
def test_the_pre_push_reminder_never_blocks_a_push(monkeypatch, capsys, name, line, refs, non_branch, deleted):
    """**R62-F1 (الحاجب):** خطّافٌ يُسقط دفعاً مشروعاً (وسمٌ · حذفُ فرع · رأسٌ مفصول · دفعٌ بلا
    جديد) يُصنع به الحافزُ على `--no-verify` الذي يُسقط حرّاسَ الأمن ⇒ فالتذكيرُ يخرج **صفراً**
    في كلّ شكل، ولا يمسّ الشبكة."""
    def boom(args):
        raise AssertionError("التذكيرُ لا يستدعي `gh` — لا شبكةَ في مسار الدفع")

    monkeypatch.setattr(cr, "_gh", boom)
    monkeypatch.setattr(cr.sys, "stdin", io.StringIO(line))
    assert cr.main(["--pre-push"]) == 0, f"{name}: الدفعُ المشروع لا يُسقَط"
    out = capsys.readouterr().out
    for r in refs:
        assert r in out, f"{name}: يُسمّى المرجعُ المقصود ({r})"
    if non_branch or deleted:
        assert "لا تشغيلَ يُقاس عليهما" in out, f"{name}: ويُعلَن ما لا يُقاس (لا يُخفي)"


def test_a_run_without_a_headsha_cannot_be_called_green(monkeypatch, capsys):
    """**فشلٌ مُغلَق:** تشغيلٌ بلا `headSha` (أو بحقلٍ فارغ) لا يُقابَل بالمدفوع ⇒ «غيرُ مقروء»
    ورمزُه 2 — لا «أخضر». حُكمٌ بلا مرساةٍ ليس حكماً، وهو عينُ صنفِ R61-1 طبقةً أعمق."""
    for payload in ({"conclusion": "success", "status": "completed", "workflowName": "publish-guard"},
                    {"conclusion": "success", "status": "completed", "headSha": "",
                     "workflowName": "publish-guard"}):
        monkeypatch.setattr(cr, "_gh", lambda args, p=payload: (0, json.dumps([p])))
        monkeypatch.setattr(cr, "_pushed_sha", lambda ref, remotes_list=None: HEAD)
        assert cr.main(["chore/round56-evidence"]) == 2, payload
        assert "غيرُ مقروء" in capsys.readouterr().out


def test_json_mode_is_machine_readable_and_keeps_the_limit_on_stderr(monkeypatch, capsys):
    """`--json` مُعلَنٌ «للسجلّ» ⇒ يجب أن يُستهلك آليًّا: stdout = JSON وحده، والبيانُ البشريّ
    (ومنها إعلانُ الحدّ) على stderr — فلا يُخفى ولا يُفسد السجلّ."""
    _fake(monkeypatch, _run("success"))
    assert cr.main(["--json", "chore/round56-evidence"]) == 0
    cap = capsys.readouterr()
    data = json.loads(cap.out)                       # كان يسقط: جملةُ الحدّ تُطبَع بعد فرع `--json`
    assert isinstance(data, list) and data[0]["state"] == "أخضر"
    assert "حدُّ هذا الفحص" in cap.err and "حدُّ هذا الفحص" not in cap.out


def test_a_tracking_ref_is_measured_by_its_branch_name(monkeypatch, capsys):
    """**قِيس قبل الإغلاق (ملاحظةُ الجولة ٦٤):** `ci_report.py origin/main` كان يقول «بلا تشغيل»
    ويُسقط `BLOCK` **كاذبًا** — لأنّ `gh run list --branch origin/main` لا يعرف فرعاً بهذا الاسم،
    والتشغيلُ موجودٌ باسم الفرع الحقيقيّ (`main`). فالمقابلةُ على اسم الفرع، والمرجعُ المرجعيُّ
    يبقى مقبولًا في البيان **والتحويلُ يُعلَن** (لا صمت)."""
    seen: list[list[str]] = []

    def gh(args):
        seen.append(list(args))
        return 0, json.dumps([{"conclusion": "success", "status": "completed",
                               "headSha": HEAD, "workflowName": "publish-guard"}])

    monkeypatch.setattr(cr, "_gh", gh)
    monkeypatch.setattr(cr, "_pushed_sha", lambda ref, remotes_list=None: HEAD)
    monkeypatch.setattr(cr, "_local_sha", lambda ref: HEAD)
    assert cr.main(["origin/main"]) == 0
    out = capsys.readouterr().out
    assert seen[0][2] == "--branch" and seen[0][3] == "main", \
        "يُسأل `gh` باسم الفرع لا بالمرجع المرجعيّ"
    assert "قِيس على الفرع `main`" in out, "ويُعلَن التحويلُ (لا صمت)"
    assert cr.branch_of("refs/heads/x") == "x" and cr.branch_of("main") == "main"
