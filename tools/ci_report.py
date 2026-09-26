#!/usr/bin/env python3
"""مُدقِّقُ CI لكلِّ ما دُفع — «ولا يُقال أخضرُ بلا دليل» (مراجعة ٦١ · R61-1 «ملحقُ الدفع»).

ملحقُ دفعِ الجولة ٦١ ادّعى «CI ناجح» بنطاقٍ **أضيقَ من الدفع**: قِيس مرجعٌ واحدٌ من خمسة، وفرعان
من فروع المدقّق المدفوعة كانتا **حمراوين** ولم يذكرهما التقرير. والصنفُ ليس سهواً في جملة، بل
**ادّعاءٌ بلا موضعِ قياس** — فلا يُصلحه وعدٌ بأن أتذكّر، بل أداةٌ تُنتج الموضع:

* نتيجةُ CI **لكلِّ مرجعٍ دُفع**، لا لمرجعٍ واحد.
* **مقيسةً على التزامه هو** — فتشغيلٌ أخضرُ لالتزامٍ قديمٍ لا يُبرّئ رأساً جديداً (درسُ §٢٧:
  «وإن كانت مدفوعةً فعلًا فتحقّق أنّ `origin/main` هو الالتزامُ المقصود لا مرجعاً متقادماً»).
* وتخرج بغير صفر إن كان مرجعٌ أحمرَ أو جارياً أو **بلا تشغيل** أو **غيرَ مقروء** — فغيابُ القياس
  ليس نظافةً (القاعدة: «غيرُ المقروء ليس نظيفاً»). وغيابُ `headSha` من خرج `gh` **فشلٌ مُغلَق**:
  حُكمٌ بلا مرساةٍ ليس حكماً.

    python3 tools/ci_report.py chore/round56-evidence claude/review-56
    python3 tools/ci_report.py --json <ref>...        # للسجلّ في تقرير الدفع (stdout = JSON وحده)

رموزُ الخروج: 0 = كلُّ مرجعٍ أخضرُ على التزامه · 1 = مرجعٌ ليس أخضر (يُسمّى) · 2 = تعذّر القياس.
**استثناءٌ واحدٌ معلَن:** `--pre-push` (تذكيرُ الخطّاف) يخرج **صفراً دائماً** ولا يمسّ الشبكة —
فخطّافٌ يُسقط دفعاً مشروعاً يُصنع به حافزُ `--no-verify` الذي يُسقط حرّاسَ الأمن.

حدُّ هذا الفحص: يقيس **نتيجةَ تشغيلٍ على GitHub** لا صحّةَ الشجرة — الشجرةُ تقيسها البوّاباتُ
والاختبارات، وهذه الأداةُ تقيس **صدقَ ما يُكتب في تقرير الدفع**، فلا هي تُصلح عطباً ولا هي تُخفيه.
وكذلك لا يقيس **وجوبَ** حملِ تقرير الدفع لمخرَجها: الحاملُ بشريٌّ يذكّره `pre-push` — وهذه قاعدةٌ
مُعلَنة لا بوّابة (وفي المستودع موضعٌ يقيس أسماءَ التقارير لا مضمونَها).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
GREEN = "success"


def _run(cmd: list[str]) -> tuple[int, str]:
    """نداءٌ خارجيّ واحد — نقطةٌ واحدةٌ تُستبدَل في الضوابط."""
    try:
        r = subprocess.run(cmd, cwd=str(PROJ), capture_output=True, text=True)
    except OSError as e:                       # `gh` غيرُ مثبَّتٍ أو غيرُ قابلٍ للتنفيذ
        return 127, str(e)
    out = (r.stdout or "").strip() or (r.stderr or "").strip()
    return r.returncode, out


def _gh(args: list[str]) -> tuple[int, str]:
    return _run(["gh", *args])


def _local_sha(ref: str) -> str | None:
    rc, out = _run(["git", "rev-parse", ref])
    return out if rc == 0 and out else None


def _pushed_sha(ref: str, remotes_list: "list[str] | None" = None) -> str | None:
    """**الالتزامُ الذي دُفع فعلًا** لا الذي في يدي: `<remote>/<branch>` أوّلًا (والمرجعُ يُطبَّع).

    (تصحيحٌ بعد قياسٍ حيّ: كان القياسُ على المرجع المحلّيّ، وفرعٌ محلّيٌّ متقدّمٌ على المدفوع
    يُوسَم «قديمًا» وهو **أحمرُ** في الحقيقة ⇒ وسمٌ مضلِّل. المقصودُ صدقُ تقرير الدفع،
    وتقريرُ الدفع يتكلّم عن **المدفوع**.)

    **وقياسٌ ثانٍ (إغلاقُ ملاحظة الجولة ٦٤):** كان يُبنى `origin/{ref}` **بلا تطبيع**، فمرجعٌ
    بصيغة git (`refs/heads/main`) يُنتج `origin/refs/heads/main` (لا وجودَ له) ⇒ يسقط إلى
    **المرجع المحلّيّ** فيُوسَم الرأسُ المدفوع «قديمًا» **كذبًا**. فصار المسارُ: `branch_of(ref)`
    أوّلًا، ثم يُجرَّب **كلُّ ريموتٍ مُهيَّأ** (`git remote`) لا `origin` وحدَه.

    **والقائمةُ تُمرَّر لا تُخزَّن:** `main` يسأل `remotes()` مرّةً واحدةً ويُمرّرها هنا (قِيس: ٤ نداءاتِ
    `git remote` لمرجعٍ واحد قبل ذلك ⇒ ١ للتشغيل كلّه بعده) — فالتخزينُ العالميُّ كان يُبطل سِمَةَ
    `_run` المُعلَنة، والمعامَلُ يُعطي الوحدةَ نفسَها بلا حالةٍ خفيّة.
    """
    branch = branch_of(ref, remotes_list)
    for remote in (remotes_list or remotes()):
        pushed = _local_sha(f"{remote}/{branch}") if branch else None
        if pushed:
            return pushed
    return _local_sha(branch or ref)


FALLBACK_REMOTES = ("origin", "upstream")      # حين يتعذّر سؤالُ git (يُعلَن ولا يُخفي)


def _git_remotes() -> str:
    """سطرٌو `git remote` الخامّ — نقطةُ نداءٍ واحدة تُستبدَل في الضوابط.

    **وبلا تخزين — بقرارٍ مقيس:** أُدخِل تخزينٌ (`lru_cache`) في محاولةٍ أولى فردّه مقعد البنية بقياس:
    بعد نداءٍ حقيقيّ يصبح تبديلُ `_run` — وهو النمطُ الذي يُعلنه هذا الملفّ نفسُه على أنّه **نقطةُ
    الاستبدال الوحيدة** — **بلا أثر** (قِيس: `remotes()` تُعيد `['origin']` والمتوقَّع `['upstream']`)،
    فحالةٌ عالميّةٌ خفيّةٌ بلا مُبطِل تُبطل السِّمَةَ المُعلَنة. **والحلُّ نقلُ الوحدة إلى المعامَل:**
    `main` يسأل مرّةً واحدةً ويمرّر القائمة، والدالّةُ تبقى طازجةً لكلّ نداءٍ مباشر.
    """
    rc, out = _run(["git", "remote"])
    return out if rc == 0 else ""


def remotes() -> list[str]:
    """**أسماءُ الريموتات المُهيَّأة** (يُسأل git — لا قائمةٌ مغلقة بيد).

    (قِيس في مقعد المعايير: قائمةٌ مغلقةٌ (`origin/` · `upstream/`) تُمرّر أيَّ اسمِ ريموتٍ آخر
    **بلا تحويل** ⇒ `BLOCK` الكاذبُ نفسُه يعود في ذلك الشكل.)
    """
    names = [line.strip() for line in (_git_remotes() or "").splitlines() if line.strip()]
    return names or list(FALLBACK_REMOTES)


def branch_of(ref: str, remotes_list: "list[str] | None" = None) -> str:
    """**اسمُ الفرع** من مرجعٍ كما يكتبه git: `origin/main` ⇒ `main` (و`refs/heads/x` ⇒ `x`).

    (قِيس بعد إغلاق ملاحظة الجولة ٦٤: `gh run list --branch origin/main` يُعيد لا شيء ⇒ «بلا تشغيل»
    ⇒ `BLOCK` **كاذبٌ** على مرجعٍ له تشغيلٌ أخضرُ باسمه الحقيقيّ. والمرجعُ يُقبل بالصيغتين،
    والتحويلُ إلى اسم الفرع في موضعٍ واحد — **وأسماءُ الريموتات تُسأل git** لا تُكتب بيد.)
    """
    name = (ref or "").strip()
    if name.startswith("refs/heads/"):
        return name[len("refs/heads/"):]
    if name.startswith("refs/remotes/"):
        name = name[len("refs/remotes/"):]
    for remote in (remotes_list if remotes_list is not None else remotes()):
        prefix = remote.rstrip("/") + "/"
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def _same_commit(a: str, b: str) -> bool:
    n = min(len(a), len(b), 12)
    return n >= 7 and a[:n] == b[:n]


def parse_pushed_refs(text: str) -> tuple[list[str], int, int]:
    """مراجعُ الفروع التي **دُفعت**، من سطور خطّاف `pre-push`: (مراجع · ليس فرعاً · حذف).

    صيغةُ السطر: `<local ref> <local sha> <remote ref> <remote sha>`. **والحقلُ الأوّل ليس
    مرجعاً دائماً** — مقيسٌ من git نفسِه (لا من ظنّ؛ انظر أدناه) — والقصدُ **وجهةُ الدفع** في
    الحقل الثالث، فمنه يُقرأ:

    * `refs/heads/main <sha> refs/heads/main 000…`   — تحديثُ فرع (والأصفارُ في الرابع تعني «الوجهةُ بلا مرجع» لا حذفاً).
    * `refs/tags/v1 <sha> refs/tags/v1 000…`         — وسمٌ ⇒ ليس فرعاً (يُعَدّ ويُعلَن ولا يُقاس عليه).
    * `(delete) 000… refs/heads/old <sha>`           — حذفُ مرجع ⇒ لا تشغيلَ يُقاس عليه.
    * `HEAD <sha> refs/heads/new 000…`               — رأسٌ مفصول يُدفع إلى فرعٍ جديد.

    ومقيسٌ حيًّا في نسخةٍ اختباريّة: هذه الأشكالُ هي ما أرسله git فعلًا (ومنها وُلد الحاجبُ R62-F1:
    `awk '{print $1}'` يقرأ `(delete)`/`HEAD`/`refs/tags/…` كأنّها أسماءُ فروع).
    """
    refs: list[str] = []
    non_branch = 0
    deleted = 0
    for line in text.splitlines():
        f = line.split()
        if len(f) < 3:
            continue
        if f[0] == "(delete)" or (f[1] and set(f[1]) == {"0"}):   # حذفُ مرجع: علامتُه في git الحقلُ الأوّل
            deleted += 1
            continue
        remote = f[2]
        if not remote.startswith("refs/heads/"):
            non_branch += 1
            continue
        name = remote[len("refs/heads/"):]
        if name and name not in refs:
            refs.append(name)
    return refs, non_branch, deleted


def verdict(ref: str, *, gh=None, sha_of=None, local_of=None,
            remotes_list: "list[str] | None" = None) -> dict:
    """حُكمٌ على مرجعٍ واحد: «أخضر» لا يُقال إلّا بتشغيلٍ مكتملٍ ناجح **على الالتزام المدفوع**.

    الوسائطُ تُحلّ في وقت النداء (لا تُربَط في التعريف) لتُستبدَل في الضوابط بلا سِحر.
    **و`remotes_list` مرورٌ للقائمة المسؤول عنها `main`** (مرّةً واحدةً لكلّ تشغيل) — وغيابُه يعني
    «سَلْ git» فلا حالةَ مخزَّنة.
    """
    gh = gh or _gh
    sha_of = sha_of or (lambda r: _pushed_sha(r, remotes_list))
    local_of = local_of or _local_sha
    branch = branch_of(ref, remotes_list)   # **ما يُسأل به `gh` اسمُ الفرع** — والمرجعُ كما كُتب يبقى في البيان
    rc, txt = gh(["run", "list", "--branch", branch, "--limit", "1",
                  "--json", "conclusion,status,headSha,workflowName"])
    if rc != 0:
        return {"ref": ref, "state": "غيرُ مقروء", "why": f"`gh` لم يُجب: {txt[:100]}"}
    try:
        runs = json.loads(txt or "[]")
    except json.JSONDecodeError:
        return {"ref": ref, "state": "غيرُ مقروء", "why": "خرجُ `gh` ليس JSON"}
    if not runs:
        return {"ref": ref, "state": "بلا تشغيل", "why": "لا تشغيلَ لهذا المرجع على GitHub"}
    run = runs[0]
    head = str(run.get("headSha") or "")
    want = str(sha_of(ref) or "")
    if not want:
        return {"ref": ref, "state": "غيرُ مقروء",
                "why": f"لا مرجعَ محلّيٌّ/متعقَّبٌ لـ`{ref}` ⇒ لا أُثبت أنّ التشغيلَ له ⇒ `git fetch`"}
    if not head:
        return {"ref": ref, "state": "غيرُ مقروء",
                "why": f"تشغيلٌ بلا `headSha` ⇒ لا مرساةَ تقيسها (والمدفوعُ {want[:7]})"}
    if not _same_commit(want, head):
        return {"ref": ref, "state": "قديم",
                "why": f"آخرُ تشغيلٍ على {head[:7]} والمدفوعُ على {want[:7]} ⇒ لا يُبرّئ الرأسَ المدفوع"}
    where = ""
    local = str(local_of(ref) or "")
    if local and not _same_commit(local, head):
        where = f" (ومحلّيًّا {local[:7]} — التزامٌ غيرُ مدفوع)"
    if run.get("status") != "completed":
        return {"ref": ref, "state": "جارٍ", "why": f"{run.get('workflowName', '')} لم يكتمل بعد{where}"}
    if run.get("conclusion") == GREEN:
        return {"ref": ref, "state": "أخضر", "why": f"{run.get('workflowName', '')}{where}"}
    return {"ref": ref, "state": "أحمر",
            "why": f"{run.get('workflowName', '')}: {run.get('conclusion')}{where}"}


LIMIT = ("حدُّ هذا الفحص: يقيس نتيجةَ تشغيلٍ على GitHub لا صحّةَ الشجرة — "
         "وهو يُقاس عليه صدقُ ما يُكتب في تقرير الدفع.")


def _remind(refs: list[str], non_branch: int, deleted: int) -> int:
    """تذكيرُ مسار الدفع: يطبع الأمرَ ويُعلن ما لا يُقاس — **ويخرج صفراً دائماً**.

    الـCI يعمل **بعد** الدفع، فخطّافُ ما قبل الدفع لا يملك ما يقيسه؛ فيقف التذكيرُ في المسار الذي
    يُنسى فيه. **ولا يمسّ الشبكة**، ورمزُ خروجِه صفرٌ في كلّ حال: خطّافٌ يُسقط دفعاً مشروعاً
    (وسمٌ · حذفُ فرع · رأسٌ مفصول) يُصنع به الحافزُ على `--no-verify` — وهو ما يُسقط حرّاسَ الأمن.
    """
    print("تذكيرُ الدفع: بعد أن يبدأ الـCI، قِس **كلَّ مرجعٍ دفعته** ثم اذكر النتيجة في التقرير:")
    if refs:
        print(f"    python3 tools/ci_report.py {' '.join(refs)}")
    else:
        print("    (لا مرجعَ فرعٍ في هذه الدفعة ⇒ لا شيءَ يُقاس)")
    if non_branch or deleted:
        print(f"    (وتُرك {non_branch} سطراً ليس فرعاً و{deleted} حذفَ مرجع — لا تشغيلَ يُقاس عليهما)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="نتيجةُ CI لكلِّ مرجعٍ دُفع — ولا يُقال أخضرُ بلا دليل (R61-1 «ملحقُ الدفع»).")
    ap.add_argument("refs", nargs="*",
                    help="أسماءُ المراجع كما تعرفها `gh` (مثال: chore/round56-evidence) — "
                         "وتُقبل صيغةُ git أيضًا (`origin/main` · `refs/heads/main`) وتُقاس على اسم الفرع")
    ap.add_argument("--json", action="store_true",
                    help="خرجٌ آليٌّ للسجلّ في تقرير الدفع (stdout = JSON وحده · والبيان البشريّ على stderr)")
    ap.add_argument("--remind", action="store_true",
                    help="تذكيرٌ بمراجعَ مُعلَنة صريحاً: يطبع الأمرَ — ولا يحكم ولا شبكة")
    ap.add_argument("--pre-push", dest="pre_push", action="store_true",
                    help="وضعُ الخطّاف: يقرأ سطورَ `pre-push` من stdin ويطبع الأمرَ بمراجع الوجهة — ويخرج صفراً دائماً")
    a = ap.parse_args(argv)

    if a.pre_push:
        # **لا شبكةَ ولا حُكمَ ولا إسقاط:** يُقرأ stdin كما يقرأه حارسان آخران (الخطّافُ يقرأه مرّةً)،
        # وتُقرأ مراجعُ الوجهة هنا لا في خطّافٍ بـawk/sed — في ذيول ذلك: مُحلِّلٌ مختبَر، والخطّافُ لا يُسقط دفعاً.
        raw = "" if sys.stdin.isatty() else sys.stdin.read()
        try:
            refs, non_branch, deleted = parse_pushed_refs(raw)
        except Exception as e:                 # لا شيءَ في مسار الدفع يُسقِط دفعاً — ولا صمتَ عن السبب
            print(f"⚠ تذكيرُ الدفع تعذّر (لا أثر على الدفع): {e}", file=sys.stderr)
            return 0
        return _remind(refs, non_branch, deleted)

    if a.remind:
        # تذكيرٌ بمراجعَ صريحة (يُستعمل في التوثيق وبعد الدفع): نفسُ العقد — لا شبكةَ ولا حُكم.
        return _remind(list(a.refs), 0, 0)

    if not a.refs:
        ap.error("مرجعٌ واحدٌ على الأقلّ — أو `--remind`/`--pre-push`")

    rmts = remotes()        # **مرّةً واحدةً لكلّ تشغيل** — تُمرَّر لكلّ ما يحتاجها (لا تخزينَ عالميّ)

    def _line(v: dict) -> str:
        """سطرُ حكمِ مرجعٍ واحد: `branch_of` **مرّةً واحدة** على القائمة المارّة (كان يُنادى مرّتين)."""
        br = branch_of(v["ref"], rmts)
        tail = f" (قِيس على الفرع `{br}`)" if br != v["ref"] else ""
        return f"{'✓' if v['state'] == 'أخضر' else '·'} {v['state']:<11} {v['ref']} — {v['why']}{tail}"

    vs = [verdict(r, remotes_list=rmts) for r in a.refs]
    lines = [_line(v) for v in vs]
    lines.append(LIMIT)

    unreadable = [v for v in vs if v["state"] == "غيرُ مقروء"]
    bad = [v for v in vs if v["state"] != "أخضر"]
    if unreadable:
        lines.append("⛔ BLOCK — تعذّر القياس ⇒ «غيرُ المقروء ليس نظيفاً» فلا يُقال أخضر:")
        lines += [f"   ⛔ {v['ref']} — {v['why']}" for v in unreadable]
        code = 2
    elif bad:
        lines.append("⛔ BLOCK — ما دُفع لا يُقال عنه أخضرُ بلا دليل (وكلٌّ باسمه):")
        lines += [f"   ⛔ {v['state']}: {v['ref']} — {v['why']}" for v in bad]
        code = 1
    else:
        lines.append(f"PASS — كلُّ مرجعٍ دُفع ({len(vs)}) له تشغيلٌ أخضرُ على التزامه.")
        code = 0

    # **`--json` يعني آليًّا:** stdout = JSON وحده (يُستهلك بـ`json.loads`)، والبيانُ البشريّ على stderr
    # فلا يُخفى إعلانُ الحدّ ولا يُفسد السجلَّ ([R62] قِيس: `json.loads` كان يسقط على «حدُّ هذا الفحص»).
    stream = sys.stderr if a.json else sys.stdout
    if a.json:
        print(json.dumps(vs, ensure_ascii=False, indent=1))
    for ln in lines:
        print(ln, file=stream)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
