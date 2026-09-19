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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


LIGHT_TOOLS = ("health_monitor", "health_check", "publish_guard",
               "verify_provenance", "arbitrate_footer", "refusal_test")


def _app_stack_available() -> bool:
    """Can the application stack import on this machine at all?

    CI installs pytest and nothing else — no pdfplumber, no torch — so the
    import check is a LOCAL gate, and it says so instead of failing there. The
    compile test above still runs everywhere: it needs no dependency at all.

    **The probe checks the heavy dependencies themselves, not `import
    statement_qa`.** The package became lazy (PEP 562), so a light environment
    imports it successfully while the tools under test still need pdfplumber,
    PIL and langchain — and a probe on the package would open this gate in the
    one place it must stay shut (measured: the light suite went red with
    `No module named 'PIL'` the moment that happened).
    """
    import importlib.util

    heavy = ("pdfplumber", "PIL", "langchain")
    if not all(importlib.util.find_spec(mod) is not None for mod in heavy):
        return False
    try:
        import statement_qa  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def test_every_tracked_python_file_imports_cleanly():
    """Compiling is not enough: a module-level NameError compiles fine and dies
    the moment the tool runs — which is how a missing `import re` reached the
    refusal test (found by RUNNING it, not by the suite). The tools here are the
    light, side-effect-free ones; importing them is the cheapest way to catch
    that whole class.
    """
    import importlib

    import pytest

    if not _app_stack_available():
        pytest.skip("حزمة التطبيق غير مثبّتة هنا (CI خفيف) — فحص محلي فقط")
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tools"))
    broken = []
    for name in LIGHT_TOOLS:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001
            broken.append(f"{name}: {type(exc).__name__}: {exc}")
    assert broken == [], broken


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
