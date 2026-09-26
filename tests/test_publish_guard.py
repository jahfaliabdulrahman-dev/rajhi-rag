"""Publish guard tests — the dedup bug, the digit-table exemption, and the
four structural holes an external audit opened are regressions; lock them
here. No git operations.

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
    """
    root = Path(__file__).resolve().parents[1]
    wf = (root / ".github" / "workflows" / "publish-guard.yml").read_text(encoding="utf-8")
    assert "publish_guard.py --tracked-real-data" in wf, \
        "خطوةُ الـCI تستدعي قاعدةَ الحارس نفسَها (مالكٌ واحد)"
    assert "grep -E '^data/(local_sample" not in wf, \
        "النمطُ الجذريُّ المكرَّر أُزيل — وإلّا عاد التداخلُ فمرّ (الشرحُ يبقى، والنمطُ لا)"


def test_a_three_wide_space_grouped_account_is_blocked():
    """**الثغرة التي فتحها توسيعي ثم أُغلق.** مدقّقٌ خارجي قاس أن حساباً من 15 أو
    18 رقماً مكتوباً بثلاثاتٍ مفصولةٍ بفراغ كان **يمرّ**، لأنني وسّعتُ القاعدة
    ليُقبل ملفٌّ واحد. والاختبارات الثلاثة السابقة كانت تغطّي الحالات **الآمنة**
    وحدها — فلا يسمّم أحدٌ الحالةَ التي يفتحها استثناؤه. هذا هو السمّ الغائب."""
    line = ' "account": "' + " ".join(_run(str(n), 3) for n in range(1, 6)) + '"'
    findings = [r for r in _scan_one(line) if r[1] == "long_digits"]
    assert findings, "حسابٌ بثلاثاتٍ مفصولةٍ بفراغ يجب أن يُحجب (ثغرةٌ كانت مفتوحة)"
