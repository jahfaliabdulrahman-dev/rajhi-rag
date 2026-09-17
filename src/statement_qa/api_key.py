"""One place resolves OPENROUTER_API_KEY — and it is the only place allowed to.

Order, documented because a public repository must not tell a stranger to write
a file that no code reads:

1. the environment variable;
2. a ``.env`` in the repository root — the file both README and
   ``.env.example`` point a newcomer at, now actually loaded;
3. this machine's ``~/.hermes/.env`` — a convenience for the owner, wrapped in
   ``try/except`` so a stranger never sees a home directory in a traceback.

The failure message names the two portable options and nothing else: no home
path, no framework name, no hint that some other machine has a shortcut.
"""
from __future__ import annotations

import os
from pathlib import Path

_ENV_NAME = "OPENROUTER_API_KEY"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _from_env_file(path: Path, name: str) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None                      # absent or unreadable is simply "no"
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == name:
            return value.strip().strip("\"'") or None
    return None


def _load_dotenv(path: Path) -> None:
    """python-dotenv is optional: the manual read below covers its absence."""
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    try:
        load_dotenv(path)
    except Exception:
        return


def get_api_key(name: str = _ENV_NAME) -> str:
    root_env = _REPO_ROOT / ".env"
    _load_dotenv(root_env)
    key = os.environ.get(name)
    if key:
        return key
    for candidate in (root_env, Path.home() / ".hermes" / ".env"):
        key = _from_env_file(candidate, name)
        if key:
            return key
    raise RuntimeError(
        f"{name} غير موجود. ضعه في ملف .env في جذر المشروع "
        f"(انسخ .env.example ثم أضف المفتاح) أو في متغيّر بيئة."
    )
