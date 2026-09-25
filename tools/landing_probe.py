#!/usr/bin/env python3
"""**مسبارُ الهبوط (P-11)** — يقيس الثابتَ الذي انكسر ثلاثَ مرّات: **«هل تهبط مراجعة؟»**

**العلّةُ التي وُلد منها** (مراجعة ٥٩ · القرارُ بتأييد المالك): R57-1 (حارسُ المكان) ثم R58-1 (عدّادُ
الكشيدة) ثم R59-1 (ضابطُ مواضع النثر) — **ثلاثةُ إصلاحاتٍ للصنف نفسه**: في كلّ مرّةٍ كان **نصُّ المدقّق
مُدخَلاً إلى راتشتٍ يملكه المنفّذ**، فمجردُ اقتباسِ صيغةٍ في مراجعةٍ تهبط يُحمرّ الـCI. ولم يُمسكها مقعدٌ
من الثلاثة في أيّ جولة، وأمسكتها **محاكاةُ الهبوط بيدٍ** في كلّ مرّة. فهذه الأداةُ تُؤتمت تلك المحاكاة.

**كيف يقيس** — يبني **نسخةً مؤقّتةً** من الشجرة، ويُودِع فيها **مراجعةً اصطناعيّة** تحت `handoff/claude/`
بزمن اللحظة، تحمل في نصٍّ واحد كلَّ ما تصطاده العدّادات (انظر `_synthetic_review`)، ثم يُشغّل **قائمةَ
الـCI** هناك. والقائمةُ تُقرأ من ملفّ الـworkflow نفسِه (`.github/workflows/publish-guard.yml`) ⇒
**مصدرٌ واحد** لا قائمةُ نسخٍ ثانية تتقادم.

    tools/landing_probe.py                  # يقيس الشجرةَ المُودَعة (`HEAD`)
    tools/landing_probe.py --from-worktree   # يقيس شجرةَ العمل (التغييراتُ غيرُ المُودَعة تُودَع في النسخة)
    tools/landing_probe.py --list            # يطبع ما سيقيسه (القائمةُ والخطوات) بلا نسخٍ ولا تشغيل
    tools/landing_probe.py --poison NAME     # يُسمّم المراجعةَ الاصطناعيّة (إثباتُ عضٍّ بلا شجرةٍ معطوبة)
    tools/landing_probe.py --keep            # يُبقي النسخةَ المؤقّتة للمعاينة

**رموزُ الخروج:** `0` = المراجعةُ تهبط · `1` = الهبوطُ كسر شيئاً (يُسمّى) · `2` = **تعذّر القياس**
(فشلٌ مُغلَق: لا نسخةَ · لا pytest · لا قائمةَ مقروءة — ولا يُقرأ التعذّرُ نظافةً).

**وحدودُه مُعلَنة** (ولا تُدَّعى أوسعَ منها):
- **ما يُقاس:** قائمةُ ضوابط الـCI (مقروءةٌ من الـworkflow) + `publish_guard --tree --ci`.
- **ما لا يُقاس:** `publish_guard --history` (التاريخُ لا يتغيّر بهبوط نصّ · وهو ثقيل)، وبوّاباتُ
  المال/الثوابت/اللقطة على خطوات الـworkflow (تقرأ الشيفرةَ لا صندوقَ المراسلة)، و«هل المراجعةُ
  الاصطناعيّةُ تشبه مراجعةً حقيقيّةً بالكامل» — الشكلُ متّفقٌ عليه بين الطرفَين (شرطُ المدقّق نفسه).
- **والمقيسُ شجرةٌ مُودَعة**: `--from-worktree` يُودِع شجرةَ العمل في النسخة (للمسح والسموم).
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
#: مسارُ الـworkflow **نسبةً إلى جذر الشجرة** — فيُقرأ من الشجرة التي تُقاس لا من شجرة المنفّذ دائمًا.
WORKFLOW_REL = Path(".github") / "workflows" / "publish-guard.yml"
WORKFLOW = PROJ / WORKFLOW_REL
DESCRIPTION = "مسبارُ الهبوط (P-11): هل تهبط مراجعةٌ تحت قائمة الـCI؟"
#: صندوقُ المدقّق — المراجعةُ الاصطناعيّةُ تسكنه (وهو موضعُ المراجعات الحقيقيّة).
BOX = "handoff/claude"
#: الصيغةُ التي أُدخل بها نصُّ المدقّق إلى الراتشت (كشيدةٌ + `sha`) — تُبنى ولا تُكتب حرفًا حرفًا هنا
#: (القاعدةُ ١٢: القيمةُ تُغيَّر لا الموضعُ يُعفى — وهذه ليست قيمةً ماليّةً بل صيغةَ كشف).
TATWEEL = "\u0640"
#: قائمةُ الـCI: **تُقرأ من الـworkflow** لا من نسخةٍ ثانية (وتُرتيبُ ورودها محفوظ).
CI_FILE_RE = re.compile(r"tests/[A-Za-z0-9_/]+\.py")


def ci_files(workflow: Path = WORKFLOW) -> list[str]:
    """ملفّاتُ ضوابط الـCI بترتيب ورودها في الـworkflow — **مصدرٌ واحد، ومن الشجرة المقيسة نفسِها**.

    القارئُ يمرّر `dst / WORKFLOW_REL` (جذرُ النسخة) فيُقرأ الـworkflow من الشجرة التي تُقاس. ولماذا:
    كانت القائمةُ تُقرأ من شجرة المنفّذ دائمًا، فأوّلُ تشغيلٍ بعد إضافة ضابطٍ جديد (وغيرِ مُودَعٍ بعد)
    قاس **نسخةً مُودَعة** بقائمةٍ محلّيّةٍ تحمل الملفَّ الغائب ⇒ «تعذّر قياس» كاذب، وقع في سمّ م٢١
    (`tests/test_landing_probe.py` يقيس الأثر: القائمةُ تتبع الشجرةَ التي تُشار إليها).

    (وفشلٌ مُغلَق: workflow غائبٌ أو بلا ملفّات ⇒ `[]`، والقارئُ يوقف القياسَ بالاسم لا يعلن نظافة.)
    """
    if not workflow.exists():
        return []
    text = workflow.read_text(encoding="utf-8")
    seen: dict[str, None] = {}
    for m in CI_FILE_RE.finditer(text):
        seen.setdefault(m.group(0), None)
    return list(seen)


def tree_steps() -> list[tuple[str, list[str]]]:
    """خطواتُ الـCI التي تقرأ **الشجرةَ والنصّ** (وهي التي يمسّها هبوطُ نصّ) — غيرُ قائمة الضوابط."""
    return [("publish_guard --tree --ci", ["tools/publish_guard.py", "--tree", "--ci"])]


def _run(cmd: list[str], cwd: Path, env: dict | None = None) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                       env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _git(repo: Path, *args: str, env: dict | None = None) -> tuple[int, str]:
    return _run(["git", *args], repo, env=env)


# ── بناءُ النسخة ────────────────────────────────────────────────────────────
def _clone(src: Path, dst: Path, ref: str, branch: str | None) -> tuple[int, str]:
    """نسخةٌ كاملةُ التاريخ (بلا `--depth`: الضوابطُ تقرأ `git ls-tree` والالتزامات) و**فرعٌ واحد**.

    وفرعٌ واحد عن قصد: نسخةٌ تحمل كلَّ فروع المالك المحلّيّة تُسقط `publish_guard --history` لأسبابٍ
    لا علاقةَ لها بهبوط المراجعة ⇒ فتكون النسخةُ حمراءَ دائمًا فيصير المسبارُ ضجيجًا (ومنبَّهَ كاذبًا).
    """
    args = ["clone", "--no-hardlinks", "--quiet", "--single-branch"]
    if branch:
        args += ["--branch", branch]
    rc, out = _git(PROJ, *args, str(src), str(dst))
    if rc != 0:
        return rc, out
    return _git(dst, "checkout", "--quiet", "--detach", ref)


def _copy_worktree(src: Path, dst: Path) -> tuple[int, str]:
    """يُودِع شجرةَ العمل في النسخة: **ما يراه `git add -A`** (متتبَّعٌ بمحتواه الحاليّ + جديدٌ غيرُ مُهمَل).

    ولا نسخَ للمُهمَل (`data/` الثقيلة · `.venv`) لأنّه لا يُلتزَم أصلًا — فالمقيسُ هو ما يُودَع لا
    ما على القرص. والحذفُ في شجرة العمل يُحذَف في النسخة (وإلّا قِيس ملفٌّ زائلٌ كأنّه قائم).
    """
    rc, listed = _git(PROJ, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if rc != 0:
        return rc, listed
    paths = [p for p in listed.split("\0") if p]
    for rel in paths:
        s, d = src / rel, dst / rel
        if not s.exists():
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
    rc_del, deleted = _git(PROJ, "ls-files", "-z", "--deleted")
    if rc_del == 0:
        for rel in [p for p in deleted.split("\0") if p]:
            (dst / rel).unlink(missing_ok=True)
    return _git(dst, "add", "-A")


# ── المراجعةُ الاصطناعيّة ───────────────────────────────────────────────────
#: نصوصُ السمّ: كلٌّ منها يجعل المراجعةَ **لا تهبط** بطريقةٍ مختلفة — فيجب أن يمسكها الـCI.
#: (ولا يُعلَن سمٌّ بلا تنفيذ: ما دام غيرَ مُنفَّذٍ في `_name`/`_synthetic_review` فهو ليس سمًّا — بل وعدًا.)
POISONS = {
    "name-stamp": "زمنُ الاسم منزاحٌ ٣ ساعات عن زمن الإيداع ⇒ ضابطُ أسماء التقارير يجب أن يسقط",
}


def _synthetic_review(stamp: str, ref: str, branch: str, poison: str | None) -> str:
    """**مراجعةٌ اصطناعيّة** بزمن اللحظة — فيها كلُّ ما تصطاده العدّادات في نصٍّ واحد.

    ومكوّناتُها من قائمة مراجعة ٥٩ نفسِها (لا تُختار بالذوق): صيغةُ الكشيدة · «N سطراً في M ملفّ» ·
    سطرُ `status:` في المتن · سطرُ `in-reply-to:` مقتبَسًا · كلمةُ REPORT · ومعرّفُ التزامٍ غريب
    (لأنّ المراجعات الحقيقيّة تحمل `commit:`). والمراجعةُ **حُكمٌ** لا جوابًا: اسمها وصندوقُها من
    صندوق المدقّق، ولا تشهد لنفسها.
    """
    foreign = "e903b12"          # معرّفُ التزامٍ ذكرته مراجعة ٥٩ (خارج رسم المستودع الحاليّ)
    form = f"الـ{TATWEEL}sha"    # الصيغةُ التي أُدخل بها نصُّ المدقّق إلى الراتشت ثلاثَ مرّات
    lines = [
        "```",
        f"id:      {stamp}-claude",
        "from:    claude",
        "to:      sulaiman",
        "type:    REVIEW",
        "step:    مراجعة ٩٩ — مسبارُ الهبوط (P-11): نصٌّ اصطناعيٌّ يقيس أنّ المراجعةَ تهبط",
        f"commit:  {ref} (`{branch}`) — CI publish-guard SUCCESS",
        "verdict: REQUEST CHANGES — مسبارُ هبوطٍ اصطناعيّ (لا يُقاس عليه عملٌ حقيقيّ)",
        "next:    لا شيء — هذه مراجعةٌ مصنوعةٌ للمسبار",
        "```",
        "",
        "## Verdict — الحكم",
        "",
        "هذا النصُّ **يُشبه مراجعةً حقيقيّةً** عن قصد: فيه ما حملته مراجعاتُ ٥٦–٦٠ بالحرف.",
        "والغرضُ أنّ قائمةَ الـCI تبقى خضراءَ بعد أن يُودَع — وإن احمرّت، فالثابتُ («هل تهبط مراجعة؟») مكسور.",
        "",
        f"- **R99-1** الصيغةُ في نثر المدقّق: «{form} {foreign}» — السطرُ نفسه في أربع مراجعات.",
        "  وقِيس أنّ الشجرةَ كلَّها تعطي **27 سطراً في 16 ملفّاً** بهذه الصيغة (رقمٌ يُقرأ بتاريخه).",
        f"  ومعرّفٌ غريبٌ ثانٍ للنصّ: `commit {foreign}` — المرجعُ غريبٌ عن رسم هذا المستودع.",
        "",
        "status: مسبارٌ اصطناعيٌّ — لا يُقرأ حكمًا على أحد",
        "",
        "## المقتبَس (كما تقتبس المراجعاتُ الحقيقيّة)",
        "",
        "```",
        "in-reply-to: handoff/sulaiman/20260925-2000-REPORT-to-claude-probe.md",
        "status: AWAITING_FOUNDER",
        "```",
        "",
        "وهذا تقريرٌ مصنوعٌ يحمل كلمة REPORT داخل متنه (لا في اسمه) — كما تحملها تقاريرُ المنفّذ.",
        "",
        "## Not proven — ما لم يُثبت",
        "",
        "- أنّ هذا الشكلَ يغطّي كلَّ صيغةٍ يرتّش عليها الـCI مستقبلًا: يُوسَّع بالاتّفاق بين الطرفَين.",
    ]
    if poison == "name-stamp":
        # الاسمُ يُصاغ في `_name` — وهنا نُعلن أنّ الزمنَ المقصودَ منزاحٌ (يُقرأ في الموضعين).
        lines.insert(1, "# ⚠ سمُّ `name-stamp`: زمنُ الاسم منزاحٌ عن زمن الإيداع ⇒ يُمسَك بضابط الأسماء")
    return "\n".join(lines) + "\n"


def _name(stamp: str, poison: str | None) -> str:
    """اسمُ الملفّ — بزمنه في مقدّمته (قاعدةُ أسماء التقارير)، وبلا كلمة REPORT في الاسم."""
    if poison == "name-stamp":                      # زمنُ اسمٍ منزاحٌ ٣ ساعات ⇒ يجب أن يسقط ضابطُ الأسماء
        shifted = datetime.fromisoformat(f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T"
                                         f"{stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}")
        shifted = (shifted - timedelta(hours=3)).strftime("%Y%m%d-%H%M%S")
        return f"{shifted}-third-eye-review-99-landing-probe.md"
    return f"{stamp}-third-eye-review-99-landing-probe.md"


def _commit(review: Path, dst: Path, stamp: str) -> tuple[int, str]:
    """يُودِع المراجعةَ في النسخة بزمن اللحظة (مؤلفٌ ومُودِع) — فاسمُها يطابق إيداعَها.

    والزمنُ من **مصدرٍ واحد** (`stamp` نفسُه الذي في الاسم) ⇒ لا ساعتان تفترقان.
    """
    when = datetime.fromisoformat(f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T"
                                  f"{stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}").astimezone()
    env = {"GIT_AUTHOR_DATE": when.isoformat(), "GIT_COMMITTER_DATE": when.isoformat(),
           "GIT_AUTHOR_NAME": "landing-probe", "GIT_AUTHOR_EMAIL": "probe@invalid",
           "GIT_COMMITTER_NAME": "landing-probe", "GIT_COMMITTER_EMAIL": "probe@invalid"}
    rc, out = _git(dst, "add", str(review.relative_to(dst)), env=env)
    if rc != 0:
        return rc, out
    return _git(dst, "commit", "--quiet", "-m",
                "probe: مراجعةٌ اصطناعيّةٌ تقيس أنّ المراجعةَ تهبط (P-11)", env=env)


# ── القياس ─────────────────────────────────────────────────────────────────
def _pytest_ready(py: str) -> bool:
    return subprocess.run([py, "-c", "import pytest"], capture_output=True).returncode == 0


def measure(ref: str, from_worktree: bool, poison: str | None, keep: bool,
            quiet: bool = False) -> int:
    files = ci_files()
    steps = tree_steps()
    if not files:
        print(f"⛔ تعذّر القياس: لا قائمةَ ضوابط في {WORKFLOW.relative_to(PROJ)} ⇒ فشلٌ مُغلَق.")
        return 2
    py = sys.executable
    if not _pytest_ready(py):
        print(f"⛔ تعذّر القياس: `{py}` بلا pytest ⇒ لا شهادةَ (والـCI يُثبّته قبل هذه الخطوة).")
        return 2
    branch = _git(PROJ, "rev-parse", "--abbrev-ref", "HEAD")[1].strip()
    sha = _git(PROJ, "rev-parse", ref)[1].strip()
    if not sha:
        print(f"⛔ تعذّر القياس: المرجعُ `{ref}` غيرُ موجود ⇒ لا نسخةَ تُقاس.")
        return 2
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    tmp = Path(tempfile.mkdtemp(prefix="landing-probe-"))
    dst = tmp / "tree"
    try:
        rc, out = _clone(PROJ, dst, sha, branch)
        if rc != 0:
            print(f"⛔ تعذّر القياس: فشلُ بناء النسخة عند {sha[:12]}:\n{out.strip()[:600]}")
            return 2
        if from_worktree:
            rc, out = _copy_worktree(PROJ, dst)
            if rc != 0:
                print(f"⛔ تعذّر القياس: فشلُ نسخ شجرة العمل:\n{out.strip()[:600]}")
                return 2
        # **والقائمةُ تُقرأ من الشجرة المقيسة** (لا من شجرة المنفّذ): فقياسُ نسخةٍ مُودَعةٍ بقائمةٍ محلّيّة
        # تحمل ضابطًا لم يُودَع بعد = «تعذّر قياس» كاذب — أمسكه سمُّ م٢١ في أوّل تشغيلٍ بعد إضافة ضابط.
        files = ci_files(dst / WORKFLOW_REL)
        if not files:
            print(f"⛔ تعذّر القياس: النسخةُ لا تحمل قائمةَ ضوابط في {WORKFLOW_REL} ⇒ فشلٌ مُغلَق.")
            return 2
        box = dst / BOX
        box.mkdir(parents=True, exist_ok=True)
        name = _name(stamp, poison)
        review = box / name
        review.write_text(_synthetic_review(stamp, sha[:7], branch, poison), encoding="utf-8")
        rc, out = _commit(review, dst, stamp)
        if rc != 0:
            print(f"⛔ تعذّر القياس: لم يُودَع الشاهدُ في النسخة:\n{out.strip()[:600]}")
            return 2
        print(f"[landing-probe] النسخة: {dst} · الشجرة: {sha[:12]} · الحالة: "
              f"{'شجرةُ العمل' if from_worktree else 'المُودَعة'} · الشاهد: {BOX}/{name}"
              + (f" · **سمّ: {poison}**" if poison else ""))
        failures: list[str] = []
        # ① خطواتُ الشجرة (تقرأ النصَّ والصندوق مباشرةً)
        for label, argv in steps:
            rc, out = _run([py, *argv], dst)
            tail = out.strip().splitlines()[-1][:160] if out.strip() else ""
            print(f"  {'✓' if rc == 0 else '✗'} {label}  (rc={rc})" + (f" — {tail}" if rc else ""))
            if rc != 0:
                failures.append(f"{label} (rc={rc}) — {tail}")
        # ② قائمةُ ضوابط الـCI (مقروءةٌ من الـworkflow)
        rc, out = _run([py, "-m", "pytest", "-q", *files], dst)
        print(f"  {'✓' if rc == 0 else '✗'} قائمةُ الـCI: {len(files)} ملفّاً  (rc={rc})")
        if rc != 0:
            named = [ln.strip() for ln in out.splitlines() if ln.strip().startswith(("FAILED", "ERROR"))]
            if not quiet:
                for ln in named[:12]:
                    print(f"      {ln}")
            failures.append(f"قائمةُ الـCI: {len(named) or '?'} سقوطاً"
                            + (" — " + " · ".join(named[:4]) if named else ""))
        if failures:
            print(f"[landing-probe] ✗ **المراجعةُ لم تهبط** ({len(failures)} خطوةً):")
            for f in failures:
                print(f"    - {f}")
            return 1
        print("[landing-probe] ✓ المراجعةُ هبطت: الخطواتُ وقائمةُ الـCI خضراءُ على شجرةٍ تحملها.")
        return 0
    finally:
        if keep:
            print(f"[landing-probe] أُبقيت النسخةُ للمعاينة: {dst}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=DESCRIPTION)
    ap.add_argument("--ref", default="HEAD", help="المرجعُ الذي تُقاس شجرتُه (افتراضاً: HEAD)")
    ap.add_argument("--from-worktree", action="store_true", dest="from_worktree",
                    help="يُودِع شجرةَ العمل في النسخة (تغييراتٌ غيرُ مُودَعة · للمسح والسموم)")
    ap.add_argument("--poison", choices=sorted(POISONS), default=None,
                    help="يُسمّم المراجعةَ الاصطناعيّة (إثباتُ عضٍّ: يجب أن يسقط)")
    ap.add_argument("--list", action="store_true", help="يطبع ما سيقيسه بلا نسخٍ ولا تشغيل")
    ap.add_argument("--keep", action="store_true", help="يُبقي النسخةَ المؤقّتة")
    ap.add_argument("--quiet", action="store_true", help="لا يُطبع أسماءُ الضوابط الساقطة")
    args = ap.parse_args(argv)
    files, steps = ci_files(), tree_steps()
    if args.list:
        print(f"قائمةُ الـCI ({len(files)} ملفّاً · مقروءةٌ من {WORKFLOW.relative_to(PROJ)}):")
        for f in files:
            print(f"  - {f}")
        print("خطواتُ الشجرة:")
        for label, argv in steps:
            print(f"  - {label}   ({' '.join(argv)})")
        print("السموم المُتاحة: " + " · ".join(f"`{k}` ({v})" for k, v in POISONS.items()))
        print(f"صندوقُ الشاهد: {BOX}/ · الاسمُ بصيغة {_name('YYYYMMDD-HHMMSS', None)}"
              " · ويُشغَّل على شجرةٍ مُودَعة، والقياسُ بلا شبكة")
        return 0
    return measure(args.ref, args.from_worktree, args.poison, args.keep, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
