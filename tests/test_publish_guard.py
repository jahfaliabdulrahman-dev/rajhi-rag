"""Publish guard tests — the dedup bug and the digit-table exemption are
regressions that were caught live; lock them here. No git operations."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import publish_guard as pg  # noqa: E402


def test_digit_table_ramp_is_exempt_from_long_digits():
    assert pg._is_digit_table("٠١٢٣٤٥٦٧٨٩")
    assert pg._is_digit_table("01234567890123456789")
    assert pg._is_digit_table("۱۲۳۴۵۶۷۸۹۰")
    assert not pg._is_digit_table("١٠٠٥٧٦١")   # a real-looking account run
    assert not pg._is_digit_table("10000001")


def test_long_digit_rule_flags_account_like_runs():
    rid, sev, rx, _ = [r for r in pg.TEXT_RULES if r[0] == "long_digits"][0]
    m = rx.search("FRACCT/1005761FR")
    assert m and not pg._is_digit_table(m.group(0))
    assert rx.search("٣٠٠,٠٠") is None


def test_snippet_masks_long_digit_runs():
    out = pg._snippet("balance 1005761 riyals")
    assert "0001199" not in out and "99…" in out


def test_allowlist_parsing_skips_comments(tmp_path, monkeypatch):
    f = tmp_path / ".publish-allowlist"
    f.write_text("# comment\nname_token :: tools/* :: reason\nbadline\n",
                 encoding="utf-8")
    monkeypatch.setattr(pg, "ROOT", tmp_path)
    entries = pg.load_allowlist()
    assert entries == [("name_token", "tools/*")]
    assert pg._allowed(entries, "name_token", "tools/x.py")
    assert not pg._allowed(entries, "home_path", "tools/x.py")
