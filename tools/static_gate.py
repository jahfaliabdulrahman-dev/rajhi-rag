#!/usr/bin/env python3
"""static-gate — pyflakes over every Python file in the tree, suppressions visible.

WHY THIS EXISTS (an incident, not a preference)
-----------------------------------------------
A *paid* run of `tools/scale_slice.py` used a name that was never defined
anywhere in the tree: the run spent the full API cost and then died with
`NameError` before it could write its report. The 185-test suite never saw it,
because no test exercises the paid branch — pytest only proves what some test
actually executes. A linter reads the code instead: it sees that whole class
without spending a cent.

One undefined name is not one bug, it is one *class* of bug: fixing the site you
happened to crash in while leaving its siblings alive is guessing, not proving.
This gate is what turns "I fixed the crash" into "there is no other one".

WHAT IT CATCHES
  · undefined names        · dead bindings (assigned, never read)
  · unused imports         · f-strings with no placeholders
WHAT IT CANNOT CATCH (never claim otherwise)
  · logic: a wrong comparison, a threshold off by one, inverted math, leakage
  · anything that needs execution: only a test or a real run can prove that
  → It complements pytest and the published-surface guard. It replaces neither.

DESIGN RULES
  1. ONE engine: pyflakes. A hand-rolled name resolver would under-report, and a
     gate that under-reports is worse than no gate at all (false confidence is
     the most expensive kind).
  2. STRICT: zero findings is the bar; any finding blocks. The tree is clean, so
     the gate can afford to be absolute — and a strict gate on a clean tree is
     the only kind that stays switched on. There is deliberately no bypass flag.
  3. SUPPRESSION IS VISIBLE: `# noqa` on a finding's line suppresses it, and
     every suppressed finding is still printed with its file:line + reason text,
     so the count is part of the verdict and never a hiding place.
     (`# noqa: CODE` is accepted with the code ignored — pyflakes emits no codes;
     the flake8/ruff spelling is kept so the markers stay portable if the engine
     is ever swapped. pyflakes itself does NOT honour noqa — verified with a
     probe file, not assumed.)
  4. NO SILENT PASS: a missing engine (exit 2) or a syntax/read error (exit 1) is
     a FAILURE. An unrunnable gate must never look green.
  5. WHOLE TREE BY DEFAULT: every `*.py` under the repo root except hidden dirs
     and build/venv dirs. A gate that must be updated whenever a directory is
     added is a gate that eventually leaks.

CI installs the engine pinned (`pyflakes==3.4.0`) so the verdict cannot drift
with a version bump; it stays a dev tool and is intentionally not a runtime
dependency in `requirements.txt`.

Usage:  python tools/static_gate.py [paths…]        # default: the repo root
Exit:   0 = clean · 1 = findings / syntax error · 2 = engine missing
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import pyflakes
    from pyflakes import api as flake_api
    from pyflakes import reporter as flake_reporter
except ImportError:  # the gate must never pass just because it could not run
    print("[static-gate] BLOCK — محرّك الفحص pyflakes غير مثبّت في هذا المفسّر.",
          file=sys.stderr)
    print(f"[static-gate] المفسّر الحالي: {sys.executable}", file=sys.stderr)
    print("[static-gate] الحل: .venv/bin/python tools/static_gate.py "
          "أو: python -m pip install pyflakes==3.4.0", file=sys.stderr)
    sys.exit(2)

ENGINE = f"pyflakes {getattr(pyflakes, '__version__', '?')} " \
         f"(Python {sys.version.split()[0]})"

# Skipped wherever they appear in a path. Hidden dirs (`.venv`, `.git`,
# `.claude`, …) are covered by the `startswith('.')` rule; the rest are explicit.
SKIP_DIRS = {
    "__pycache__", "venv", "env", "build", "dist", "node_modules",
    ".venv", ".git", ".claude", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}
NOQA_RE = re.compile(r"#\s*noqa\b")


class _Collector(flake_reporter.Reporter):
    """Capture pyflakes' findings instead of printing them as they arrive."""

    def __init__(self) -> None:
        super().__init__(sys.stdout, sys.stderr)
        self.findings: list[tuple[str, int, int, str]] = []   # path, line, col, msg
        self.fatal: list[tuple[str, int, str]] = []           # path, line, msg

    def flake(self, message) -> None:
        try:                                   # bare text without "path:line:col:"
            text = message.message % message.message_args
        except Exception:                      # a subclass with a custom __str__
            text = str(message)
        col = (getattr(message, "col", 0) or 0) + 1
        self.findings.append((message.filename, message.lineno, col, text))

    def syntaxError(self, filename, msg, lineno, offset, text) -> None:
        self.fatal.append((filename, max(lineno or 0, 1), f"syntax error: {msg}"))

    def unexpectedError(self, filename, msg) -> None:
        self.fatal.append((filename, 0, f"unexpected error: {msg}"))


def python_files(root: Path) -> list[Path]:
    """Every `*.py` under `root`, skipping hidden/build dirs. Deterministic order."""
    found = []
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(root).parts[:-1]      # the directories only
        if any(part.startswith(".") or part in SKIP_DIRS for part in parts):
            continue
        found.append(path)
    return found


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv[1:]] or [Path(".")]
    files: list[Path] = []
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            files.append(root)
        elif root.is_dir():
            files.extend(python_files(root))
        else:
            print(f"[static-gate] BLOCK — المسار غير موجود: {root}", file=sys.stderr)
            return 1

    findings: list[tuple[str, int, int, str]] = []
    suppressed: list[tuple[str, int, str]] = []
    fatal: list[tuple[str, int, str]] = []

    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            fatal.append((str(path), 0, f"cannot read: {exc}"))
            continue
        lines = source.splitlines()
        collector = _Collector()
        flake_api.check(source, str(path), collector)
        fatal.extend(collector.fatal)
        for name, lineno, col, text in collector.findings:
            current = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
            if NOQA_RE.search(current):
                suppressed.append((name, lineno, text))
            else:
                findings.append((name, lineno, col, text))

    total = len(findings) + len(fatal)
    print(f"[static-gate] files: {len(files)} · findings: {total} "
          f"· suppressed: {len(suppressed)} · engine: {ENGINE}")

    if suppressed:                      # declared, never hidden
        print("[static-gate] مستثنى بوسم noqa (معلن لا مخفي):")
        for name, lineno, text in suppressed:
            print(f"  NOQA  {name}:{lineno}  — {text}")
    for name, lineno, col, text in findings:
        print(f"  BLOCK {name}:{lineno}:{col}  — {text}")
    for name, lineno, text in fatal:
        where = f"{name}:{lineno}" if lineno else name
        print(f"  BLOCK {where}  — {text}")

    if total:
        print("\nالحكم: BLOCK — اسم لا يُحلّ أو ربط لا يُقرأ = صنف يقتل تشغيلاً "
              "مدفوعاً بعد أن يدفع ثمنه. عالجه أو استثنه بـnoqa معلَّلة على السطر.")
        return 1

    print("الحكم: PASS — كل اسم يُحلّ، ولا ربط ميت، ولا استيراد بلا مستعمل.")
    print("حدّ هذا الفحص: لا يرى المنطق ولا الأرقام — البوابة الرقمية والاختبارات "
          "تكملان ما لا يراه.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
