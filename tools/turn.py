#!/usr/bin/env python3
"""**مَن الدور الآن — يُشتقّ من الوقائع لا يُكتب بيد** (P-6 · تبنّاه المدقّق في مراجعة ٥٤).

**العلّةُ التي وُلد منها:** `handoff/STATE.md` هو أوّلُ ملفٍّ يُقرأ، وكان يُحدَّث **بيد** الطرف الذي أنهى
دوره (نصُّ §١ من البروتوكول) ⇒ قِيس تقادُمُه: ظلّ يقول «`P-1..P-3` تنتظر قرارَ المدقّق» بعد أن قُرِّرت
ونُفِّذت. والقاعدةُ التي تحكم (J52-1): **ما يُشتقّ لا يُكتب** — فالاشتقاقُ هنا من واقعٍ موجود:

- **آخرُ فاعل**: أحدثُ تقريرٍ اسمُه يحمل زمنَه (`handoff/<طرف>/YYYYMMDD-HHMM-…md`).
- **الدور**: للطرف الآخر… **إلّا** إذا حمل آخرُ تقريرٍ طلبَ قرارٍ من المالك («بيدك» · `AWAITING_FOUNDER`)
  ⇒ فالدورُ **للمالك** — وهذا هو الموضعُ الذي تأخّر فيه دمجُ #119 بلا مالكٍ ظاهر (P-6 صريحاً).

    tools/turn.py                # سطرُ الملفّ المشترك (مُؤشِّر) + الدورُ الآنيّ وسببُه
    tools/turn.py --json         # الحكمُ كاملاً (الطرف · آخرُ فاعل · زمنُه · السبب)
    tools/turn.py --check        # 0 لا قيمةَ محفوظة (لا تقادُمَ ممكن) · 1 قيمةٌ محفوظةٌ ستتقادم · 2 تعذّر القياس
    tools/turn.py --write        # يكتب **المُؤشِّر** في handoff/STATE.md (ولا قيمةَ فيه)

**ولا تُحفَظ قيمتُه** (R55-1 ب): سطرُ الدور في الملفّ المشترك **مُؤشِّرٌ إلى الأمر**، لأنّ قيمًة محفوظةً
يتقادم **بعد كلّ دفعةٍ من الطرف الآخر** (كاتبُ السطر واحدٌ بالبروتوكول) ⇒ فحصٌ يسقط بلا ذنبٍ لأحد. والسطرُ
بنفسه يُقاس: وجودُ قيمةٍ بين علامتين خلفيّتين = عطب.

**والحدُّ المُعلَن:** يقرأ **الأسماءَ** (زمنُ الاسم) لا زمنَ الالتزام — فالتقادمُ يُقاس على ما أُعلن؛
ولو غاب تقريرٌ من صندوقٍ صار الحكمُ `UNMEASURED` لا «الدورُ على الطرف الآخر».
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = "handoff/STATE.md"
SIDES = {"sulaiman": "المنفّذ", "claude": "المدقّق"}
OWNER = "المالك"
#: زمنُ الاسم: أربعُ خانات (HHMM) أو **ستّ** (HHMMSS) — والصيغةُ الثانيةُ هي الموثَّقة في البروتوكول،
#: وأسماءُ المدقّق كلُّها بها ⇒ نمطٌ بأربعٍ فقط كان **يُعميه عن صندوقِ الطرف الآخر كاملاً** (R55-1).
NAME_RE = re.compile(r"^(\d{8})-(\d{4})(\d{2})?-")
#: علاماتُ «الدورُ عند المالك»: طلبُ قرارٍ صريح لا يملكه غيرُه.
OWNER_SIGNALS = ("بيدك", "AWAITING_FOUNDER", "AWAITING FOUNDER", "قرار المالك", "قرارُ المالك")


def _reports(side: str) -> list[tuple[str, str, Path]]:
    """(الزمنُ من الاسم، الطرف، الملف) — بترتيب الاسم؛ و`STATE.md` ليس تقريراً."""
    out = []
    for p in sorted((ROOT / "handoff" / side).glob("*.md")):
        m = NAME_RE.match(p.name)
        if m and not p.name.upper().startswith("STATE"):
            # توحيدُ الطولين إلى ستّ خانات قبل المقارنة (وإلا قارنّا «0203» بـ«021953» بترتيبٍ مختلّ)
            out.append((f"{m.group(1)}-{m.group(2)}{m.group(3) or '00'}", side, p))
    return out


def derive() -> dict[str, object]:
    """الحكمُ المُشتقّ — بلا كتابة، وبلا افتراض: يُعلن سببَه ومن أين جاء."""
    allreps = _reports("sulaiman") + _reports("claude")
    if not allreps:
        return {"verdict": "UNMEASURED", "why": "لا تقريرَ في أيّ صندوق (لا زمنَ يُقاس)"}
    ts, side, path = max(allreps, key=lambda t: (t[0], t[1]))
    body = path.read_text(encoding="utf-8", errors="replace")
    owner_awaiting = [s for s in OWNER_SIGNALS if s in body]
    if owner_awaiting:
        turn, why = OWNER, f"آخرُ تقريرٍ ({side} · {ts}) يطلب قراراً من المالك («{owner_awaiting[0]}»)"
    else:
        other = "claude" if side == "sulaiman" else "sulaiman"
        turn, why = other, f"آخرُ فاعلٍ {side} ({ts}) ⇒ الدورُ على {other}"
    return {"verdict": "MEASURED", "turn": turn, "turn_label": SIDES.get(turn, turn),
            "last_actor": side, "last_report": str(path.relative_to(ROOT)), "as_of": ts, "why": why}


#: **ولا تُحفَظ القيمة** (R55-1 الطبقةُ الثانية): لو كُتبت في الملفّ المشترك لتقادمت **بعد كلّ دفعةٍ من
#: الطرف الآخر** (كاتبُه واحدٌ بالبروتوكول) فيسقط `--check` بلا ذنبٍ لأحد. ⇒ السطرُ **مُؤشِّر** يُشير إلى
#: الأمر، والقيمةُ تُقاس لحظةَ الطلب. وهذا يقتل صنفَ التقادُم من أصله لا حادثتَه.
POINTER = "turn: **يُقاس لا يُكتب** — `python tools/turn.py` يعرض الدورَ الآنيّ وسببَه (ولا قيمةَ محفوظةً تتقادم)"


def line_for(d: dict[str, object]) -> str:
    """السطرُ الذي يُكتب في الملفّ المشترك: **مُؤشِّرٌ لا قيمة**. والقيمةُ تُطبع في المخرَج."""
    return POINTER


def _stored_value(text: str) -> str | None:
    """هل حُفظت قيمةٌ (معرّفُ طرفٍ بين علامتين خلفيّتين) في سطر الدور؟ ⇒ عطبٌ سيُنتج تقادُماً."""
    for ln in text.splitlines():
        if ln.startswith("turn:"):
            m = re.search(r"`([a-z]+)`", ln)
            return m.group(1) if m else None
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="اشتقاقُ الدور من الوقائع (P-6)")
    ap.add_argument("--check", action="store_true",
                    help="يكشف قيمةً محفوظةً للدور (ستتقادم بعد كلّ دفعةٍ من الطرف الآخر)")
    ap.add_argument("--write", action="store_true", help="يُصلح سطرَ `turn:` في الملفّ المشترك")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    d = derive()
    if d["verdict"] != "MEASURED":
        print(f"⚠ UNMEASURED — {d['why']} ⇒ **فشلٌ مُغلَق** (لا أُعلن دوراً لم أقِسه)")
        return 2
    want = line_for(d)
    shared = ROOT / SHARED

    if a.write:
        t = shared.read_text(encoding="utf-8")
        lines = t.splitlines(keepends=True)
        for i, ln in enumerate(lines):
            if ln.startswith("turn:"):
                lines[i] = want + "\n"
                break
        else:
            lines.insert(1, want + "\n")
        shared.write_text("".join(lines), encoding="utf-8")
        print(f"✓ كُتب سطرُ الدور في {SHARED}: {d['turn']}")
        return 0

    if a.check:
        if not shared.exists():
            print(f"⚠ تعذّر الفحص: لا {SHARED} ⇒ فشلٌ مُغلَق")
            return 2
        stored = _stored_value(shared.read_text(encoding="utf-8"))
        if stored is None:
            print(f"✓ {SHARED}: لا قيمةَ محفوظةً للدور (مُؤشِّرٌ لا قيمة) ⇒ لا تقادُمَ ممكن. "
                  f"والدورُ الآنيّ: {d['turn']} ({d['why']})")
            return 0
        print(f"⛔ {SHARED} يحفظ قيمةً للدور (`{stored}`) ⇒ ستتقادم بعد كلّ دفعةٍ من الطرف الآخر. "
              f"أصلِحْها بـ`tools/turn.py --write` (مُؤشِّرٌ لا قيمة). والدورُ الآنيّ: `{d['turn']}`")
        return 1

    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(want)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
