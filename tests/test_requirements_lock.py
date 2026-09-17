"""The lock file must cover everything the loose requirements ask for.

`requirements.txt` says what may be installed; `requirements.lock` records what
WAS installed when the measured numbers were produced (audit P2-11). Without a
check, a new dependency can be added to one and not the other and nobody
notices until a fresh install produces a different application.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _names(text: str) -> set[str]:
    out = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _NAME.match(line)
        if m:
            out.add(m.group(1).lower().replace("_", "-"))
    return out


def test_every_requirement_is_pinned_in_the_lock():
    req = _names((ROOT / "requirements.txt").read_text(encoding="utf-8"))
    lock_text = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    lock = _names(lock_text)
    assert req, "requirements.txt parsed empty"
    missing = sorted(req - lock)
    assert missing == [], f"غير مقفلة في requirements.lock: {missing}"


def test_lock_pins_exact_versions():
    lock_text = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    pinned = [l for l in lock_text.splitlines()
              if l.strip() and not l.strip().startswith("#")]
    assert pinned, "the lock file is empty"
    loose = [l for l in pinned if "==" not in l]
    assert loose == [], f"أسطر بلا تثبيت دقيق: {loose[:5]}"
