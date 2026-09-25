#!/usr/bin/env python3
"""مُدقِّقُ CI لكلِّ ما دُفع — «ولا يُقال أخضرُ بلا دليل» (مراجعة ٦١ · R61-1).

ملحقُ دفعِ الجولة ٦١ ادّعى «CI ناجح» بنطاقٍ **أضيقَ من الدفع**: قِيس مرجعٌ واحدٌ من خمسة، وفرعان
من فروع المدقّق المدفوعة كانتا **حمراوين** ولم يذكرهما التقرير. والصنفُ ليس سهواً في جملة، بل
**ادّعاءٌ بلا موضعِ قياس** — فلا يُصلحه وعدٌ بأن أتذكّر، بل أداةٌ تُنتج الموضع:

* نتيجةُ CI **لكلِّ مرجعٍ دُفع**، لا لمرجعٍ واحد.
* **مقيسةً على التزامه هو** — فتشغيلٌ أخضرُ لالتزامٍ قديمٍ لا يُبرّئ رأساً جديداً (درسُ §٢٧:
  «وإن كانت مدفوعةً فعلًا فتحقّق أنّ `origin/main` هو الالتزامُ المقصود لا مرجعاً متقادماً»).
* وتخرج بغير صفر إن كان مرجعٌ أحمرَ أو جارياً أو **بلا تشغيل** أو **غيرَ مقروء** — فغيابُ القياس
  ليس نظافةً (القاعدة: «غيرُ المقروء ليس نظيفاً»).

    python3 tools/ci_report.py chore/round56-evidence claude/review-56
    python3 tools/ci_report.py --json <ref>...        # للسجلّ في تقرير الدفع

رموزُ الخروج: 0 = كلُّ مرجعٍ أخضرُ على التزامه · 1 = مرجعٌ ليس أخضر (يُسمّى) · 2 = تعذّر القياس.

حدُّ هذا الفحص: يقيس **نتيجةَ تشغيلٍ على GitHub** لا صحّةَ الشجرة — الشجرةُ تقيسها البوّاباتُ
والاختبارات، وهذه الأداةُ تقيس **صدقَ ما يُكتب في تقرير الدفع**، فلا هي تُصلح عطباً ولا هي تُخفيه.
"""
from __future__ import annotations

import argparse
import json
import subprocess
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


def _pushed_sha(ref: str) -> str | None:
    """**الالتزامُ الذي دُفع فعلًا** لا الذي في يدي: `origin/<ref>` أوّلًا.

    (تصحيحٌ بعد قياسٍ حيّ: كان القياسُ على المرجع المحلّيّ، وفرعٌ محلّيٌّ متقدّمٌ على المدفوع
    يُوسَم «قديمًا» وهو **أحمرُ** في الحقيقة ⇒ وسمٌ مضلِّل. المقصودُ صدقُ تقرير الدفع،
    وتقريرُ الدفع يتكلّم عن **المدفوع**.)
    """
    pushed = _local_sha(f"origin/{ref}")
    return pushed or _local_sha(ref)


def _same_commit(a: str, b: str) -> bool:
    n = min(len(a), len(b), 12)
    return n >= 7 and a[:n] == b[:n]


def verdict(ref: str, *, gh=None, sha_of=None, local_of=None) -> dict:
    """حُكمٌ على مرجعٍ واحد: «أخضر» لا يُقال إلّا بتشغيلٍ مكتملٍ ناجح **على الالتزام المدفوع**.

    الوسائطُ تُحلّ في وقت النداء (لا تُربَط في التعريف) لتُستبدَل في الضوابط بلا سِحر.
    """
    gh = gh or _gh
    sha_of = sha_of or _pushed_sha
    local_of = local_of or _local_sha
    rc, txt = gh(["run", "list", "--branch", ref, "--limit", "1",
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
    if head and not _same_commit(want, head):
        return {"ref": ref, "state": "قديم",
                "why": f"آخرُ تشغيلٍ على {head[:7]} والمدفوعُ على {want[:7]} ⇒ لا يُبرّئ الرأسَ المدفوع"}
    where = ""
    local = str(local_of(ref) or "")
    if local and head and not _same_commit(local, head):
        where = f" (ومحلّيًّا {local[:7]} — التزامٌ غيرُ مدفوع)"
    if run.get("status") != "completed":
        return {"ref": ref, "state": "جارٍ", "why": f"{run.get('workflowName', '')} لم يكتمل بعد{where}"}
    if run.get("conclusion") == GREEN:
        return {"ref": ref, "state": "أخضر", "why": f"{run.get('workflowName', '')}{where}"}
    return {"ref": ref, "state": "أحمر",
            "why": f"{run.get('workflowName', '')}: {run.get('conclusion')}{where}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="نتيجةُ CI لكلِّ مرجعٍ دُفع — ولا يُقال أخضرُ بلا دليل (R61-1).")
    ap.add_argument("refs", nargs="+",
                    help="أسماءُ المراجع كما تعرفها `gh` (مثال: chore/round56-evidence)")
    ap.add_argument("--json", action="store_true", help="خرجٌ آليٌّ للسجلّ في تقرير الدفع")
    ap.add_argument("--remind", action="store_true",
                    help="تذكيرٌ في مسار الدفع: يطبع الأمرَ الذي يُقاس به ما دُفعت — ولا يحكم ولا شبكة")
    a = ap.parse_args(argv)

    if a.remind:
        # **تذكيرٌ لا حُكم:** الـCI يعمل **بعد** الدفع، فحكمُه لا يُقاس في خطّاف ما قبل الدفع.
        # فيقف التذكيرُ في المسار نفسِه الذي يُنسى فيه، ويبقى الحُكمُ لأداةٍ تُشغَّل بعده.
        print("تذكيرُ الدفع: بعد أن يبدأ الـCI، قِس **كلَّ مرجعٍ دفعته** ثم اذكر النتيجة في التقرير:")
        print(f"    python3 tools/ci_report.py {' '.join(a.refs)}")
        return 0

    vs = [verdict(r) for r in a.refs]
    if a.json:
        print(json.dumps(vs, ensure_ascii=False, indent=1))
    else:
        for v in vs:
            print(f"{'✓' if v['state'] == 'أخضر' else '·'} {v['state']:<11} {v['ref']} — {v['why']}")
    print("حدُّ هذا الفحص: يقيس نتيجةَ تشغيلٍ على GitHub لا صحّةَ الشجرة — "
          "وهو يُقاس عليه صدقُ ما يُكتب في تقرير الدفع.")

    unreadable = [v for v in vs if v["state"] == "غيرُ مقروء"]
    if unreadable:
        print("⛔ BLOCK — تعذّر القياس ⇒ «غيرُ المقروء ليس نظيفاً» فلا يُقال أخضر:")
        for v in unreadable:
            print(f"   ⛔ {v['ref']} — {v['why']}")
        return 2
    bad = [v for v in vs if v["state"] != "أخضر"]
    if bad:
        print("⛔ BLOCK — ما دُفع لا يُقال عنه أخضرُ بلا دليل (وكلٌّ باسمه):")
        for v in bad:
            print(f"   ⛔ {v['state']}: {v['ref']} — {v['why']}")
        return 1
    print(f"PASS — كلُّ مرجعٍ دُفع ({len(vs)}) له تشغيلٌ أخضرُ على التزامه.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
