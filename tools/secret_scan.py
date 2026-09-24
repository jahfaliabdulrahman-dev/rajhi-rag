#!/usr/bin/env python3
"""ماسحُ الأسرار في **ما يُضاف التزامًا** — صنفٌ دخل فعلًا في هذه الحادثة، فالمنعُ قبل وجود الكائن.

**لماذا أداةٌ لا `grep` في الخطّاف:** قِيس ٢٠٢٦-٠٩-٢٥ أنّ النمطَ الأوّل (في `pre-commit`) كان يمرّر
`sk-or-v1-…` و`sk-ant-…` و`sk-proj-…` و`github_pat_…` — لأنّه توقّف عند أوّل شَرطة، فأمسكه مدقّقٌ
بمفاتيحَ مصطنعة. والنمطُ الواحد لا يُغني: هنا **نمطٌ لكلّ صنف**، **وضابطٌ يعدّد الأصنافَ ويقيس
ما يجب ألّا يُطابَق** (وإلا صار الفحصُ زينةً مرّةً أخرى).

    tools/secret_scan.py --staged        # الأسطرُ **المُضافة** في الفهرس (ما سيصير التزامًا)
    tools/secret_scan.py --text PATH     # فحصُ ملفّ (للضوابط وللاستعمال اليدويّ)

**ولا تُطبع قيمةٌ أبدًا** (القاعدة ١٣): رقمُ السطر واسمُ الصنف فقط.
الرموزُ: `0` نظيف · `1` وُجد سِرّ · `2` تعذّر الفحص ⇒ **فشلٌ مُغلَق** (والخطّافُ يمنع).

والحدُّ المُعلَن: يقرأ **الأسطرَ المُضافة** لا تاريخَ المستودع (ذاك عملُ `publish_guard --history`
وحيّازِ الانكشاف على مرآةٍ كاملة)، ولا يعرف المفاتيحَ المجهولةَ الشكل إلا بنمطِ الإسناد المسمّى.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (اسمُ الصنف، النمط) — الأنماطُ تُطابَق على الأسطر المُضافة وحدها.
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("anthropic", re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}")),
    ("openrouter", re.compile(r"sk-or-v1-[A-Za-z0-9_\-]{16,}")),
    ("openai_project", re.compile(r"sk-proj-[A-Za-z0-9_\-]{16,}")),
    ("openai_legacy", re.compile(r"sk-[A-Za-z0-9]{24,}")),
    ("github_pat", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("aws_access_key", re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
    ("named_assignment",
     re.compile(r"(?i)\b(api[_-]?key|secret|token|passw\w*)\b\s*[:=]\s*[\"'][A-Za-z0-9_./+\-]{24,}[\"']")),
]


def scan_lines(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """يُعيد (رقمُ السطر، اسمُ الصنف) — **بلا قيمة**. أوّلُ صنفٍ يُطابَق لكلّ سطر."""
    hits: list[tuple[int, str]] = []
    for n, text in lines:
        for name, pat in PATTERNS:
            if pat.search(text):
                hits.append((n, name))
                break
    return hits


def _added_lines(diff: str) -> list[tuple[int, str]]:
    """الأسطرُ **المُضافة** مع أرقامها في الملفّ الجديد (رأسُ الـhunk يحدّد الترقيم)."""
    out: list[tuple[int, str]] = []
    n = 0
    for line in diff.splitlines():
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            n = int(m.group(1)) if m else 0
            continue
        if line.startswith("+") and not line.startswith("+++"):
            out.append((n, line[1:]))
            n += 1
        elif not line.startswith("-") and not line.startswith("\\"):
            n += 1
    return out


def staged_diff() -> str:
    r = subprocess.run(["git", "diff", "--cached", "-U0", "--diff-filter=ACMR"],
                       cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200] or "git diff فشل")
    return r.stdout


def _report(hits: list[tuple[int, str]], where: str) -> int:
    if not hits:
        print(f"✓ ماسحُ الأسرار: لا سِرَّ في {where} ({len(PATTERNS)} صنفاً مفحوصاً — بلا طباعةِ قيمة)")
        return 0
    print(f"⛔ ماسحُ الأسرار: {len(hits)} إصابةً في {where} (رقمُ السطر والصنف فقط):")
    for n, name in hits[:10]:
        print(f"   {name} (سطر {n})")
    print("   ⇒ أدِرِ السِرَّ بمتغيّر بيئةٍ أو مديرِ أسرار، ودوِّرْه إن كان قد نُشر.")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ماسحُ الأسرار في الأسطر المُضافة")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true", help="الفهرس (ما سيصير التزامًا)")
    g.add_argument("--text", metavar="PATH", default="", help="ملفٌّ مباشرةً")
    a = ap.parse_args(argv)

    if a.text:
        p = Path(a.text)
        if not p.is_file():
            print(f"⚠ تعذّر الفحص: لا ملفَّ في {a.text} ⇒ **فشلٌ مُغلَق**")
            return 2
        lines = [(i, l) for i, l in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)]
        return _report(scan_lines(lines), a.text)

    try:
        diff = staged_diff()
    except Exception as e:                       # noqa: BLE001 — أيُّ عطبٍ ⇒ لا أمرّ
        print(f"⚠ تعذّر الفحص: {e} ⇒ **فشلٌ مُغلَق** (لا أُعلن نظافةً لم أرها)")
        return 2
    return _report(scan_lines(_added_lines(diff)), "الفهرس")


if __name__ == "__main__":
    raise SystemExit(main())
