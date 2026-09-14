"""Publish guard tests — the dedup bug and the digit-table exemption are
regressions that were caught live; lock them here. No git operations.

NOTE: this file deliberately contains NO ≥10-digit literal, not even as a
"fake" example: the guard cannot tell a mock from real data, and a guard
with holes in its own tests is worse than none. Account-like strings are
built from parts at runtime.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import publish_guard as pg  # noqa: E402

# Built from parts — nothing that looks like a real account lives in the repo.
FAKE_ACCOUNT = "".join(("990000", "1199"))
FAKE_ACCOUNT_AR = "".join(("٩٩٩٩٠٠", "٠٠١١"))


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
    assert FAKE_ACCOUNT not in out and "11…" in out


def test_allowlist_parsing_skips_comments(tmp_path, monkeypatch):
    f = tmp_path / ".publish-allowlist"
    f.write_text("# comment\nname_token :: tools/* :: reason\nbadline\n",
                 encoding="utf-8")
    monkeypatch.setattr(pg, "ROOT", tmp_path)
    entries = pg.load_allowlist()
    assert entries == [("name_token", "tools/*")]
    assert pg._allowed(entries, "name_token", "tools/x.py")
    assert not pg._allowed(entries, "home_path", "tools/x.py")
