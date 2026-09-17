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

# Invented pieces, joined at runtime. Deliberately no literal concatenation.
_PARTS = ("990000", "1199")
_PARTS_AR = ("٩٩٩٩٠٠", "٠٠١١")
FAKE_ACCOUNT = "".join(_PARTS)
FAKE_ACCOUNT_AR = "".join(_PARTS_AR)
FAKE_IBAN_GROUPS = ["9900", "0011", "9900", "0011"]


def _scan(text: str) -> list[tuple]:
    findings: list[tuple] = []
    pg._scan_text("tests/probe.py", text, "tree", findings, [])
    return findings


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
