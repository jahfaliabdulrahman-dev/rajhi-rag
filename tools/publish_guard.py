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
  names appearing in the document · ≥10-digit runs (account/card numbers) —
  **including runs a plain scan cannot see**: runs broken by a grouping
  separator (uniform groups of 3 or 4 wide, joined by space/dot/hyphen/
  underscore) and runs rebuilt by adding two string literals together ·
  real-data paths (data/local_sample/*) · .env files · media binaries that
  are not explicitly allowed · unscannable binaries (archives/databases/
  fonts) with no allowlist line of their own · any tracked blob that cannot
  be decoded as text. Any BLOCK fails the run (exit 1).
- WARN: the owner's name/handle tokens in prose, docs and commit messages
  (usually attribution — review, don't panic). WARN does NOT fail the run by
  default; `--strict-warn` makes it fail, and the output always prints an
  explicit advisory block so a WARN can never pass unnoticed.

WHAT THIS GUARD CANNOT SEE (documented, not hidden): the bytes inside media
binaries and allowlisted archives are skipped, never read. An allowlist line
is therefore a *claim by a human*, not a scan — which is exactly why every
line in `.publish-allowlist` carries a written reason. Nor does it see the
outside world (a value already indexed elsewhere), and its self-exclusion is
a HOLE, not a feature: this file is never scanned by itself, so its text is
policed by `test_guard_source_passes_its_own_rules` in the suite instead —
the rule exists because a real account number once sat in this very docstring
as two added literals, invisible to the guard that excluded itself.

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

LONG_DIGITS_RX = re.compile("[" + _AR + "]{10,}")
LONG_DIGITS_DESC = "سلسلة ارقام طويلة (رقم حساب/بطاقة؟)"

# A long run can be written in uniform groups — the IBAN/card/cheque idiom
# (four-wide groups for IBANs and cards, three-wide for some cheque formats).
# The signature used here is groups of EQUAL width, 3 or 4 digits, joined by
# one separator:
#   · equal width  → two unrelated amounts on one line are never welded;
#   · width 3 or 4 → "١٤٣٩٠٧٢٢ ٢٠١٨٠٤٠٨" (two 8-digit dates) and
#                    "20260917-172327" (a timestamp) stay two numbers.
# Both of those were FALSE POSITIVES produced by the first draft of this
# rule — found by running it against the repository itself, which is why the
# width test exists at all.
# Commas are deliberately not grouping separators: "1000,2000,3000,4000" is a
# CSV row of four amounts, not one number. Stated consequence (honest limit):
# "1,234,567,890" — non-uniform groups — is NOT caught by this rule.
_GROUP_SEP = " \t._-"
_GROUPED_RUN = re.compile("[" + _AR + "]{3,}(?:[" + _GROUP_SEP + "]"
                          "[" + _AR + "]{3,})+")
# The two-literal trick: 'aaaa' + 'bbbb' → one run the plain rule never sees.
_STRING_CONCAT = re.compile("""["']\\s*\\+\\s*["']""")

TEXT_RULES = [
    ("home_path", "BLOCK", re.compile(r"/Users/[A-Za-z0-9_.-]+"),
     "مسار منزل مطلق (اسم مستخدم حقيقي)"),
    ("orig_filename", "BLOCK", re.compile(r"[Rr]ajehi\s+[Oo]riginal"),
     "اسم ملف الكشف الاصلي"),
    ("name_full", "BLOCK", re.compile(r"عبده\s*جحفلي"),
     "اسم عائلي من الكشف الحقيقي"),
    ("long_digits", "BLOCK", LONG_DIGITS_RX, LONG_DIGITS_DESC),
    ("name_token", "WARN",
     re.compile(r"عبد\s*الرحمن|جحفلي|jahfali|abdurrahman", re.IGNORECASE),
     "اسم/معرف المالك — راجعه"),
]
# rule id recorded when the run only appears AFTER joining string literals
CONCAT_RULE = ("concat_digits", "BLOCK",
               "رقم مبني بتجميع شطرين نصيّين (يتخطى فحص السلاسل)")

BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".tif",
               ".tiff", ".bmp", ".pdf", ".ttf", ".otf", ".woff", ".woff2",
               ".mp4", ".mov", ".zip", ".gz", ".tar", ".ico", ".icns",
               ".pyc", ".so", ".dylib", ".sqlite", ".db"}
MEDIA_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".tif",
              ".tiff", ".bmp", ".pdf", ".mp4", ".mov"}
# Binaries the guard cannot read as text: archives, exports, databases, fonts.
# They are not "safe" — they are *opaque*. Each one needs an allowlist line.
OPAQUE_EXTS = {".zip", ".xlsx", ".xlsm", ".xls", ".docx", ".doc", ".pptx",
               ".ppt", ".sqlite", ".db", ".tar", ".gz", ".tgz", ".7z", ".rar",
               ".pickle", ".pkl", ".bin", ".ttf", ".otf", ".woff", ".woff2"}

PATH_RULES = [
    ("local_data", "BLOCK",
     lambda p: p == "data/local_sample" or p.startswith("data/local_sample/"),
     "ملف بيانات حقيقية — ممنوع رفعه نهائياً"),
    ("env_file", "BLOCK", lambda p: Path(p).name == ".env", "ملف اسرار"),
    ("media_file", "BLOCK",
     lambda p: Path(p).suffix.lower() in MEDIA_EXTS
     and not fnmatch.fnmatch(p, "data/sample/*.pdf"),
     "وسائط/مستند ثنائي غير مسموح — راجع قائمة المسموح"),
    ("opaque_binary", "BLOCK",
     lambda p: Path(p).suffix.lower() in OPAQUE_EXTS,
     "ثنائي لا يمكن فحصه كنص (ارشيف/قاعدة/خط) — لا يُدفع بلا سطر استثناء مبرَّر"),
    ("undecodable", "BLOCK",
     lambda p: False,  # decided in _scan_blobs, where the bytes are known
     "ملف لا يُفك كنص ولم يُدرج في قوائم الوسائط — لا يُدفع بصمت"),
]

SKIP_PATHS = {"tools/publish_guard.py", ".publish-allowlist"}


def _git(*args: str) -> str:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    return out.stdout.decode("utf-8", "replace")


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
            result[header[0]] = out[nl + 1: nl + 1 + size]
            i = nl + 1 + size + 1
        else:  # missing / unusual object
            i = nl + 1
    return result


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


_SCOPES = {"tree", "history", "push", "message", "worktree"}


def _allowed(entries, rule_id: str, path: str, where: str = "") -> bool:
    """Is this rule waived for this path — and, when scoped, in this pass?

    A glob may carry a scope prefix (`history:tests/x.py`). An exemption that
    only exists because OLD commits carry the value must not also blind the
    working tree: the tree is what a future edit lands in, and that is exactly
    where the account number slipped through the first time (audit S1).
    An unprefixed glob keeps the old meaning — every pass.
    """
    for rid, glob in entries:
        if rid != rule_id:
            continue
        scope, _, rest = glob.partition(":")
        if rest and scope in _SCOPES:
            if where and where != scope:
                continue
            glob = rest
        if fnmatch.fnmatch(path, glob):
            return True
    return False


def _snippet(line: str) -> str:
    s = line.strip()
    s = re.sub("[" + _AR + "]{6,}", lambda m: m.group(0)[:2] + "…", s)
    return s[:90]


_JOIN_RX = re.compile(r"""(['"])(.*?)\1\s*\.join\s*\(\s*[\[\(]([^\]\)]*)[\]\)]""")
_LIT_RX = re.compile(r"""(['"])(.*?)\1""")


def _joined_literals(line: str) -> str:
    """«"".join([...])» of string literals — the idiom `concat_digits` cannot see.

    The rule was born from a split account number (`"a" + "b"`), and the very
    file it caught later moved to `"".join(_PARTS)`, which walked straight past
    it. Detecting a rule's blind spot is part of the rule (external audit, S1).
    """
    built: list[str] = []
    for m in _JOIN_RX.finditer(line):
        sep, body = m.group(2), m.group(3)
        # The real value uses the separator: `" ".join(("١٤٣٩٠٧٢٢", "٢٠١٨٠٤٠٨"))`
        # is two dates, not a sixteen-digit run — welding them would be the same
        # false positive the first draft of the digit rule produced.
        built.append(sep.join(lit for _q, lit in _LIT_RX.findall(body)))
    return "".join(built)


# The pieces need not sit inside the join(): `_PARTS = ("a", "b")` on one line
# and `"".join(_PARTS)` on the next is the shape THIS repository adopted after
# the first rule caught `"a" + "b"` — so the file the rule was born from walked
# past it a second time (audit, round 3). A registry of name -> literal pieces
# closes it without needing a full parser.
_ASSIGN_SEQ_RX = re.compile(
    r"""^\s*([A-Za-z_][A-Za-z_0-9]*)\s*=\s*[\[\(]([^\]\)]*)[\]\)]""", re.M)
_JOIN_NAME_RX = re.compile(
    r"""(['"])(.*?)\1\s*\.join\s*\(\s*([A-Za-z_][A-Za-z_0-9]*)\s*\)""")
# Python welds adjacent string literals at PARSE time: `"a" "b"` is one string
# and no operator appears between them, so `concat_digits` never sees it.
_ADJACENT_LIT_RX = re.compile(r"""(['"])([^'"]*)\1[ \t]+(['"])([^'"]*)\3""")


def _literal_registry(text: str) -> dict[str, list[str]]:
    """`NAME = ("a", "b")` / `["a", "b"]` -> the pieces a later join() welds."""
    reg: dict[str, list[str]] = {}
    for m in _ASSIGN_SEQ_RX.finditer(text):
        lits = [lit for _q, lit in _LIT_RX.findall(m.group(2))]
        if lits:
            reg[m.group(1)] = lits
    return reg


def _joined_names(line: str, registry: dict[str, list[str]]) -> str:
    """`sep.join(NAME)` -> the string it builds, using the registered pieces."""
    built: list[str] = []
    for m in _JOIN_NAME_RX.finditer(line):
        sep, name = m.group(2), m.group(3)
        if name in registry:
            built.append(sep.join(registry[name]))
    return "".join(built)


def _weld_adjacent_literals(line: str) -> str:
    """`"a" "b"` -> `"ab"`, repeatedly (three or more pieces weld too)."""
    prev = None
    while prev != line:
        prev = line
        line = _ADJACENT_LIT_RX.sub(
            lambda m: m.group(1) + m.group(2) + m.group(4) + m.group(1), line)
    return line


HEX_CHARS = "0123456789abcdefABCDEF"
HEX_LETTERS = "abcdefABCDEF"


def _in_hex_token(src: str, match, min_len: int = 24) -> bool:
    """A ten-digit run inside a long hexadecimal token is a hash, not an account.

    Both auditors hit this: a commit sha blocked the message that documented it,
    and a guard that teaches its own team to omit evidence works against itself.

    TWO conditions, and the second one is the whole point. Length alone is not a
    discriminator, because DIGITS ARE HEXADECIMAL CHARACTERS: with length only,
    any digit run of `min_len` or more became "a hash" and walked out — measured
    at 30 of the 31 real statement descriptions that carry a ≥24-digit run
    (audit, 2026-09-17). A hash also carries at least one a–f letter; an account
    number, a card, an IBAN's digits and a padded reference never do. Requiring
    a letter keeps the sha exemption and closes the hole, and it fails SAFE: an
    all-digit token is scanned, not waived.
    """
    a = match.start()
    while a > 0 and src[a - 1] in HEX_CHARS:
        a -= 1
    b = match.end()
    while b < len(src) and src[b] in HEX_CHARS:
        b += 1
    token = src[a:b]
    return len(token) >= min_len and any(c in HEX_LETTERS for c in token)


def _is_digit_table(text: str) -> bool:
    """«٠١٢٣٤٥٦٧٨٩»-style translation tables are ramps, not account numbers.
    Rotations count too («۱۲۳۴۵۶۷۸۹۰»): the doubled-string check catches
    every cyclic shift of 0123456789 / 9876543210."""
    t = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
                                     "01234567890123456789"))
    doubled = t + t
    return "0123456789" in doubled or "9876543210" in doubled


def _digit_variants(line: str) -> list[str]:
    """The line plus every way a grouped run can hide inside it.

    A number a human reads as one value is often printed in uniform groups
    (IBANs, cards, cheques). Joining is allowed only when every group has the
    SAME width and that width is 3 or 4 — the two conditions that keep a pair
    of adjacent dates, a hyphenated timestamp and a row of equal-width
    amounts from being welded into a false account number.
    """
    out = [line]
    for m in _GROUPED_RUN.finditer(line):
        groups = re.split("[" + _GROUP_SEP + "]", m.group(0))
        if len(groups) < 2 or len(groups[0]) not in (3, 4):
            continue
        if len({len(g) for g in groups}) != 1:
            continue
        joined = line[:m.start()] + "".join(groups) + line[m.end():]
        if joined not in out:
            out.append(joined)
    return out


def _join_string_concat(line: str) -> str:
    """'aaaa' + 'bbbb' → 'aaaabbbb' (the trick that hid a real account)."""
    return _STRING_CONCAT.sub("", line)


def _scan_text(path: str, text: str, where: str, findings, entries) -> None:
    def record(sev, rid, lineno, src_line, desc):
        if _allowed(entries, rid, path, where):
            return
        findings.append((sev, rid, path, where, lineno, _snippet(src_line), desc))

    # Python-only welds: a registry of `NAME = (pieces…)` for a later join(),
    # and parse-time concatenation of adjacent literals. Restricted to .py
    # because both are Python semantics — applying them to prose would invent
    # numbers out of two quoted words that merely sit side by side.
    is_py = path.endswith(".py")
    registry = _literal_registry(text) if is_py else {}

    for lineno, line in enumerate(text.splitlines(), 1):
        if is_py:
            line = _weld_adjacent_literals(line)
        for rid, sev, rx, desc in TEXT_RULES:
            if rid == "long_digits":
                continue  # handled below over the digit-joined variants
            for _m in rx.finditer(line):  # every match, not just the first
                record(sev, rid, lineno, line, desc)
        named = _joined_names(line, registry) if registry else ""
        if named and LONG_DIGITS_RX.search(named) and not _is_digit_table(named):
            record("BLOCK", "joined_digits", lineno, line,
                   "رقم مبني بـ join على شظائف مُسمّاة")
        for src in _digit_variants(line):
            matches = [m for m in LONG_DIGITS_RX.finditer(src)
                       if not _is_digit_table(m.group(0))
                       and not _in_hex_token(src, m)]
            if matches:
                for _m in matches:  # every occurrence, not just the first
                    record("BLOCK", "long_digits", lineno, line,
                           LONG_DIGITS_DESC)
                break  # the joined variant already reported this line
        built = _joined_literals(line)
        if built and LONG_DIGITS_RX.search(built) and not _is_digit_table(built):
            record("BLOCK", "joined_digits", lineno, line,
                   "رقم مبني بـ join على شظائف نصية")
        joined = _join_string_concat(line)
        if joined != line:
            for m in LONG_DIGITS_RX.finditer(joined):
                if _is_digit_table(m.group(0)):
                    continue
                record(CONCAT_RULE[1], CONCAT_RULE[0], lineno, line,
                       CONCAT_RULE[2])
                break


def _binary_verdict(path: str, entries) -> tuple | None:
    """Decision for a tracked blob whose bytes are not decodable text.

    Pure and testable: media are handled by PATH_RULES, opaque binaries are
    handled by PATH_RULES too, so anything left here is an unknown binary —
    and silence is the one answer that is never acceptable.
    """
    ext = Path(path).suffix.lower()
    if ext in MEDIA_EXTS or ext in OPAQUE_EXTS:
        return None
    if _allowed(entries, "undecodable", path):
        return None
    return ("BLOCK", "undecodable", path, "", 0, "",
            "ملف لا يُفك كنص ولم يُدرج في قوائم الوسائط — لا يُدفع بصمت")


def _check_path(path: str, where: str, findings, entries) -> None:
    if path in SKIP_PATHS or path.startswith(".githooks/"):
        return
    for rid, sev, pred, desc in PATH_RULES:
        try:
            hit = pred(path)
        except Exception:
            hit = False
        if hit and not _allowed(entries, rid, path, where):
            findings.append((sev, rid, path, where, 0, "", desc))


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
        if Path(path).suffix.lower() in (BINARY_EXTS | OPAQUE_EXTS):
            continue  # unreadable by design; their verdict comes from PATH_RULES
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
            verdict = _binary_verdict(blob_of[sha], entries)
            if verdict:
                findings.append(verdict[:-1] + (where,) + verdict[-1:])
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


def scan_messages(findings, entries, revs: list[str] | None = None) -> int:
    """Commit messages carry text too — an account number pasted into a
    message body is exactly as public as one pasted into a file, and until
    now messages were never scanned at all. The public repo URL already
    carries the owner's handle, so `name_token` findings here are WARN at
    worst (attribution), never a block. Author/committer identities are NOT
    scanned for the same reason: they are already public on the remote."""
    args = ["log", "--format=%H%x09%B%x1e"]
    if revs:
        args += list(revs)
    else:
        args.append("--all")
    out = _git(*args)
    n = 0
    for chunk in out.split("\x1e"):
        sha, _, body = chunk.partition("\t")
        sha = sha.strip()
        if not sha or not body.strip():
            continue
        n += 1
        pseudo = f"git-msg/{sha[:10]}"
        for rid, sev, rx, desc in TEXT_RULES:
            for m in rx.finditer(body):
                if rid == "long_digits" and _is_digit_table(m.group(0)):
                    continue
                if _allowed(entries, rid, pseudo):
                    continue
                findings.append((sev, rid, pseudo, "message", 0,
                                 _snippet(m.group(0)), desc))
        joined = _join_string_concat(body)
        if joined != body:
            for m in LONG_DIGITS_RX.finditer(joined):
                if _is_digit_table(m.group(0)):
                    continue
                findings.append(("BLOCK", CONCAT_RULE[0], pseudo, "message",
                                 0, _snippet(body), CONCAT_RULE[2]))
                break
    return n


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
    # No sampling: a commit that carried PII and was later rewritten is
    # exactly the case this mode exists for, and picking "the first 200 by
    # SHA text" is a random sample dressed up as coverage. Blob dedup (`seen`)
    # keeps the cost linear in NEW blobs, not in commits.
    pairs = []
    for rev in sorted(revs):
        pairs.extend(_tree_entries(rev))
    _scan_blobs(pairs, "push", findings, entries, seen)
    n = len(pairs)
    n += scan_messages(findings, entries, sorted(revs))
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
                    help="tree + history + commit messages (CI mode)")
    ap.add_argument("--messages", action="store_true",
                    help="scan every commit message body")
    ap.add_argument("--strict-warn", action="store_true", dest="strict_warn",
                    help="treat WARN as blocking (opt-in; default is advisory)")
    ap.add_argument("--report-only", action="store_true",
                    help="print findings but always exit 0")
    args = ap.parse_args()

    if not (args.tree or args.history or args.pre_push or args.ci
            or args.messages):
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
        scanned.append(("messages", scan_messages(findings, entries)))
    if args.messages and not (args.history or args.ci):
        scanned.append(("messages", scan_messages(findings, entries)))

    blocks = [f for f in findings if f[0] == "BLOCK"]
    warns = [f for f in findings if f[0] == "WARN"]
    print("[publish-guard] " +
          " · ".join(f"{label}: {n}" for label, n in scanned) +
          f" — {len(blocks)} BLOCK / {len(warns)} WARN")
    if warns:
        print("[publish-guard] تنبيه معلن (لا يوقف الدفع):")
        for sev, rid, path, where, lineno, snip, desc in warns:
            loc = f"{path}:{lineno}" if lineno else path
            print(f"  WARN  {rid:<12} [{where}] {loc}"
                  + (f"  | {snip}" if snip else "") + f"  — {desc}")
        print("  → للمنع الصارم: أضف --strict-warn، أو استثناءً مبرَّراً "
              "في .publish-allowlist (كل سطر بسبب مكتوب).")
    for sev, rid, path, where, lineno, snip, desc in blocks:
        loc = f"{path}:{lineno}" if lineno else path
        print(f"  {sev:<5} {rid:<12} [{where}] {loc}"
              + (f"  | {snip}" if snip else "") + f"  — {desc}")
    if blocks:
        print("\nالحكم: BLOCK — لا تدفع حتى تُعالج هذه البنود "
              "(أو أضف استثناءً مبرَّراً في .publish-allowlist).")
    else:
        print("\nالحكم: آمن للدفع.")
    if (blocks or (warns and args.strict_warn)) and not args.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
