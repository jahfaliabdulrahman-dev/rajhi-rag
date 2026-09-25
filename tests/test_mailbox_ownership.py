"""**ملكيّةُ الصندوق ونقلُ الملفّات: قاعدتان ميكانيكيّتان** (مراجعة ٥٢ · R52-5 · القاعدةُ الحديديّة ١).

**العلّةُ التي وُلدتا منها:** ستّةُ تقاريرَ للمنفّذ سكنت `handoff/claude/` (صندوقُ المدقّق) — سادسةُ مرّة —
ومعها **إعادةُ تسميةٍ داخل صندوقه** في `1bb07a8`. والقاعدةُ الحديديّة ١ تقول: «لا أحد يعدّل ملفات الطرف
الآخر ولا يحذفها (append-only)» — ونقلُ ملفٍّ خارجه ليس تعديلًا فحسب، بل **يُنقل شاهدٌ من صندوقه**.

والحرسُ هنا **باسم الملفّ وبسجلّ الالتزامات والمسرَح** لا بالنوايا. و**الاستثناءُ التاريخيُّ يُعلَن باسمه
وسببه** (كما يفعل المستودع في مواضع أخرى) — ويُقاس: استثناءٌ زال سببُه (الملفُّ لم يبقَ) **يُكشف**
ليُزال، وإلا صارت القائمةُ غطاءً دائمًا.
"""
from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLAUDE_BOX = ROOT / "handoff" / "claude"
DECLARATIONS = ROOT / "handoff" / "RENAMES.md"

# استثناءٌ **مُعلَنٌ بسببه** — يُقرأ ويُقاس ولا يُخفى. وملفٌّ لم يبقَ ⇒ الضابطُ يسقط لِيُزال السطر.
DECLARED_INTRUDERS = {
    "20260923-2238-REPORT-to-claude-review-47-closure-and-the-delivery-gate.md":
        "نسخةٌ مكرّرةٌ بايتًا بايتًا (`cmp` = متطابق · 12,052) سكنت صندوقَ المدقّق **قبل** بند ٧ من §١ ⇒ "
        "**لا تُحذف** (القاعدةُ الحديديّة ١: لا يُمسّ ما في صندوق الطرف — والحذفُ نفسه كسرٌ للقاعدة التي "
        "وُلد هذا الضابطُ منها). مُعلَنةٌ لتُقرأ وتُقاس، ونسخةُ المنفّذ القائمةُ في `handoff/sulaiman/` هي المرجع.",
}


def _git(*args: str) -> tuple[int, str]:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.returncode, r.stdout


def test_no_implementer_report_lives_in_the_auditors_box_unless_declared():
    """**صندوقُ المدقّق لأحكامه**: `*REPORT*` في سطحه = تقريرُ المنفّذ في غير صندوقه — إلا ما أُعلن وله سبب.

    ⚠ **ونمطُ الاسم صُحِّح بقياسِ سمّ**: كان `glob("REPORT*")` — وأسماءُ التقارير الحقيقيّة تبدأ بزمن
    (`20260924-0155-REPORT-...`) ⇒ **الحرسُ كان يمرّ والملفُّ في مكانه** (قِيس: ٦/٦ صار ٥/٦). فالمطابقةُ
    الآن على وجود الكلمة في الاسم لا على بدايته. والحرسُ على **سطح الصندوق** (حيث تُوضع الرسائل) لا
    في عُمقه (`audit/`) — وهذا حدُّه المُعلَن، ولا يُدَّعى أوسعَ منه.
    """
    if not CLAUDE_BOX.exists():
        return
    found = sorted(p.name for p in CLAUDE_BOX.iterdir() if p.is_file() and "REPORT" in p.name.upper())
    undeclared = [n for n in found if n not in DECLARED_INTRUDERS]
    assert not undeclared, (
        f"تقاريرُ المنفّذ في صندوق المدقّق (القاعدةُ الحديديّة ١): {undeclared[:6]}\n"
        f"   الصندوقُ الصحيح: `handoff/sulaiman/` — والنقلُ يُعلَن في `handoff/RENAMES.md`")
    stale = [n for n in DECLARED_INTRUDERS if n not in found]
    assert not stale, f"استثناءٌ متقادم (الملفُّ لم يبقَ) ⇒ يُزال من `DECLARED_INTRUDERS`: {stale}"


def _moves() -> set[str]:
    """النقلُ/الحذفُ تحت `handoff/` من **مرجعٍ واحد**: الالتزامات (`base..HEAD`) + المسرَح (`HEAD` ← الآن).

    **ولماذا مرجعٌ واحد لكلّ جهة** (مقعدُ البنية): كان قارئان — `--name-status` للالتزامات، وتقطيعُ
    `porcelain` يدويًّا **عمودًا واحدًا** ⇒ يَعْمى عن `" D old"` (حذفٌ في شجرة العمل) وعن نقلٍ بلا `add`
    (`" D old"` + `"?? new"`)، وهما بالضبط الحالةُ التي وُلد لها. و`git diff --name-status -M HEAD`
    يجمع المسرَحَ كلَّه بكشفِ إعادة تسميةٍ واحد ⇒ لا عمودان ولا محلّلان.
    """
    moved: set[str] = set()
    base = None
    for ref in ("origin/main", "main"):
        rc, _ = _git("rev-parse", "--verify", "--quiet", ref)
        if rc == 0:
            base = ref
            break
    if base is not None:
        _, out = _git("log", "--diff-filter=DR", "--name-status", "-M", "--format=",
                      f"{base}..HEAD", "--", "handoff/")
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0][:1] in ("R", "D"):
                moved.update(parts[1:] if parts[0][:1] == "R" else [parts[1]])
    _, now = _git("diff", "--name-status", "--diff-filter=DR", "-M", "HEAD", "--", "handoff/")
    for line in now.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0][:1] in ("R", "D"):
            moved.update(parts[1:] if parts[0][:1] == "R" else [parts[1]])
    return moved


def test_every_move_or_delete_under_handoff_is_declared():
    """**كلُّ نقلٍ أو حذفٍ مُعلَنٌ بالسبب**: يُقرأ من الالتزامات ومن المسرَح، لا من قائمةٍ بيد."""
    moved = _moves()
    if not moved:
        return                      # لا حركةَ ⇒ لا شيءَ يُعلَن (والضابطُ يُقاس لحظةَ وجودها)
    assert DECLARATIONS.exists(), (
        f"ملفّاتٌ نُقلت أو حُذفت تحت `handoff/` بلا سجلِّ إعلان: {sorted(moved)[:6]}\n"
        f"   أنشئ `handoff/RENAMES.md` (المسار · ماذا · السبب · أُعلن في أيّ مراجعة)")
    declared = DECLARATIONS.read_text(encoding="utf-8")
    undeclared = sorted({m for m in moved if m not in declared})
    assert not undeclared, f"نقلٌ/حذفٌ غيرُ مُعلَن في `handoff/RENAMES.md`: {undeclared}"
