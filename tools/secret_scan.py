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

# ── P-4 · «الرابطُ المُوسَم»: معرّفٌ يدلّ على ما ليس في هذا المستودع (تبنّاه المدقّق في مراجعة ٥٤) ──
# الحادثةُ التي وُلد منها: ثلاثةُ معرّفاتِ التزاماتٍ **ما قبل التنقية** كانت مكتوبةً بأوصافها في ملفٍّ
# مُتتبَّع ⇒ صارت «رابطاً موسوماً» إلى ما لم يُطهَّر. والقاعدةُ الميكانيكيّة: **معرّفٌ لا وجودَ له في
# رسم هذا المستودع = إشارةٌ إلى خارجه**. وحدُّه الذي طلبه المدقّق: يُطبع **الملفُّ والسطرُ فقط، لا المعرّف**
# (سجلّاتُ CI في مستودعٍ عامٍّ عامّةٌ أيضاً).
HEXISH = re.compile(r"\b[0-9a-f]{10,40}\b")
#: **سياقُ التزامٍ لا سياقُ هاش** (R55-3): كلمةُ `sha` وحدها جعلت `spec_sha`/`sha256` تُعامل معرّفاتِ التزامٍ
#: غريبة — والبصمةُ هاشُ ملفٍّ **لا يوجد في git أبداً** ⇒ إيجابٌ كاذبٌ يُغلق البوّابةَ على النثر المشروع
#: (والدليلُ الحيّ: الخطّافُ أوقف التزامَ مراجعة المدقّق على سطرين يقتبسان بصمةَ حزمة الأسئلة، بلا أيّ
#: معرّفِ التزام). ⇒ السياقُ صار **خاصّاً بالالتزام**، ويُستثنى ما كان قيمةَ حقلِ هاشٍ بنصِّه.
ID_CONTEXT = re.compile(r"(?i)(sha|commit|\u0627\u0644\u062a\u0632\u0627\u0645|revision|\brev\b|/commit/)")
#: الاستثناءُ **باسم حقلِ هاشٍ صريح** لا بكلمةٍ عامّة (R55-3 بحدّه الصحيح): تسعةُ صيغٍ نثريّة قِيست فورودُ
#: `hash` وحدها كان يبتلع `commit hash <id>` — وهي إحالةٌ صريحة. فالضابطُ الواحد: اسمُ حقلٍ صريح + فاصلٌ،
#: وإلّا فالقيمةُ تُكتشَف. (المبدأ: الدقّةُ لا تُشترى بالقدرة — و«لا اكتشافَ» أخطرُ من ضجيجٍ يُراجَع.)
HASH_FIELD = re.compile(r"(?i)\b(sha256|sha1|sha512|md5|checksum|content_sha|spec_sha|hashsum|digest)\b[\"'`*=:\s]*$")


def _looks_like_id(tok: str) -> bool:
    """٤٠ خانةً دائماً · أو أقلُّ بشرطِ **حرفٍ** سِتّ عشريّ (فيمنع سلاسلَ الأرقام الطويلة كسلاسل العائم)."""
    if not (10 <= len(tok) <= 40):
        return False
    return len(tok) == 40 or bool(re.search(r"[a-f]", tok))


def _exists_in_repo(tok: str) -> bool:
    r = subprocess.run(["git", "cat-file", "-e", tok], cwd=str(ROOT), capture_output=True)
    return r.returncode == 0


def _is_shallow() -> bool:
    r = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=str(ROOT), capture_output=True, text=True)
    return r.stdout.strip() == "true"


def scan_foreign_ids(lines: list[tuple[int, str]], exists=_exists_in_repo) -> list[tuple[int, str]]:
    """(رقمُ السطر، اسمُ الصنف) — **بلا المعرّف**: يكفي أنّ السطرَ يحمل معرّفاً غريباً."""
    hits: list[tuple[int, str]] = []
    for n, text in lines:
        if not ID_CONTEXT.search(text):
            continue                             # سياقٌ صريح يخصّ الالتزام: يقلّل الإيجابيّات الكاذبة
        for match in HEXISH.finditer(text):
            tok = match.group(0)
            if not _looks_like_id(tok) or exists(tok):
                continue
            if HASH_FIELD.search(text[:match.start()]):
                continue                         # قيمةُ حقلِ هاش (sha256/spec_sha) ليست كائنَ git
            hits.append((n, "foreign_commit_id"))
            break
    return hits

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


def _report(hits: list[tuple[int, str]], where: str, kind: str = "secret") -> int:
    if kind == "id":
        if not hits:
            print(f"✓ المعرّفات: لا معرّفَ غريباً في {where} (وُجودُ كلّ معرّفٍ مُتحقَّقٌ منه في هذا المستودع)")
            return 0
        print(f"⛔ المعرّفات: {len(hits)} سطراً يحمل معرّفاً **لا وجودَ له في هذا المستودع** في {where} "
              "(رقمُ السطر فقط — ولا يُطبع المعرّف):")
        for n, name in hits[:10]:
            print(f"   {name} (سطر {n})")
        print("   ⇒ معرّفٌ غريبٌ = إشارةٌ إلى كائنٍ خارجَ هذا المستودع (وهو صنفُ «الرابط المُوسَم»)."
              " أزلْه أو أعلِنه من مصدرٍ غيرِ مُتتبَّع.")
        return 1
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

    if _is_shallow():
        print("⚠ تعذّر فحصُ المعرّفات الغريبة: نسخةٌ ناقصةُ العمق (`--is-shallow-repository` = true) "
              "⇒ **فشلٌ مُغلَق** (كائنٌ قد يكون موجوداً بعيداً يُقرأ غريباً)")
        return 2

    if a.text:
        p = Path(a.text)
        if not p.is_file():
            print(f"⚠ تعذّر الفحص: لا ملفَّ في {a.text} ⇒ **فشلٌ مُغلَق**")
            return 2
        lines = [(i, l) for i, l in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)]
        rc = _report(scan_lines(lines), a.text)
        return max(rc, _report(scan_foreign_ids(lines), a.text, kind="id"))

    try:
        diff = staged_diff()
    except Exception as e:                       # noqa: BLE001 — أيُّ عطبٍ ⇒ لا أمرّ
        print(f"⚠ تعذّر الفحص: {e} ⇒ **فشلٌ مُغلَق** (لا أُعلن نظافةً لم أرها)")
        return 2
    lines = _added_lines(diff)
    rc = _report(scan_lines(lines), "الفهرس")
    return max(rc, _report(scan_foreign_ids(lines), "الفهرس", kind="id"))


if __name__ == "__main__":
    raise SystemExit(main())
