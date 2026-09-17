"""Every tracked Python file must at least parse.

A syntax error reached a pushed commit in `tools/qa_gate.py`, because nothing
in the suite imports or compiles it: CI runs the publish guard, and the suite
covers `src/` and `tests/`. The cheapest possible guard against that class is
to compile everything tracked — one second, no dependencies, catches the whole
family at once (it is the same hole the audit named as «zero tests import
app.py», closed at the shallow end first).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_tracked_python_file_compiles():
    files = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT,
                           capture_output=True, text=True).stdout.split()
    assert files, "no tracked python files found — is this a git worktree?"
    bad = []
    for rel in files:
        try:
            compile((ROOT / rel).read_text(encoding="utf-8"), rel, "exec")
        except SyntaxError as exc:
            bad.append(f"{rel}:{exc.lineno}: {exc.msg}")
    assert bad == [], bad
