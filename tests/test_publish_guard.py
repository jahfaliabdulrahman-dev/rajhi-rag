"""Publish guard tests — the dedup bug, the digit-table exemption, and the
four structural holes an external audit opened are regressions; lock them
here. Mostly no git operations — **إلّا ضوابطُ الذيل، وهي كما تُقاس لا كما تُوصف:** اثنان ينشئان مستودعَ
git كاملًا داخل `tmp_path` (ثقبُ المسار غير ASCII · تسريبٌ في التاريخ وحدَه) · وواحدٌ ينسخ الأداةَ إلى
مجلّدٍ **ليس مستودعًا** ثم يُهيّئ فيه مستودعًا فارغًا (تعذّرُ القراءة · صفرُ ملفٍّ مُتتبَّع) · وواحدٌ يقرأ
نصَّ الـworkflow · وواحدٌ يشغّل `_git`/`_git_z` على عَلَمٍ لا وجودَ له **داخل مستودع المشروع** (قراءةٌ
فاشلةٌ متوقّعة: لا تلمس الشجرةَ ولا الفهرس ولا `HEAD`).

INVARIANT (enforced below, not promised in prose): this file ships no real
statement data — every account-shaped value is invented — and every payload
is assembled at runtime, so the guard's own tests cannot trip the guard.
The previous revision asserted that invariant in its header while carrying
the real account number split across two literals; the split defeated
`long_digits` structurally (audit S1). Hence two hard rules here:
  1. `_PARTS` holds the invented pieces; nothing is written as `"a" + "b"`.
  2. `test_this_file_passes_the_guard` fails the moment that slips.
Re-verify the invented value against the real cache whenever it exists
(never in CI): count occurrences of the invented number inside
`data/local_sample/*/results/pg-*.json` and expect ZERO.
"""

import pytest
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import publish_guard as pg  # noqa: E402

def _run(ch: str, n: int) -> str:
    """One character repeated.

    Every account-shaped value below is built from THIS, so the file contains
    no digit literal at all — not even a fragment. The previous revision kept
    the pieces as literals (`_PARTS = ("990000", "1199")`) and needed a
    working-tree allowlist entry to survive its own rule; a rule its own tests
    must be exempted from is not a rule. With nothing to find, the exemption
    narrows to `history:` — the old commits — which is where it belongs.
    """
    return ch * n


_PARTS = (_run("9", 6), _run("1", 4))
_PARTS_AR = (_run("٩", 6), _run("١", 4))
FAKE_ACCOUNT = "".join(_PARTS)                    # ten digits, none of them here
FAKE_ACCOUNT_AR = "".join(_PARTS_AR)
FAKE_IBAN_GROUPS = [_run("9", 4), _run("0", 4), _run("1", 4), _run("9", 4)]


def _scan(text: str) -> list[tuple]:
    findings: list[tuple] = []
    pg._scan_text("tests/probe.py", text, "tree", findings, [])
    return findings


def _merge_message() -> str:
    return ("Merge 88e4ed953b2c1c28697b0ec5613e7f3082f4ce99 into "
            "c83f197c4f0adaf64a362541821574ede9eb90a0")


def test_git_generated_merge_message_is_skipped_not_blocked():
    """GitHub writes the merge commit, not a human: its two hex SHAs weld into a
    36-digit run and the guard blocked every pull request on it. The skip is
    declared (counted and printed), and a human message is still scanned."""
    assert pg._is_git_generated(_merge_message())
    assert pg._is_git_generated("Merge pull request #5 from owner/branch")
    assert pg._is_git_generated('Revert "feat: something"')
    assert not pg._is_git_generated("Merge the two designs into one")
    assert not pg._is_git_generated(f"حساب {FAKE_ACCOUNT_AR} مرحّل")


def test_digit_table_ramp_is_exempt_from_long_digits():
    assert pg._is_digit_table("٠١٢٣٤٥٦٧٨٩")
    assert pg._is_digit_table("01234567890123456789")
    assert pg._is_digit_table("۱۲۳۴۵۶۷۸۹۰")          # a ROTATED ramp
    assert not pg._is_digit_table(FAKE_ACCOUNT_AR)     # a real-looking run
    assert not pg._is_digit_table("10000001")


def test_long_digit_rule_flags_account_like_runs():
    rid, sev, rx, _ = [r for r in pg.TEXT_RULES if r[0] == "long_digits"][0]
    m = rx.search("FRACCT/" + FAKE_ACCOUNT + "FR")
    assert m and not pg._is_digit_table(m.group(0))
    assert rx.search("٣٠٠,٠٠") is None


def test_snippet_masks_long_digit_runs():
    out = pg._snippet("balance " + FAKE_ACCOUNT + " riyals")
    assert FAKE_ACCOUNT not in out and "99…" in out


def test_allowlist_parsing_skips_comments(tmp_path, monkeypatch):
    f = tmp_path / ".publish-allowlist"
    f.write_text("# comment\nname_token :: tools/* :: reason\nbadline\n",
                 encoding="utf-8")
    monkeypatch.setattr(pg, "ROOT", tmp_path)
    entries = pg.load_allowlist()
    assert entries == [("name_token", "tools/*")]
    assert pg._allowed(entries, "name_token", "tools/x.py")
    assert not pg._allowed(entries, "home_path", "tools/x.py")


# ── S1 regression: structural bypasses the plain rule cannot see ──────────

def test_spaced_digit_run_is_caught():
    """An IBAN/card-style run — uniform groups of four — is one number to a
    human and invisible to a plain ≥10-digit scan."""
    payload = " ".join(FAKE_IBAN_GROUPS)
    assert [f[1] for f in _scan("ACCT=" + payload)] == ["long_digits"]


def test_adjacent_dates_and_timestamps_are_not_welded():
    """False positives found by running the first draft against this very
    repository: two 8-digit dates, and a hyphenated ISO timestamp. Neither is
    a uniform 3/4-wide group, so neither may be joined into an account run."""
    assert _scan("like " + " ".join(("١٤٣٩٠٧٢٢", "٢٠١٨٠٤٠٨"))) == []
    assert _scan("handoff/sulaiman/" + "20260917" + "-" + "172327"
                 + "-bootstrap.md") == []
    assert _scan("A#" + "٩٩٩" + "-" + "٠٠٠١١١٢٢٢" + " SPOUD١٠١") == []


def test_separated_digit_run_is_caught():
    payload = ".".join(FAKE_IBAN_GROUPS)          # the 1.234.567.890 idiom
    assert "long_digits" in [f[1] for f in _scan("ACCT=" + payload)]


def test_unrelated_numbers_are_not_welded_together():
    """Two amounts of different widths on one line must stay two numbers —
    otherwise every statement row becomes a false positive."""
    assert _scan(" ".join(("١٢٣٤", "٥٦٧٨٩"))) == []


def test_concat_trick_is_caught():
    """The exact S1 shape: the run appears only after joining two literals."""
    q = '"'
    payload = "A = " + q + _PARTS[0] + q + " + " + q + _PARTS[1] + q
    assert "concat_digits" in [f[1] for f in _scan(payload)]


def test_every_occurrence_is_reported_not_just_the_first():
    line = "A=" + FAKE_ACCOUNT + " B=" + FAKE_ACCOUNT_AR
    hits = [f for f in _scan(line) if f[1] == "long_digits"]
    assert len(hits) == 2


def test_this_file_passes_the_guard():
    """The guard's own tests are scanned by the guard. If a future edit adds
    a real-looking run — or writes one as `"a" + "b"` — this test fails
    before the push does."""
    text = Path(__file__).read_text(encoding="utf-8")
    blocks = [f for f in _scan(text) if f[0] == "BLOCK"]
    assert blocks == [], blocks


# ── P1-6 regression: opaque binaries and commit messages ─────────────────

def test_opaque_binary_needs_an_allowlist_line():
    f: list[tuple] = []
    pg._check_path("export/ledger.xlsx", "tree", f, [])
    assert [x[1] for x in f] == ["opaque_binary"]
    f = []
    pg._check_path("assets/fonts/Noto.ttf", "tree", f,
                   [("opaque_binary", "assets/fonts/*")])
    assert f == []


def test_unknown_binary_cannot_pass_silently():
    v = pg._binary_verdict("data/rows.xyz", [])
    assert v is not None and v[0] == "BLOCK" and v[1] == "undecodable"
    assert pg._binary_verdict("shot.png", []) is None      # media: PATH_RULES
    assert pg._binary_verdict("rows.xyz", [("undecodable", "*.xyz")]) is None


def _guard_source() -> str:
    return (Path(pg.ROOT) / "tools" / "publish_guard.py").read_text(
        encoding="utf-8")


# ── self-exclusion and worktree coverage ─────────────────────────────────

def test_guard_source_passes_its_own_rules():
    """`tools/publish_guard.py` is in SKIP_PATHS — it is never scanned by
    itself. That self-exclusion is a HOLE: a real account number once sat in
    its own docstring, written as two added literals and therefore invisible
    to everything. The source is scanned here instead."""
    blocks = [f for f in _scan(_guard_source()) if f[0] == "BLOCK"]
    assert blocks == [], blocks


def test_every_tracked_text_file_is_clean():
    """Working-tree twin of `publish_guard --tree`: the tree scan reads HEAD
    blobs, so a bad edit is caught at push time; this one reads the files on
    disk (including the guard's own source) and fails before the commit."""
    import subprocess

    root = Path(pg.ROOT)
    tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True,
                             text=True).stdout.split()
    findings: list[tuple] = []
    for rel in tracked:
        if Path(rel).suffix.lower() in (pg.BINARY_EXTS | pg.OPAQUE_EXTS):
            continue
        if not (root / rel).exists():
            # ملفٌّ محذوفٌ ولم يُلتزم بعد: الفهرسُ يسبق الشجرة، والحارسُ لا ينهار
            # على حذفٍ معلَّق — الفشلُ هنا كان `FileNotFoundError` لا حكماً.
            continue
        here: list[tuple] = []
        pg._scan_text(rel, (root / rel).read_text(encoding="utf-8"),
                      "worktree", here, pg.load_allowlist())
        findings += [f for f in here if f[0] == "BLOCK"]
    assert findings == [], findings


def test_pre_push_scans_every_pushed_commit():
    """A commit that carried PII and was later rewritten lives exactly in the
    commits an SHA-ordered sample would drop, so there is no sampling."""
    src = _guard_source()
    assert "[:200]" not in src and "first 200 commits" not in src


def test_commit_messages_are_wired_into_the_scan():
    src = _guard_source()
    assert "def scan_messages" in src
    assert "git-msg/" in src
    assert "scan_messages(findings, entries)" in src


# ── البصمةُ المقتطعة ليست حساباً (عطلٌ في الحارس نفسه، أُغلق بقياس) ──────────
# ملفُّ دليلٍ يحمل بصماتِ صفحاتٍ **مقتطعة** (16 محرفاً) حُجب ثلاثاً: الدليلُ يُحجب
# **لأنه دليل**. والفاصل الحقيقي هو الحرف اللاتيني الصغير (a–f) لا الطول وحده —
# فالحسابُ والبطاقة أرقامٌ بلا حروف، والـIBAN بحروفٍ كبيرة.

def _scan_one(text: str) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    pg._scan_text("docs/evidence/probe.json", text, "tree", findings, [])
    return [(f[0], f[1]) for f in findings]


def test_a_truncated_digest_with_letters_is_evidence_not_an_account():
    line = f' "sha256": "{_run("4", 6)}ab{_run("9", 8)}c{-0 if False else ""}"'
    assert not [r for r in _scan_one(line) if r[1] == "long_digits"], \
        "بصمةٌ مقتطعة (حروف a–f) يجب ألا تُحجب"


def test_an_all_digit_run_is_still_blocked_however_long():
    line = f' "account": "{FAKE_ACCOUNT}"'
    assert [r for r in _scan_one(line) if r[1] == "long_digits"], \
        "رقمٌ كلُّه أرقام يبقى محجوباً"


def test_an_upper_case_iban_is_still_blocked():
    line = ' "iban": "SA' + _run("8", 20) + '6129"'
    assert [r for r in _scan_one(line) if r[1] == "long_digits"], \
        "IBAN بحروفٍ كبيرة يبقى محجوباً"


def test_a_page_number_list_is_exempted_by_a_written_allowlist_entry():
    """قائمةُ أرقام صفحاتٍ مفصولةٍ بفراغ **تُحجب بقصد** — لأن الحسابَ نفسه يُكتب
    بثلاثاتٍ بفراغ، فالقاعدة لا تستطيع التمييز ⇒ **الثمنُ مقبول**: تُحجب القائمة
    ويُستثنى **ملفٌّ بعينه** بسببٍ مكتوب في `.publish-allowlist`.

    وهذا هو الفرقُ الذي فرضه المدقّق: كان استثنائي **توسيعاً للقاعدة** فمرّت أرقامُ
    حسابٍ حقيقية؛ فصار استثناءً **لملفٍ** — أضيقَ أثراً وأصدقَ في التوثيق.
    """
    list_line = "مذكورة: " + " ".join(str(n * 7) for n in range(3, 20))
    assert [r for r in _scan_one(list_line) if r[1] == "long_digits"], \
        "القاعدة تحجب القائمة (ثمنُ عدم فتح الثغرة)"
    allow = (Path(pg.ROOT) / ".publish-allowlist").read_text(encoding="utf-8")
    entry = next((ln for ln in allow.splitlines()
                  if ln.startswith("long_digits :: handoff/claude/")), None)
    assert entry, "لا بد أن يكون الاستثناءُ لملفٍ بعينه لا للشجرة"
    assert len(entry.split("::")) == 3 and entry.split("::")[2].strip(), \
        "كل استثناءٍ بسببٍ مكتوب"


def test_a_three_wide_hyphenated_cheque_is_still_blocked():
    line = ' "cheque": "' + "-".join(_run(str(n), 3) for n in range(1, 6)) + '"'
    assert [r for r in _scan_one(line) if r[1] == "long_digits"], \
        "صكٌّ بثلاثاتٍ موصولةٍ بشُرَط يبقى محجوباً"


def test_a_four_wide_card_still_blocked_even_with_spaces():
    line = ' "card": "' + " ".join(_run(str(n), 4) for n in (4, 8, 2, 6)) + '"'
    assert [r for r in _scan_one(line) if r[1] == "long_digits"], \
        "بطاقةٌ برُباعياتٍ مفصولةٍ بفراغ تبقى محجوبة"


def test_a_nested_real_data_copy_is_never_excused():
    """**تداخلُ النسخ يُخرج بياناتٍ حقيقيّةً من الحماية (مراجعة ٦٧ · R67-1).**

    قِيس: `cp -R data <نسخةٍ فيها data/>` تُنتج `data/data/` ⇒ **٣٦١٠ ملفًا ومنها المفتاح** خارج
    `.gitignore` الجذريّ، وقابلةٌ للإيداع بـ`git add .` — والحارسُ كان يقابل **بادئة** المسار وحدَها.
    فالمقابلةُ على **مقاطع** المسار، والتداخلُ لا يُعفي.
    """
    assert pg.real_data_path("data/local_sample/slice_629p/slice_report.json"), "الجذرُ محجوب"
    assert pg.real_data_path("data/data/local_sample/slice_629p/slice_report.json"), \
        "المتداخلُ محجوب — وهو موضعُ العلّة نفسُه"
    assert pg.real_data_path("a/b/data/eval_pack/x.json"), "العمقُ مهما كان لا يُعفي"
    assert not pg.real_data_path("data/sample/statement_sample.pdf"), \
        "اللقطةُ المسموحةُ في المستودع تبقى مسموحة (ضبطٌ موجب)"
    assert not pg.real_data_path("docs/data/local_sample.md"), \
        "اسمٌ يشبه المجلّدَ في مسارٍ آخر ليس بياناتٍ حقيقيّة (ضبطٌ موجب ثانٍ)"


def test_the_ignore_rules_are_depth_agnostic_too():
    """**خطُّ الدفاع الأول، بالصنف نفسه (مراجعة ٦٧):** كان `.gitignore` جذريًّا، فقِيس أنّ
    `git check-ignore data/data/local_sample/x.json` ⇒ **`rc=1`** (غيرُ محجوب) بينما الجذريُّ محجوب ⇒
    فالمتداخلُ يصير مرشَّحًا لـ`git add .` قبل أن يراه الحارس. فالمقابلةُ الآن على أيّ عمقٍ تحت `data/`.
    """
    import subprocess

    root = Path(__file__).resolve().parents[1]

    def ignored(rel: str) -> bool:
        return subprocess.run(["git", "check-ignore", "-q", rel], cwd=root).returncode == 0

    assert ignored("data/local_sample/x.json"), "الجذريُّ محجوب"
    assert ignored("data/data/local_sample/x.json"), "المتداخلُ محجوب — وهو موضعُ العلّة"
    assert ignored("data/eval_pack/amount-manifest.json"), "خريطةُ التطهير محجوبة"
    assert not ignored("data/sample/statement_sample.pdf"), \
        "اللقطةُ المسموحةُ تبقى غيرَ محجوبة (ضبطٌ موجب)"


def test_the_ci_step_and_the_guard_share_one_rule():
    """**مالكٌ واحد للقاعدة (مراجعة ٦٧):** كانت خطوةُ الـCI تحمل نمطًا جذريًّا خاصًّا بها ⇒ فالنسخةُ
    المتداخلةُ تفلت من الاثنين معًا. فلا يُعاد النمطُ الثاني، والخطوةُ تستدعي قاعدةَ الحارس.

    **ويُقاس الواقعُ لا النصّ (مقعدُ البنية · جولة ٦٧):** كان الفحصُ يبحث عن الاسم في الملفّ كلِّه
    ⇒ يمرّ لو صار السطرُ `echo "…"` (سلبيّةٌ كاذبة)، ويسقط لو ذُكر النمطُ القديم في **تعليق**
    (إيجابيّةٌ كاذبة). فالمقيسُ الآن: **سطرُ `run:` نفسُه** هو الاستدعاء، ولا سطرَ **فاعلًا** يحمل النمط.
    """
    root = Path(__file__).resolve().parents[1]
    wf = (root / ".github" / "workflows" / "publish-guard.yml").read_text(encoding="utf-8")
    stripped = [ln.strip() for ln in wf.splitlines()]
    calls = [ln for ln in stripped
             if ln.startswith("run:") and "publish_guard.py --tracked-real-data" in ln]
    assert calls == ["run: python3 tools/publish_guard.py --tracked-real-data"], \
        f"خطوةُ الـCI تستدعي قاعدةَ الحارس نفسَها (وُجد: {calls})"
    effective = [ln for ln in stripped if not ln.startswith("#")]
    assert not any("^data/(local_sample" in ln for ln in effective), \
        "نمطٌ جذريٌّ فاعلٌ آخر — الشرحُ في تعليقٍ لا يُحسب، والتنفيذُ يُحسب"


def test_a_non_ascii_path_cannot_hide_from_the_guard(tmp_path):
    """**ثقبٌ مقيسٌ في إغلاق R67-1 نفسه (مقعدُ المواصفة · جولة ٦٧):** `core.quotePath` يقوّس كلَّ
    مسارٍ فيه محرفٌ غيرُ ASCII (`"data/training/\\331\\203…"`) ⇒ فمقابلةُ مقاطع المسار تفشل و**يُفلت
    الملفُّ**: قِيس أنّ `data/training/كشوف/عميل.json` المُتتبَّع أعطى «0 تحت مجلّدات البيانات
    الحقيقيّة» و`rc=0` — أي أنّ الخطوةَ التي أُضيفت لسدّ R67-1 كانت هي التي تمرّ منه. والعلاجُ `_git_z`
    (`-z`: بلا تقويسٍ ولا فاصلٍ يمكن أن يظهر في اسم ملفّ).

    **ويُقاس على نسخةٍ حقيقيّةٍ صغيرة** (تُشغَّل الأداةُ فيها) لا بمحاكاةٍ — فالأداةُ تقرأ `ROOT` من
    موقعها.
    """
    import shutil
    import subprocess
    import sys as _sys

    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    shutil.copy(Path(__file__).resolve().parents[1] / "tools" / "publish_guard.py", root / "tools")
    for cmd in (["git", "init", "-q"],
                ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=root, check=True)
    leak = root / "data" / "training" / "كشوف"
    leak.mkdir(parents=True)
    (leak / "عميل-1439.json").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "-f", "data/training/كشوف/عميل-1439.json"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "leak"], cwd=root, check=True)

    r = subprocess.run([_sys.executable, "tools/publish_guard.py", "--tracked-real-data"],
                       cwd=root, capture_output=True, text=True)
    assert r.returncode == 1, (
        f"مسارٌ غيرُ ASCII تحت مجلّد بياناتٍ حقيقيّةٍ لم يُكشَف (rc={r.returncode})\n{r.stdout}")
    assert "كشوف" in r.stdout, "والرسالةُ تسمّي المسارَ نفسَه (القراءةُ بلا تقويس)"


def test_a_leak_that_lives_only_in_history_is_caught(tmp_path):
    """**مراجعة ٦٨ · R68-1 — الضابطُ الذي كان غائبًا سببَ العطل:** لا اختبارَ كان يفحص مسحَ
    التاريخ، فمرّ عطلٌ **صامت** أوقف نصفَ الحارس: `rev-list --objects --all -z` يُخرج **سجلّاتٍ**
    (`<sha>\\0<sha>\\0path=<المسار>\\0`) لا أسطرًا بفراغ ⇒ فقارئٌ يفصل على الفراغ يقرأ **صفرَ كائن**،
    ويُخرج «نظيف» وهو لم يقرأ شيئًا (قِيس في الشجرة: `history: 0 · 0 BLOCK · rc=0`).
    **والضابطُ يزرع تسريبًا في التاريخ وحدَه** (مسارُ منزلٍ وهميّ يُضاف ثم يُحذَف في التزامٍ تالٍ).
    """
    import shutil
    import subprocess
    import sys

    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    shutil.copy(Path(__file__).resolve().parents[1] / "tools" / "publish_guard.py", root / "tools")

    def g(*a):
        return subprocess.run(["git", *a], cwd=root, capture_output=True, text=True)

    g("init", "-q", ".")
    g("config", "user.email", "t@example.invalid")
    g("config", "user.name", "t")
    note = root / "notes.md"
    note.write_text("workdir: /Users/" + "auditor" + "/secret/project\n", encoding="utf-8")
    g("add", "-A")
    g("commit", "-qm", "add")
    note.unlink()
    g("add", "-A")
    g("commit", "-qm", "remove")

    r = subprocess.run([sys.executable, "tools/publish_guard.py", "--history"],
                       cwd=root, capture_output=True, text=True)
    assert "history: 0" not in r.stdout, (
        "القارئُ لم يقرأ التاريخَ أصلًا — صيغةُ `-z` تغيّرت أو عاد الفصلُ على الفراغ:\n" + r.stdout)
    assert r.returncode == 1, f"تسريبٌ في التاريخ (وحده) يجب أن يُحجب (rc={r.returncode})\n{r.stdout}"
    assert "BLOCK" in r.stdout, "ويكون الحكمُ حجبًا لا تحذيرًا:\n" + r.stdout


def test_a_failed_git_read_is_not_an_empty_read():
    """**R68-1:** كانت `_git_z` تُعيد المخرَجَ بلا فحصِ رمزِ الخروج ⇒ فأمرٌ فاشلٌ يُقرأ «قائمةً
    فارغةً» = «نظيفًا». والآن يرفع `GitReadError` (ورمزُ الخروج ٢: تعذّرُ قياسٍ لا وجودُ محجوب)."""
    import publish_guard as pg
    with pytest.raises(pg.GitReadError):
        pg._git_z("rev-list", "--definitely-not-a-git-flag-068")


def test_the_history_reader_judges_by_shape_not_by_zero(monkeypatch):
    """**R68-1 على الخام + مقعدا البنية والمواصفة (جولة ٦٨ب): الحكمُ على **شكل** ما قُرئ.**

    - سجلّاتٌ فارغة ⇒ **مشروع** (مستودعٌ بلا التزاماتٍ ⇒ لا تاريخَ يُمسح) — لا صرخة.
    - معرّفاتٌ وحدَها بلا كائنٍ مسمّى ⇒ **مشروع** (تاريخٌ بالتزامٍ فارغ) — لا صرخة.
    - `path=` **بلا معرّفٍ يسبقه** ⇒ بنيةٌ لا تُفهَم ⇒ استثناء (وهو ما فات في R68-1: أُقرئ الصفرُ نظافةً).
    - وسجلٌّ لا معرّفَ ولا `path=` ⇒ الصيغةُ تغيّرت ⇒ استثناء (ضابطُه المستقلّ: `…changed_history_format…`).
    """
    import publish_guard as pg

    monkeypatch.setattr(pg, "_git_z", lambda *a, **k: [])
    assert pg._history_pairs() == []

    monkeypatch.setattr(pg, "_git_z", lambda *a, **k: ["a" * 40, "b" * 40])
    assert pg._history_pairs() == []

    monkeypatch.setattr(pg, "_git_z", lambda *a, **k: ["path=x", "a" * 40])
    with pytest.raises(pg.GitReadError):
        pg._history_pairs()


def test_every_git_reader_refuses_a_failed_read():
    """**قارئٌ واحد للسياسة (مقعدا المعايير والبنية · جولة ٦٨):** كانت `_git` تُعيد `''` على أمرٍ
    فاشل بينما `_git_z` ترفع ⇒ فبقيت أنصافُ المسح (الرسائل · `pre-push`) تعود «نظيفةً صامتة».
    و`_git` تحمل قراءةَ الرسائل و`rev-list` في مسار الدفع، أي المسار الذي **يوقف دفعَ المالك**.
    """
    import publish_guard as pg
    for reader in (pg._git, pg._git_z):
        with pytest.raises(pg.GitReadError):
            reader("rev-list", "--definitely-not-a-git-flag-068")


def test_the_tracked_data_step_declares_a_failed_read_like_the_history_step(tmp_path):
    """**الفرعُ الذي هو خطوةُ CI بنفسه (مقعدُ البنية P1 · مقعدُ المواصفة P2 · جولة ٦٨):**
    كان `_git_z("ls-files")` **خارج** حدّ الاستثناء ⇒ خطأُ git يُخرج أثرًا (traceback) برمز ١، ورمزُ
    ٢ المُعلَن في `docs/GATES.md` لا يصله. فالمقيسُ هنا: **رمز ٢ · رسالةٌ معلَنة · بلا أثر.**
    """
    import shutil
    import subprocess
    import sys

    root = tmp_path / "not-a-repo"
    (root / "tools").mkdir(parents=True)
    shutil.copy(Path(__file__).resolve().parents[1] / "tools" / "publish_guard.py", root / "tools")
    r = subprocess.run([sys.executable, "tools/publish_guard.py", "--tracked-real-data"],
                       cwd=root, capture_output=True, text=True)
    assert r.returncode == 2, f"تعذّرُ القراءة ⇒ ٢ (لا حكم) لا ١ ولا أثرًا (rc={r.returncode})"
    assert "Traceback" not in r.stderr + r.stdout, "ولا يُسرَّب أثرُ الاستثناء:\n" + r.stderr
    assert "لا حكم" in r.stdout, "والرسالةُ تُعلن أنّها لا تحكم:\n" + r.stdout

    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    r2 = subprocess.run([sys.executable, "tools/publish_guard.py", "--tracked-real-data"],
                        cwd=root, capture_output=True, text=True)
    # **وصفرُ الملفّاتِ المُتتبَّعة حالةٌ مشروعة (تصحيحٌ في الجولة ٦٨ب):** عدتُها كانت تُخرج رمز ٢
    # عليها بينما تاريخُ المستودع نفسِه «آمن» برمز ٠ ⇒ تناقضٌ وصرخةٌ كاذبة. فالمقياسُ الصادق:
    # `ls-files` تُخرج صفرًا برمز ٠ لحالةٍ فارغةٍ حقيقةً، والقراءةُ التي لم تقع يرفعها `_run_git`.
    assert r2.returncode == 0, (
        f"مستودعٌ بلا ملفٍّ مُتتبَّع واحد: «لا ملفَّ بياناتٍ حقيقيّة» حكمٌ صادقٌ لا «تعذّرُ قياس» "
        f"(rc={r2.returncode})\n{r2.stdout}")


def test_the_count_hint_lives_in_both_ci_steps():
    """**السنُّ الذي يُفشل خطوةَ اللقطة بلا ضابطٍ كان يُمحى بصمت (مقعدُ المواصفة P3 · جولة ٦٨):**
    `render_claims --write` ثم `git diff --exit-code` هو ما يكشف انزياحَ قياسِ البيئة **بعد** أن صار
    `--check` يُقابِل الملفَّ الذي كتبته الخطوةُ نفسُها ⇒ فحذفُ السطرين يُبقي كلَّ شيءٍ أخضرَ ويعود
    الانزياحُ صامتًا (وهو صنفُ R68-1 نفسه).
    """
    wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows"
          / "publish-guard.yml").read_text(encoding="utf-8")
    assert wf.count("render_claims.py --write") == 2, (
        "الخطّافُ في الخطوتين معًا (المجموعة واللقطة) — لا في واحدة")
    assert wf.count("git diff --exit-code -- docs/claims.json") == 2, (
        "والفرقُ الفاشلُ في الخطوتين معًا")


def test_the_guard_and_the_ignore_rules_share_one_list_of_real_data_dirs():
    """**لا قائمتان تفترقان (مقعدُ البنية · جولة ٦٧):** `.gitignore` يحمل أسماءَ مجلّدات البيانات
    الحقيقيّة بيده، و`publish_guard` في `REAL_DATA_DIRS` ⇒ فزيادةُ مجلّدٍ في أحدهما لا يتبعها الآخر،
    ويعود الدرسُ نفسُه (خطّا دفاعٍ يفترقان). فيُقابَلان — وبالصيغة العميقة (`**/`) التي بها التداخلُ
    لا يُعفي.
    """
    import publish_guard as pg

    gi = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(encoding="utf-8")
    for d in pg.REAL_DATA_DIRS:
        assert f"**/{d}/" in gi, (
            f"`{d}` في `REAL_DATA_DIRS` وليس في `.gitignore` بصيغته العميقة ⇒ يفترق خطّا الدفاع")


def test_a_three_wide_space_grouped_account_is_blocked():
    """**الثغرة التي فتحها توسيعي ثم أُغلق.** مدقّقٌ خارجي قاس أن حساباً من 15 أو
    18 رقماً مكتوباً بثلاثاتٍ مفصولةٍ بفراغ كان **يمرّ**، لأنني وسّعتُ القاعدة
    ليُقبل ملفٌّ واحد. والاختبارات الثلاثة السابقة كانت تغطّي الحالات **الآمنة**
    وحدها — فلا يسمّم أحدٌ الحالةَ التي يفتحها استثناؤه. هذا هو السمّ الغائب."""
    line = ' "account": "' + " ".join(_run(str(n), 3) for n in range(1, 6)) + '"'
    findings = [r for r in _scan_one(line) if r[1] == "long_digits"]
    assert findings, "حسابٌ بثلاثاتٍ مفصولةٍ بفراغ يجب أن يُحجب (ثغرةٌ كانت مفتوحة)"


def test_the_tool_reaches_git_through_one_core_only():
    """**«قارئٌ واحد» تُقاس بالنصّ لا بالوعد (مقعدا المعايير والبنية · الجولة ٦٨ب).**

    كلُّ قراءةٍ من git في الحارس تمرّ على `_run_git` (التي تفحص رمزَ الخروج وترفع `GitReadError`).
    فظهورُ نداءٍ ثانٍ مباشر يعني **سياسةً ثانية**: قراءةٌ فاشلةٌ تُقرأ «صفرًا» = «نظيفًا».
    (والقياسُ الذي أنتج هذا الضابط: `_read_blobs` — وهي التي تُنزل محتوى الكائنات، أي موضعُ الحكم
    نفسُه — كانت القراءةَ **الرابعة** بلا فحصِ رمز خروج.)
    """
    src = Path(pg.__file__).read_text("utf-8")
    assert src.count('subprocess.run(["git"') == 1, "قراءةُ git خارج النواة `_run_git`"
    assert src.count("_run_git(") >= 4, "نواةُ القراءة لا يستهلكها كلُّ المسارات"


def _tool_repo(tmp_path, name="repo"):
    """مستودعٌ مؤقّتٌ يحمل **نسخةً من الأداة** ⇒ فـ`ROOT` عندها هو هذا المستودع (لا مستودع المشروع)."""
    repo = tmp_path / name
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "tools").mkdir(exist_ok=True)
    (repo / "tools" / "publish_guard.py").write_text(Path(pg.__file__).read_text("utf-8"), "utf-8")
    return repo


def _git_init_commit(repo, files=("ok.txt",), allow_empty=False):
    subprocess.run(["git", "init", "-q", "."], cwd=repo, check=True)
    for f in files:
        (repo / f).write_text("nothing sensitive here\n", "utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    cmd = ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"]
    if allow_empty:
        cmd.insert(6, "--allow-empty")
    subprocess.run(cmd, cwd=repo, check=True)


def _run_tool(repo, *args):
    return subprocess.run([sys.executable, "tools/publish_guard.py", *args],
                          cwd=repo, capture_output=True, text=True)


def test_a_missing_blob_object_is_not_silent_cleanliness(tmp_path):
    """**T1 / P1 / S1 — المقاعدُ الثلاثة تقاربت على هذا (الجولة ٦٨ب).**

    حذفُ جسم كائنٍ من مخزن git يُخرج `cat-file --batch` سطرَ `… missing` **برمز خروجٍ صفر** ⇒ فحصُ
    الرمز وحدَه لا يكشفه؛ وكان المستهلكُ يُسقط الغائبَ بصمت (`data is None ⇒ continue`) ⇒ فتسريبٌ
    مزروعٌ يمرّ من حارسِ النشر العامّ. قِيس عند المقاعد: قبل `1 BLOCK · rc=1`، وبعدُ `0 BLOCK` و
    «آمن للدفع» بـ`rc=0`. المطلوب: **«لا حكم»** — لا نظافة.
    """
    repo = _tool_repo(tmp_path)
    _git_init_commit(repo, files=("leak.txt",))
    # تسريبٌ يُبنى في زمن التشغيل: **لا مسارَ بيتٍ ولا سلسلةَ أرقامٍ في نصّ هذا الملفّ** (يُفحَص بحارسِه).
    (repo / "leak.txt").write_text("workdir: /Users/" + "auditor" + "/secret/project\n", "utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "leak"],
                   cwd=repo, check=True)
    before = _run_tool(repo, "--tree")
    assert before.returncode == 1 and "BLOCK" in before.stdout, before.stdout
    blob = subprocess.run(["git", "rev-parse", "HEAD:leak.txt"], cwd=repo,
                          capture_output=True, text=True).stdout.strip()
    (repo / ".git" / "objects" / blob[:2] / blob[2:]).unlink()
    after = _run_tool(repo, "--tree")
    assert after.returncode == 2, after.stdout + after.stderr
    assert "آمن للدفع" not in after.stdout, after.stdout
    assert "لا حكم" in after.stdout, after.stdout


def test_an_empty_tree_commit_is_not_a_measurement_failure(tmp_path):
    """**T2 / S2 / P4 — صرخةٌ كاذبةٌ أدخلتُها في الطلب نفسِه ثم قاسها المقاعد.***

    التزامٌ بشجرةٍ فارغة حالةٌ مشروعة (`git ls-tree -r HEAD` ⇒ صفرٌ بـ`rc=0`)، وكان شرطُ «صفرِ مدخل»
    يُخرجه «تعذّرَ قياس» برمز ٢ بينما `--history` على المستودع نفسِه يقول «آمن» برمز ٠ — حكمان
    متناقضان. والأثقلُ أنّ `scan_pre_push` يعبر `scan_tree` ⇒ فيُمنع دفعٌ مشروع (وهو ما يمنعه الخطّافُ
    بنصّه). المطلوب: صفرٌ صادق ⇒ `tree: 0` و«آمن للدفع» و`rc=0`.
    """
    repo = tmp_path / "empty"
    repo.mkdir()
    _git_init_commit(repo, files=(), allow_empty=True)
    # الأداةُ تُنسخ **بعد** الالتزام ⇒ فشجرةُ `HEAD` تبقى فارغةً فعلًا (‏`ls-tree` ⇒ صفر).
    (repo / "tools").mkdir()
    (repo / "tools" / "publish_guard.py").write_text(Path(pg.__file__).read_text("utf-8"), "utf-8")
    tree = _run_tool(repo, "--tree")
    assert tree.returncode == 0, tree.stdout + tree.stderr
    assert "tree: 0" in tree.stdout, tree.stdout
    assert "آمن للدفع" in tree.stdout, tree.stdout
    hist = _run_tool(repo, "--history")
    assert hist.returncode == 0, hist.stdout + hist.stderr
    tracked = _run_tool(repo, "--tracked-real-data")
    assert tracked.returncode == 0, tracked.stdout + tracked.stderr


def test_a_changed_history_format_is_a_failure_not_zero_pairs(monkeypatch):
    """**P2 (مقعدُ المواصفة · ٦٨ب) + R68-1 على الخام:** تغييرٌ في صيغة git يُبقي السجلّاتِ غيرَ فارغةٍ
    ويسقط `path=` ⇒ كان يُقرأ «صفرَ أزواج» ثم «آمن للدفع» (آلافُ الكائنات تُتخطّى بصمت — صنفُ R68-1
    بعينه). والحكمُ على **شكلِ** كلّ سجلّ: معرّفُ كائنٍ أو `path=<مسار>` يتبعه ⇒ ولا ثالث.
    ويقيس الضابطُ الاتجاهين: سجلٌّ غريبٌ ⇒ استثناء · وسجلّاتٌ معرّفاتٌ وحدَها (تاريخٌ مشروعٌ بلا كائنٍ
    مسمّى) ⇒ أزواجٌ صفرٌ بلا استثناء (لا صرخةٌ كاذبة).
    """
    import publish_guard as pg
    monkeypatch.setattr(pg, "_git_z",
                        lambda *a, **k: ["a" * 40, "src/app.py", "b" * 40, "docs/GATES.md"])
    with pytest.raises(pg.GitReadError):
        pg._history_pairs()
    monkeypatch.setattr(pg, "_git_z", lambda *a, **k: ["a" * 40, "b" * 40])
    assert pg._history_pairs() == []


def test_a_remote_ref_absent_locally_does_not_block_a_push(tmp_path, monkeypatch, capsys):
    """**T3 (مقعدُ البنية · ٦٨ب):** مرجعٌ على الريموت لم يُجلَب (فرعٌ أُنشئ عليه · تاريخٌ أُعيد كتابتُه
    وجُلب ناقصًا) كان يُخرج رمزَ ٢ ⇒ والخطّافُ `|| exit 1` **يمنع دفعًا مشروعًا** — وهو ما يمنعه
    `.githooks/pre-push` بنصّه. المطلوب: يُعلَن المرجعُ ويُمسح ما هو موجودٌ محليًّا (بلا استثناء).
    """
    import io
    import publish_guard as pg
    repo = tmp_path / "push"
    repo.mkdir()
    _git_init_commit(repo)
    local = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                           capture_output=True, text=True).stdout.strip()
    monkeypatch.setattr(pg, "ROOT", repo)
    monkeypatch.setattr("sys.stdin", io.StringIO(
        f"refs/heads/feature {local} refs/heads/feature {'1' * 40}\n"))
    findings, entries, seen = [], [], set()
    pg.scan_pre_push(findings, entries, seen)          # لا استثناء ⇒ لا «لا حكم» على دفعٍ مشروع
    out = capsys.readouterr().out
    assert "غيرُ موجودٍ محليًّا" in out, out
    assert not [f for f in findings if f[0] == "BLOCK"], findings
