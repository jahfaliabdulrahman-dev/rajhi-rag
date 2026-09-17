"""Tests for tools/static_gate.py — a gate that never bit is decoration.

Every case runs the gate as a subprocess over a throwaway tree, so what is under
test is the real exit code and the real report, not an imported helper.
`pyflakes` is the engine the gate runs on; when it is missing (a bare CI runner
before the install step) these tests skip rather than lie.

No network, no API key, no project data.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parents[1]
GATE = PROJ / "tools" / "static_gate.py"

pytest.importorskip("pyflakes", reason="gate engine not installed in this interpreter")


def run_gate(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GATE), str(root)],
                          capture_output=True, text=True, timeout=60)


def test_clean_tree_passes(tmp_path):
    (tmp_path / "clean.py").write_text(
        "import json\n\n\ndef f(a):\n    return json.dumps({'a': a})\n",
        encoding="utf-8")
    done = run_gate(tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "findings: 0" in done.stdout
    assert "PASS" in done.stdout


def test_undefined_name_blocks(tmp_path):
    """The class that killed a paid run: a name that never resolves."""
    (tmp_path / "broken.py").write_text("def f():\n    return footer_checks\n",
                                        encoding="utf-8")
    done = run_gate(tmp_path)
    assert done.returncode == 1, done.stdout
    assert "undefined name 'footer_checks'" in done.stdout
    assert "BLOCK" in done.stdout


def test_dead_binding_and_unused_import_block(tmp_path):
    (tmp_path / "dead.py").write_text(
        "import os\n\n\ndef f():\n    prev = 1\n    return 2\n", encoding="utf-8")
    done = run_gate(tmp_path)
    assert done.returncode == 1
    assert "findings: 2" in done.stdout


def test_noqa_suppresses_but_stays_visible(tmp_path):
    """Suppression must count as suppressed, print the line, and not vanish."""
    (tmp_path / "kept.py").write_text(
        "import os  # noqa: F401  (imported for its side effect)\n",
        encoding="utf-8")
    done = run_gate(tmp_path)
    assert done.returncode == 0, done.stdout
    assert "suppressed: 1" in done.stdout
    assert "kept.py:1" in done.stdout          # the suppressed line is named
    assert "NOQA" in done.stdout


def test_noqa_does_not_swallow_a_real_error(tmp_path):
    """`# noqa` on another line must not hide an undefined name."""
    (tmp_path / "mixed.py").write_text(
        "import os  # noqa: F401\n\n\ndef f():\n    return missing_thing\n",
        encoding="utf-8")
    done = run_gate(tmp_path)
    assert done.returncode == 1
    assert "missing_thing" in done.stdout
    assert "suppressed: 1" in done.stdout


def test_noqa_inside_a_string_is_not_a_suppression(tmp_path):
    """A real hole an external audit drove through: the marker must be a comment.

    `x = "# noqa"  # os-unused` — the string looked like a waiver to a raw regex,
    so a genuine finding on that line disappeared. Read the tokenizer instead.
    """
    p = tmp_path / "string_noqa.py"
    p.write_text('# a line nobody waives\nimport os\nx = "# noqa"\n',
                 encoding="utf-8")
    done = run_gate(tmp_path)
    assert done.returncode == 1, done.stdout
    assert "imported but unused" in done.stdout
    assert "suppressed: 0" in done.stdout


def test_noqa_on_the_same_line_as_a_string_still_works_as_a_comment(tmp_path):
    """The named legitimate case must keep working: a waiver is a comment."""
    (tmp_path / "waived.py").write_text(
        'import os  # noqa: F401 — مطلوب لجانبه\n', encoding="utf-8")
    done = run_gate(tmp_path)
    assert done.returncode == 0, done.stdout
    assert "suppressed: 1" in done.stdout


def test_dot_directories_are_scanned_too(tmp_path):
    """`.github/` is where a CI helper script lives — the gate must see it."""
    (tmp_path / ".github" / "scripts").mkdir(parents=True)
    (tmp_path / ".github" / "scripts" / "helper.py").write_text(
        "def f():\n    return never_defined\n", encoding="utf-8")
    done = run_gate(tmp_path)
    assert done.returncode == 1, done.stdout
    assert "helper.py" in done.stdout and "never_defined" in done.stdout


def test_syntax_error_blocks(tmp_path):
    (tmp_path / "bad_syntax.py").write_text("def f(:\n    pass\n",
                                            encoding="utf-8")
    done = run_gate(tmp_path)
    assert done.returncode == 1
    assert "syntax error" in done.stdout


def test_hidden_and_venv_dirs_are_skipped(tmp_path):
    """A vendored copy inside the tree must not change the verdict."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    for junk in (".venv/lib", ".claude/worktrees/x", "__pycache__"):
        d = tmp_path / junk
        d.mkdir(parents=True)
        (d / "junk.py").write_text("def f():\n    return never_defined\n",
                                   encoding="utf-8")
    done = run_gate(tmp_path)
    assert done.returncode == 0, done.stdout
    assert "files: 1" in done.stdout
