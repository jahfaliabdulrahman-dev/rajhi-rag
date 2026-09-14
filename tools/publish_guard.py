#!/usr/bin/env python3
"""Publish guard — the last line of defense before anything goes PUBLIC.

What-if workshop #8/#9 (the catastrophic tier): one careless push puts real
family data, account numbers, or personal paths into a public repository —
an effect that cannot be undone. This scanner runs on every push (git hook),
on CI, and manually:

    python3 tools/publish_guard.py --tree        # what is tracked now
    python3 tools/publish_guard.py --history     # everything ever committed
    python3 tools/publish_guard.py --pre-push    # refs fed by the git hook
    python3 tools/publish_guard.py --tree --history --ci

Severity model (practical by design — a guard that cries wolf gets disabled):
- BLOCK: personal home paths · the original statement filename · real family
  names appearing in the document · ≥10-digit runs (account/card numbers) ·
  real-data paths (data/local_sample/*) · .env files · media binaries that
  are not explicitly allowed. Any BLOCK failing exit code 1.
- WARN: the owner's name/handle tokens in prose/docs (usually attribution —
  review, don't panic). WARN does not fail the run.

ALLOWLIST: `.publish-allowlist` — one entry per line:
    <rule_id> :: <path-glob> :: <why>
Self-exclusion: this script, the allowlist, and the hooks dir are never
scanned (their pattern sources would otherwise self-trip).

Stdlib only — it must run in CI and inside git hooks with bare python3.
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_AR = "0-9\u0660-\u0669\u06f0-\u06f9"  # western + arabic-indic + persian

TEXT_RULES = [
    ("home_path", "BLOCK", re.compile(r"/Users/[A-Za-z0-9_.-]+"),
     "مسار منزل مطلق (اسم مستخدم حقيقي)"),
    ("orig_filename", "BLOCK", re.compile(r"[Rr]ajehi\s+[Oo]riginal"),
     "اسم ملف الكشف الاصلي"),
    ("name_full", "BLOCK", re.compile(r"عبده\s*جحفلي"),
     "اسم عائلي من الكشف الحقيقي"),
    ("long_digits", "BLOCK", re.compile("[" + _AR + "]{10,}"),
     "سلسلة ارقام طويلة (رقم حساب/بطاقة؟)"),
    ("name_token", "WARN",
     re.compile(r"عبد\s*الرحمن|جحفلي|jahfali|abdurrahman", re.IGNORECASE),
     "اسم/معرف المالك — راجعه"),
]

BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".tif",
               ".tiff", ".bmp", ".pdf", ".ttf", ".otf", ".woff", ".woff2",
               ".mp4", ".mov", ".zip", ".gz", ".tar", ".ico", ".icns",
               ".pyc", ".so", ".dylib", ".sqlite", ".db"}
MEDIA_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".tif",
              ".tiff", ".bmp", ".pdf", ".mp4", ".mov"}

PATH_RULES = [
    ("local_data", "BLOCK",
     lambda p: p == "data/local_sample" or p.startswith("data/local_sample/"),
     "ملف بيانات حقيقية — ممنوع رفعه نهائياً"),
    ("env_file", "BLOCK", lambda p: Path(p).name == ".env", "ملف اسرار"),
    ("media_file", "BLOCK",
     lambda p: Path(p).suffix.lower() in MEDIA_EXTS
     and not fnmatch.fnmatch(p, "data/sample/*.pdf"),
     "وسائط/مستند ثنائي غير مسموح — راجع قائمة المسموح"),
]

SKIP_PATHS = {"tools/publish_guard.py", ".publish-allowlist"}


def _git(*args: str) -> str:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    return out.stdout.decode("utf-8", "replace")


def _git_bytes(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT,
                          capture_output=True).stdout


def load_allowlist() -> list[tuple[str, str]]:
    p = ROOT / ".publish-allowlist"
    if not p.exists():
        return []
    entries = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split("::")]
        if len(parts) >= 2:
            entries.append((parts[0], parts[1]))
    return entries


def _allowed(entries, rule_id: str, path: str) -> bool:
    return any(rid == rule_id and fnmatch.fnmatch(path, glob)
               for rid, glob in entries)


def _snippet(line: str) -> str:
    s = line.strip()
    s = re.sub("[" + _AR + "]{6,}", lambda m: m.group(0)[:2] + "…", s)
    return s[:90]


def _is_digit_table(text: str) -> bool:
    """«٠١٢٣٤٥٦٧٨٩»-style translation tables are ramps, not account numbers."""
    t = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
                                     "01234567890123456789"))
    return "0123456789" in t or "9876543210" in t


def _scan_text(path: str, text: str, where: str, findings, entries) -> None:
    for lineno, line in enumerate(text.splitlines(), 1):
        for rid, sev, rx, desc in TEXT_RULES:
            m = rx.search(line)
            if not m:
                continue
            if rid == "long_digits" and _is_digit_table(m.group(0)):
                continue
            if _allowed(entries, rid, path):
                continue
            findings.append((sev, rid, path, where, lineno,
                             _snippet(line), desc))


def _check_path(path: str, where: str, findings, entries) -> None:
    if path in SKIP_PATHS or path.startswith(".githooks/"):
        return
    for rid, sev, pred, desc in PATH_RULES:
        try:
            hit = pred(path)
        except Exception:
            hit = False
        if hit and not _allowed(entries, rid, path):
            findings.append((sev, rid, path, where, 0, "", desc))


def _read_blobs(shas: list[str]) -> dict[str, bytes]:
    """Batch-read blobs in ONE git process (fast even for history mode)."""
    if not shas:
        return {}
    proc = subprocess.run(["git", "cat-file", "--batch"],
                          input="\n".join(shas).encode(),
                          cwd=ROOT, capture_output=True)
    out = proc.stdout
    result: dict[str, bytes] = {}
    i = 0
    while i < len(out):
        nl = out.find(b"\n", i)
        if nl < 0:
            break
        header = out[i:nl].decode("utf-8", "replace").split()
        if len(header) == 3 and header[1] == "blob":
            size = int(header[2])
            content = out[nl + 1: nl + 1 + size]
            result[header[0]] = content
            i = nl + 1 + size + 1
        else:  # missing / unusual object
            i = nl + 1
    return result


def _tree_entries(rev: str) -> list[tuple[str, str]]:
    """[(path, blob_sha)] for a commit tree."""
    out = _git("ls-tree", "-r", rev)
    pairs = []
    for line in out.splitlines():
        if "\t" not in line:
            continue
        meta, path = line.split("\t", 1)
        parts = meta.split()
        if len(parts) >= 3 and parts[1] == "blob":
            pairs.append((path, parts[2]))
    return pairs


def _scan_blobs(pairs: list[tuple[str, str]], where: str,
                findings, entries, seen: set[str]) -> None:
    blob_of = {}
    for path, sha in pairs:
        _check_path(path, where, findings, entries)
        if path in SKIP_PATHS or path.startswith(".githooks/"):
            continue
        if Path(path).suffix.lower() in BINARY_EXTS:
            continue
        blob_of.setdefault(sha, path)
    fresh = [sha for sha in blob_of if sha not in seen]
    blobs = _read_blobs(fresh)
    for sha in fresh:
        seen.add(sha)
        data = blobs.get(sha)
        if data is None:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        _scan_text(blob_of[sha], text, where, findings, entries)


def scan_tree(findings, entries, seen) -> int:
    pairs = _tree_entries("HEAD")
    _scan_blobs(pairs, "tree", findings, entries, seen)
    return len(pairs)


def scan_history(findings, entries, seen) -> int:
    # Every object ONCE (rev-list dedupes objects); the same path appears
    # many times across commits with different blob shas — ALL versions must
    # be scanned, or an older commit that still carries PII slips through.
    # (An earlier version deduped by path and kept only the newest blob —
    # caught by running it: older test fixtures with real names were masked.)
    out = _git("rev-list", "--objects", "--all")
    pairs, dedup = [], set()
    for line in out.splitlines():
        parts = line.split(" ", 1)
        if len(parts) != 2:
            continue
        sha, path = parts
        if (path, sha) in dedup:
            continue
        dedup.add((path, sha))
        pairs.append((path, sha))
    _scan_blobs(pairs, "history", findings, entries, seen)
    return len(pairs)


def scan_pre_push(findings, entries, seen) -> int:
    refs = [l.split() for l in sys.stdin.read().splitlines() if l.strip()]
    revs: set[str] = set()
    for parts in refs:
        if len(parts) < 4:
            continue
        local_sha, remote_sha = parts[1], parts[3]
        if set(local_sha) <= {"0"}:
            continue  # branch deletion
        if set(remote_sha) <= {"0"}:
            revs.update(_git("rev-list", local_sha).split())
        else:
            revs.update(_git("rev-list", f"{remote_sha}..{local_sha}").split())
    if len(revs) > 200:
        print(f"[publish-guard] pushed history is large ({len(revs)} commits) "
              f"— scanning the tip tree + first 200 commits")
        revs = set(sorted(revs)[:200])
    pairs = []
    for rev in sorted(revs):
        pairs.extend(_tree_entries(rev))
    _scan_blobs(pairs, "push", findings, entries, seen)
    n = len(pairs)
    n += scan_tree(findings, entries, seen)
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="publish-time PII guard")
    ap.add_argument("--tree", action="store_true", help="scan HEAD tree")
    ap.add_argument("--history", action="store_true",
                    help="scan every blob in every commit")
    ap.add_argument("--pre-push", action="store_true", dest="pre_push",
                    help="read refs from stdin (git hook) and scan them")
    ap.add_argument("--ci", action="store_true",
                    help="tree + history (CI mode)")
    ap.add_argument("--report-only", action="store_true",
                    help="print findings but always exit 0")
    args = ap.parse_args()

    if not (args.tree or args.history or args.pre_push or args.ci):
        args.tree = True

    entries = load_allowlist()
    findings: list[tuple] = []
    seen: set[str] = set()
    scanned = []

    if args.pre_push:
        scanned.append(("push", scan_pre_push(findings, entries, seen)))
    if args.tree or args.ci:
        scanned.append(("tree", scan_tree(findings, entries, seen)))
    if args.history or args.ci:
        scanned.append(("history", scan_history(findings, entries, seen)))

    blocks = [f for f in findings if f[0] == "BLOCK"]
    warns = [f for f in findings if f[0] == "WARN"]
    print(f"[publish-guard] " +
          " · ".join(f"{label}: {n}" for label, n in scanned) +
          f" — {len(blocks)} BLOCK / {len(warns)} WARN")
    for sev, rid, path, where, lineno, snip, desc in findings:
        loc = f"{path}:{lineno}" if lineno else path
        print(f"  {sev:<5} {rid:<12} [{where}] {loc}"
              + (f"  | {snip}" if snip else "") + f"  — {desc}")
    if blocks:
        print("\nالحكم: BLOCK — لا تدفع حتى تُعالج هذه البنود "
              "(أو أضف استثناءً مبرَّراً في .publish-allowlist).")
    else:
        print("\nالحكم: آمن للدفع (تحذيرات فقط تحتاج نظراً).")
    if blocks and not args.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
