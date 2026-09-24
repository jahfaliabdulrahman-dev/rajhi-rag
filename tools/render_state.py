#!/usr/bin/env python3
"""**حلُّ تعارض ملفّ الحالة بأداةٍ لا بيد** — `handoff/STATE.md` ملفٌّ مشتركٌ بين طرفَين.

**العلّةُ التي وُلدت منها الأداة (R52-1 · مراجعة ٥٢):** §١ من البروتوكول يُسند `handoff/STATE.md` إلى
«الطرف الذي أنهى دوره» ⇒ **كاتبان على ملفّ واحد** ⇒ كلُّ إعادةِ تركيبٍ على `main` تتوقّف عند هذا الملفّ
(قِيس: `git rebase 51b2e9d` من `9622101` ⇒ `CONFLICT (content): Merge conflict in handoff/STATE.md`
عند `1bb07a8`) ⇒ فالدمجُ الذي يفرضه §٦-٢ («Rebase and merge») **يقف**. والحلُّ اليدويّ يُنتج ملفًّا صالحًا
لكنّه غيرُ قابلٍ للتكرار: من حلَّه مرّةً قد يحلّه أخرى بمخرَجٍ مختلف — فيصير التعارضُ ذاكرةً لا قاعدة.

**قاعدةُ الحلّ (مُعلَنة، ويقيسها ضابط):**
1. **لا حذفَ لطرف.** كلُّ سطرٍ من الطرفَين يخرج في المخرَج: إمّا فعّالًا، وإمّا **مُعلَّقًا بوسمٍ صريح**.
2. **الفائزُ بمعيارٍ واحد:** صاحبُ **أحدثِ تاريخ ISO** في سطوره؛ وعند غيابِ التاريخين أو تعادلهما يُرجَّح
   **الوارد** (`theirs` = الالتزامُ القادم) لأنّه الأحدثُ عملًا. مُعلَنٌ لا مُخمَّن.
3. **السطورُ السجلّية (تبدأ بـ`(`) جمعٌ لا اختيار:** تبقى سطورُ الطرفَين بلا تكرار.
4. **الخرجُ حتميّ**: نفسُ المدخل ⇒ نفسُ المخرَج بايتًا بايتًا.

الاستعمال:
    python3 tools/render_state.py --check            # يفشل إن بقي تعارضٌ غيرُ محلول
    python3 tools/render_state.py --union            # يطبع الملفَّ محلولًا (لا يكتب)
    python3 tools/render_state.py --union --write    # يحلّ محلَّه (نسخةٌ احتياطيّة `.bak`)

والاختبارُ على **حالةٍ حقيقيةٍ ملتقطة** منه: `tests/fixtures/state-conflict-r52.md`.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from tools.pack_io import repo_root  # noqa: E402 — **جذرٌ واحد** (git-يّ وواعٍ بـworktree)، لا اشتقاقٌ ثانٍ

STATE = repo_root() / "handoff" / "STATE.md"

BEGIN = re.compile(r"^<{7}")
MID = re.compile(r"^={7}\s*$")
END = re.compile(r"^>{7}")
LOG = re.compile(r"^\(")
ISO_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
LOSER_PREFIX = "# سابق (تعارضٌ مُحلٌّ آليًّا — الجديدُ فعّالٌ أعلاه): "
SOLVED_NOTE = "<!-- تعارضٌ مُحلٌّ آليًّا بـ`tools/render_state.py`: لا سطرَ محذوف · الفائزُ {who} -->"


def _blocks(text: str) -> list[tuple[str, object]]:
    """يفكّك النصَّ: `("plain", line)` أو `("conflict", (ours, theirs))` — وترتيبُ الفروع يحترم `=====`."""
    out: list[tuple[str, object]] = []
    ours: list[str] | None = None
    theirs: list[str] | None = None
    for line in text.splitlines():
        if BEGIN.match(line):
            ours, theirs = [], None
            continue
        if ours is None:
            out.append(("plain", line))
            continue
        if MID.match(line):
            theirs = [] if theirs is None else theirs
            continue
        if END.match(line):
            if theirs is None:
                theirs = []
            out.append(("conflict", (ours, theirs)))
            ours = theirs = None
            continue
        (ours if theirs is None else theirs).append(line)
    if ours is not None:
        raise ValueError("علامةُ تعارضٍ مفتوحةٌ بلا إغلاق — الملفُّ غيرُ صالح")
    return out


def _criterion_date(lines: list[str]) -> str:
    """تاريخُ الحكم = تاريخُ **السطر المحكوم** (`status:`) لا أيِّ سطرٍ في الكتلة.

    **مقعدُ البنية (مراجعة ٥٢):** المعيارُ كان يقرأ **كلَّ** سطور الطرف، فقِيس على العيّنة الحقيقيّة أنّ
    `ours` بلا تاريخ، وأنّ تاريخَ `theirs` جاء من **سطرِ سجلّ** (`(claude) REVIEW-51`) ⇒ المعيارُ لم
    يُسهم بشيءٍ في العيّنة الوحيدة، وحسم الفائزَ الافتراضُ. فالآن يُقرأ من السطر الذي يُحكَم عليه،
    والافتراضُ («الوارد») يبقى — لكنّه **يُعلَن** في مخرَج الأداة، ويظهر أيُّهما حكم.
    """
    for x in lines:
        if x.startswith("status:"):
            d = ISO_DATE.search(x)
            if d:
                return d.group(1)
    return ""


def resolve(text: str) -> str:
    """يحلّ كلَّ تعارضٍ بالقاعدة المعلنة — بلا قراءة حالة git، فالأداةُ قابلةٌ للاختبار وحدها."""
    lines: list[str] = []
    for kind, payload in _blocks(text):
        if kind == "plain":
            lines.append(str(payload))
            continue
        ours, theirs = payload                                    # type: ignore[misc]
        dt_o, dt_t = _criterion_date(ours), _criterion_date(theirs)
        # الفائزُ: أحدثُ تاريخٍ **على سطر الحالة**؛ وعند غياب التاريخين أو تعادلهما يُرجَّح الوارد (مُعلَن).
        win, lose, who = ((theirs, ours, f"الوارد (بتاريخ سطر الحالة {dt_t or 'غائب'})")
                          if dt_t >= dt_o else (ours, theirs, f"الحاليّ (بتاريخ سطر الحالة {dt_o})"))
        lines.extend(x for x in win if not LOG.match(x))          # حقولُ الفائز فعّالة
        lines.extend(LOSER_PREFIX + x for x in lose              # حقولُ الخاسر: مُعلَّقةٌ لا محذوفة
                     if x.strip() and not LOG.match(x))
        seen: set[str] = set()
        for x in (x for x in [*win, *lose] if LOG.match(x)):      # السجلُّ جمعٌ بلا تكرار
            if x not in seen:
                seen.add(x)
                lines.append(x)
        lines.append(SOLVED_NOTE.format(who=who))
    return "\n".join(lines) + "\n"


def has_conflict(text: str) -> bool:
    return any(BEGIN.match(x) for x in text.splitlines())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="حلُّ تعارض ملفّ الحالة حتمًا — لا بيد")
    ap.add_argument("--path", type=pathlib.Path, default=STATE)
    ap.add_argument("--union", action="store_true", help="يطبع الملفَّ محلولًا")
    ap.add_argument("--write", action="store_true", help="يحلّ محلَّ الملفّ (نسخةٌ احتياطيّة .bak)")
    ap.add_argument("--check", action="store_true", help="يفشل إن بقي تعارضٌ غيرُ محلول")
    a = ap.parse_args(argv)

    text = a.path.read_text(encoding="utf-8")
    if a.check:
        if has_conflict(text):
            print(f"⛔ {a.path} يحمل تعارضًا غيرَ محلول ⇒ الحلُّ: `--union --write` (القاعدةُ في رأس الأدوات)",
                  file=sys.stderr)
            return 1
        print(f"✓ {a.path}: بلا تعارض")
        return 0
    if not a.union:
        ap.error("حدِّد --union أو --check")
    if not has_conflict(text):
        print("لا تعارضَ في الملفّ ⇒ لا شيءَ يُحلّ (لا يُعاد كتابةُ ملفٍّ سليم)")
        return 0
    try:
        out = resolve(text)
    except ValueError as exc:
        # **حكمٌ مُسمّى لا أثرُ بايثون** (مراجعة ٥٢ · مقعدُ المعايير): ملفٌّ بعلامةٍ غير مغلقة كان يُفجّر
        # Traceback على سطر الأوامر ⇒ قارئٌ لا يعرف ما يفعل. الآن: سببٌ ورمزُ خروجٍ مميّز (2).
        print(f"⛔ {a.path}: {exc} ⇒ لم يُكتب شيء. أصلِح العلامةَ (أو التقط الحالةَ بـ`git show :handoff/STATE.md`) ثم أعِد.",
              file=sys.stderr)
        return 2
    if a.write:
        (a.path.parent / (a.path.name + ".bak")).write_text(text, encoding="utf-8")
        a.path.write_text(out, encoding="utf-8")
        print(f"✓ حُلَّ وكُتب: {a.path} (النسخةُ قبل الحلّ: {a.path.name}.bak)")
        return 0
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
