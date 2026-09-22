#!/usr/bin/env python3
"""Mechanical gate for a code-review report produced by the code-review-elite skill.

Validates STRUCTURE and EVIDENCE-BINDING, never truth. A passing report can still be wrong;
a failing report is unconditionally not ready to deliver.

Checks: the five required sections exist; the verdict is explicit; every finding inside an axis
section carries a citation AND an evidence tag; no tagged finding lacks a severity; the `Not proven`
section is non-empty; a clean review names what was not covered; nits never outnumber substantive
findings; forbidden flattery/hedging phrases are absent; the axes are not blended.

Usage:
    python3 check_review_report.py <report.md>
    python3 check_review_report.py --self-test

Exit codes: 0 = gate passed, 1 = violation(s), 2 = usage error.
Output is deterministic (no timestamps) so this can double as a cron monitor.
"""
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- definitions

REQUIRED_SECTIONS = ["Verdict", "Standards", "Spec", "Structure", "Not proven"]
AXIS_SECTIONS = ("standards", "spec", "structure")

VERDICT_TOKENS = re.compile(r"\b(APPROVE WITH FIXES|APPROVE|REQUEST CHANGES|BLOCKED)\b", re.I)
HEADING = re.compile(r"^(#{2,})\s+(.+?)\s*$")
FINDING_ITEM = re.compile(r"^ {0,4}(?:[-*+]|\d{1,3}[.)])\s+\S")
TERSE_FINDING = re.compile(r"^\s*L\d+(?:-\d+)?\s*[:\u2014-]")
CONTINUATION = re.compile(r"^\s{2,}\S")
SEV = re.compile(
    r"\bP[0-3]\b|\U0001F534|\U0001F7E1|\U0001F535|\u2753|bug:|risk:|nit:|"
    r"\[(?:blocking|important|nit)\]",
    re.I,
)
NIT = re.compile(r"\bP3\b|\U0001F535|nit:", re.I)
SUBSTANTIVE = re.compile(
    r"\bP[0-2]\b|\U0001F534|\U0001F7E1|bug:|risk:|\b(critical|blocking|important)\b", re.I
)
CITE_FILELINE = re.compile(r"[\w./\\-]+\.[A-Za-z0-9_]{1,8}:\d+(?:-\d+)?")
CITE_TERSE_LINE = re.compile(r"\bL\d+(?:-\d+)?\b")
CITE_NAMED = re.compile(r"`[^`\n]{3,70}`")
CITE_KEYED = re.compile(
    r"(?i)\b(?:spec|standard|rule|smell|convention|requirement)s?\s*[:#]|\bCWE-\d+\b|\bOWASP\b"
)
CITE_CONTEXT = re.compile(r"(?i)rule|smell|standard|spec|convention|requirement")
TAG_LATIN = re.compile(r"(?i)\b(PROVEN|LIKELY|UNKNOWN)\b")
TAG_ARABIC = ("\u0645\u062b\u0628\u062a", "\u0645\u0631\u062c\u062d", "\u0645\u062c\u0647\u0648\u0644")
FLATTERY = [
    "lgtm",
    "looks good to me",
    "you're absolutely right",
    "youre absolutely right",
    "great job",
    "great catch",
    "thanks for",
    "excellent feedback",
    "i noticed that",
    "might want to consider",
    "just a suggestion",
]
BLEND = [
    r"(?i)overall winner",
    r"(?i)overall verdict",
    r"(?i)combined verdict",
    r"(?i)blended verdict",
]
CLEAN_QUALIFIER = re.compile(
    r"(?i)not (?:checked|reviewed|covered|verified)|did not review|no files reviewed|unreviewed"
)
DIACRITICS = re.compile("[\u064b-\u0652\u0670\u0640]")


# ---------------------------------------------------------------- helpers


def normalize(text: str) -> str:
    """Strip Arabic diacritics/tatweel so tag matching survives vocalisation."""
    return DIACRITICS.sub("", text)


def axis_lines(text: str):
    """1-based line numbers that sit inside an axis section (Standards / Spec / Structure)."""
    allowed = set()
    current = None
    for i, line in enumerate(text.splitlines(), 1):
        m = HEADING.match(line)
        if m:
            current = m.group(2).lstrip("#").strip().rstrip(":").lower()
            continue
        if current and current.split()[0] in AXIS_SECTIONS:
            allowed.add(i)
    return allowed


def heading_present(text: str) -> dict:
    """Map each required keyword to the heading line found for it (or None)."""
    found = {k: None for k in REQUIRED_SECTIONS}
    for line in text.splitlines():
        m = HEADING.match(line)
        if not m:
            continue
        label = m.group(2).lstrip("#").strip().rstrip(":").lower()
        for kw in REQUIRED_SECTIONS:
            lk = kw.lower()
            for sep in (" ", "\u2014", "("):
                if (label == lk or label.startswith(lk + sep)) and found[kw] is None:
                    found[kw] = line
    return found


def section_body(text: str, heading_line: str) -> str:
    """Body of the section opened by `heading_line` (up to the next heading at the same level)."""
    lines = text.splitlines()
    level = len(HEADING.match(heading_line).group(1))
    try:
        start = next(i for i, l in enumerate(lines) if l == heading_line)
    except StopIteration:
        return ""
    out = []
    for line in lines[start + 1:]:
        m = HEADING.match(line)
        if m and len(m.group(1)) <= level:
            break
        out.append(line)
    return "\n".join(out)


def blocks_of_findings(lines, allowed):
    """Group finding items with their indented continuation lines.

    Returns [{line, text, has_sev, has_tag, has_cite, is_nit, is_sub}]. A finding is a list item or
    terse `L42:` line that carries a severity label on its FIRST line; continuation lines are folded
    in so a citation or tag written on the next line still counts (markdown wraps findings).
    """
    out = []
    i = 0
    n = len(lines)
    while i < n:
        ln = i + 1
        line = lines[i].rstrip()
        if ln in allowed:
            is_item = bool(FINDING_ITEM.match(line)) or bool(TERSE_FINDING.match(line))
            if is_item:
                block = [line]
                j = i + 1
                while j < n and CONTINUATION.match(lines[j]) and (j + 1) in allowed:
                    block.append(lines[j].rstrip())
                    j += 1
                joined = "  ".join(x.strip() for x in block)
                out.append(
                    {
                        "line": ln,
                        "text": joined,
                        "has_sev": bool(SEV.search(normalize(line))),
                        "has_tag": has_tag(joined),
                        "has_cite": has_citation(joined),
                        "is_sub": bool(SUBSTANTIVE.search(normalize(line))),
                        "is_nit": bool(NIT.search(normalize(line)))
                        and not SUBSTANTIVE.search(normalize(line)),
                    }
                )
                i = j
                continue
        i += 1
    return out


def has_citation(line: str) -> bool:
    n = normalize(line)
    if CITE_FILELINE.search(n) or CITE_KEYED.search(n) or CITE_TERSE_LINE.search(n):
        return True
    if CITE_NAMED.search(n) and CITE_CONTEXT.search(n):
        return True
    return False


def has_tag(line: str) -> bool:
    n = normalize(line)
    return bool(TAG_LATIN.search(n)) or any(t in n for t in TAG_ARABIC)


# ---------------------------------------------------------------- the gate


def check(text: str):
    """Return (violations, findings) where findings are the detected claim blocks."""
    v = []
    norm_all = normalize(text)
    lines = text.splitlines()
    headings = heading_present(text)

    for kw in REQUIRED_SECTIONS:
        if headings[kw] is None:
            v.append(("SEC-MISSING", "required section missing: '## %s'" % kw))

    # G9 - explicit verdict
    if headings["Verdict"]:
        body = section_body(text, headings["Verdict"])
        if not VERDICT_TOKENS.search(body):
            v.append(
                (
                    "VERDICT-INVALID",
                    "Verdict section has no APPROVE / APPROVE WITH FIXES / REQUEST CHANGES / "
                    "BLOCKED token",
                )
            )

    # G4 / G8 - findings are cited and tagged; conversely, a tag implies a severity
    findings = blocks_of_findings(lines, axis_lines(text))
    for f in findings:
        if not f["has_sev"]:
            continue
        if not f["has_cite"]:
            v.append(
                (
                    "FINDING-NOCITE",
                    "line %d: finding has no citation (rule, smell + hunk, file:line, or spec line)"
                    % f["line"],
                )
            )
        if not f["has_tag"]:
            v.append(
                (
                    "FINDING-NOTAG",
                    "line %d: finding has no evidence tag (\u0645\u062b\u0628\u062a / "
                    "\u0645\u0631\u062c\u062d / \u0645\u062c\u0647\u0648\u0644 / PROVEN / LIKELY / UNKNOWN)"
                    % f["line"],
                )
            )
    for f in findings:
        if not f["has_sev"] and f["has_tag"]:
            v.append(
                (
                    "FINDING-NOSEV",
                    "line %d: tagged finding without a severity label (P0-P3)" % f["line"],
                )
            )

    sized = [f for f in findings if f["has_sev"]]
    nits = sum(1 for f in sized if f["is_nit"])
    substantive = sum(1 for f in sized if f["is_sub"])

    # G8 - the Not proven section must carry content
    if headings["Not proven"]:
        body = section_body(text, headings["Not proven"])
        content = [
            l
            for l in body.splitlines()
            if l.strip() and l.strip() not in ("-", "*") and not l.strip().startswith("<!--")
        ]
        if not content:
            v.append(
                (
                    "NOPROVEN-EMPTY",
                    "'Not proven' section is empty - nothing verified is a FAILURE, never silence",
                )
            )

    # A clean review must name its limits
    if not sized and not CLEAN_QUALIFIER.search(norm_all):
        v.append(
            (
                "CLEAN-UNQUALIFIED",
                "no findings at all and no statement of what was NOT checked/reviewed: a clean "
                "review must name its limits",
            )
        )

    # G10 - nits never lead
    if nits > substantive:
        v.append(
            (
                "NIT-RATIO",
                "nits (%d) outnumber substantive findings (%d) - cut the nits, lead with leverage"
                % (nits, substantive),
            )
        )

    # anti-sycophancy / anti-hedging
    low_all = norm_all.lower()
    for phrase in FLATTERY:
        if phrase in low_all:
            v.append(("FLATTERY", "forbidden phrase present: '%s'" % phrase))

    # G6 - axes never blended
    for pat in BLEND:
        if re.search(pat, text):
            v.append(("AXIS-BLEND", "axes must not be blended: pattern /%s/" % pat))

    return v, sized


# ---------------------------------------------------------------- fixtures

F1 = (
    "1. **P1** `lib/invoice/capture.dart:88` \u2014 write happens before the key is persisted, "
    "so a retry can\n   double-capture. Move: persist the key in the same transaction. "
    "Evidence: rule `docs/standards/data.md#idempotency`. Tag: \u0645\u062b\u0628\u062a"
)
F2 = (
    "1. **P2** `lib/invoice/capture.dart:41` \u2014 spec requires a 24h dedupe window; "
    "implementation uses 1h.\n   Evidence: spec `docs/specs/invoice-capture.md:12`. "
    "Tag: \u0645\u062b\u0628\u062a"
)
F3 = (
    "1. **P3** `lib/invoice/capture.dart:110-160` \u2014 50-line function does 4 things. "
    "Extract\n   validate/normalize/persist. Tag: \u0645\u0631\u062c\u062d"
)
NP1 = "- Concurrency behaviour under >100 parallel captures \u2014 would need a load test."
NP2 = "- Not reviewed: the iOS build config files in the diff."

GOOD = (
    "# Code Review: feat(invoice) add idempotent capture\n\n"
    "**Target:** `main...HEAD` (3 commits, 4 files, 120 changed lines)\n"
    "**Scope note:** uncommitted and working-tree changes are NOT included (three-dot diff)\n"
    "**Context:** invoice capture may be retried by the queue; the change adds an idempotency key.\n\n"
    "## Verdict\n\n"
    "**APPROVE WITH FIXES** \u2014 one P1 correctness gap; nothing security-critical.\n"
    "Blocking: 1\n\n"
    "## Standards\n\n" + F1 + "\n\n"
    "## Spec\n\n" + F2 + "\n\n"
    "## Structure\n\n" + F3 + "\n\n"
    "## Declined to judge\n\n"
    "- Retry backoff values \u2014 outside this spec; owned by the queue change.\n\n"
    "## Not proven (\u0645\u0627 \u0644\u0645 \u064a\u064f\u062b\u0628\u062a)\n\n"
    + NP1 + "\n" + NP2 + "\n\n"
    "## Next steps\n\n1. Fix all\n2. Fix P0/P1 only\n3. Fix specific items\n"
    "4. Review only \u2014 no implementation\n"
)


def _mutations():
    """(name, expected_code, mutated_text). Each case asserts its own fixture changed."""
    m = []

    m.append(
        (
            "finding-without-citation",
            "FINDING-NOCITE",
            GOOD.replace(
                "`lib/invoice/capture.dart:88` \u2014 write happens before the key is persisted, "
                "so a retry can\n   double-capture. Move: persist the key in the same transaction. "
                "Evidence: rule `docs/standards/data.md#idempotency`. Tag: \u0645\u062b\u0628\u062a",
                "write happens before the key is persisted, so a retry can double-capture. "
                "Move: persist the key in the same transaction. Tag: \u0645\u062b\u0628\u062a",
            ),
        )
    )

    m.append(
        (
            "finding-without-tag",
            "FINDING-NOTAG",
            GOOD.replace(
                "Evidence: spec `docs/specs/invoice-capture.md:12`. Tag: \u0645\u062b\u0628\u062a",
                "Evidence: spec `docs/specs/invoice-capture.md:12`.",
            ),
        )
    )

    m.append(
        (
            "tag-without-severity",
            "FINDING-NOSEV",
            GOOD.replace(
                "**P3** `lib/invoice/capture.dart:110-160`",
                "`lib/invoice/capture.dart:110-160`",
            ),
        )
    )

    m.append(("empty-not-proven", "NOPROVEN-EMPTY", GOOD.replace(NP1 + "\n" + NP2, "")))

    m.append(
        (
            "flattery",
            "FLATTERY",
            GOOD.replace(
                "**APPROVE WITH FIXES** \u2014 one P1 correctness gap; nothing security-critical.",
                "**APPROVE WITH FIXES** \u2014 LGTM overall, one P1 correctness gap.",
            ),
        )
    )

    m.append(
        (
            "nit-ratio",
            "NIT-RATIO",
            GOOD.replace(
                F3,
                F3
                + "\n2. **P3** `lib/invoice/capture.dart:161` \u2014 rename `d` to `draft`. "
                "Tag: \u0645\u0631\u062c\u062d"
                + "\n3. **P3** `lib/invoice/capture.dart:162` \u2014 sort imports. "
                "Tag: \u0645\u0631\u062c\u062d",
            ),
        )
    )

    m.append(("missing-section", "SEC-MISSING", GOOD.replace("## Structure\n", "")))

    m.append(
        (
            "bad-verdict",
            "VERDICT-INVALID",
            GOOD.replace(
                "**APPROVE WITH FIXES** \u2014 one P1 correctness gap; nothing security-critical.",
                "Verdict: opinions differ, see below.",
            ),
        )
    )

    m.append(
        (
            "axis-blend",
            "AXIS-BLEND",
            GOOD.replace("Blocking: 1", "Blocking: 1\nOverall winner: Standards."),
        )
    )

    m.append(
        (
            "flat-clean",
            "CLEAN-UNQUALIFIED",
            GOOD.replace(F1, "")
            .replace(F2, "")
            .replace(F3, "")
            .replace(NP2, "Everything looked fine."),
        )
    )

    return m


def self_test() -> int:
    failures = []
    v, sized = check(GOOD)
    print("[self-test] baseline: %d finding(s), %d violation(s)" % (len(sized), len(v)))
    if v:
        failures.append("baseline GOOD report must pass, got: %s" % v)

    for name, code, text in _mutations():
        if text == GOOD:
            failures.append(
                "%s: MUTATION WAS A NO-OP (fixture did not change) - the case proves nothing" % name
            )
            continue
        mv, _ = check(text)
        codes = [c for c, _ in mv]
        if code not in codes:
            failures.append("%s: expected %s, got %s" % (name, code, codes or "no violations"))
        else:
            print("[self-test] %s: caught %s (as expected)" % (name, code))

    if failures:
        print("\nSELF-TEST FAILED")
        for f in failures:
            print("  -", f)
        return 1
    print("\nSELF-TEST PASSED - the gate can fail, and a compliant report passes it.")
    return 0


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    if argv[1] == "--self-test":
        return self_test()
    path = Path(argv[1])
    if not path.is_file():
        print("usage error: %s is not a file" % path)
        return 2
    v, sized = check(path.read_text(encoding="utf-8"))
    print("report: %s" % path)
    print("findings detected: %d" % len(sized))
    if not v:
        print("GATE PASSED - structure and evidence-binding are intact.")
        return 0
    print("GATE FAILED - %d violation(s):" % len(v))
    for code, msg in v:
        print("  FAIL %s: %s" % (code, msg))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
