#!/usr/bin/env python3
"""**مَن الدور الآن — يُشتقّ من الوقائع لا يُكتب بيد** (P-6 · تبنّاه المدقّق في مراجعة ٥٤).

**العلّةُ التي وُلد منها:** `handoff/STATE.md` هو أوّلُ ملفٍّ يُقرأ، وكان يُحدَّث **بيد** الطرف الذي أنهى
دوره (نصُّ §١ من البروتوكول) ⇒ قِيس تقادُمُه: ظلّ يقول «`P-1..P-3` تنتظر قرارَ المدقّق» بعد أن قُرِّرت
ونُفِّذت. والقاعدةُ التي تحكم (J52-1): **ما يُشتقّ لا يُكتب** — فالاشتقاقُ هنا من واقعٍ موجود:

- **آخرُ فاعل**: أحدثُ تقريرٍ اسمُه يحمل زمنَه (`handoff/<طرف>/YYYYMMDD-HHMM-…md`).
- **الدور**: للطرف الآخر… **إلّا** إذا حمل آخرُ تقريرٍ طلبَ قرارٍ من المالك («بيدك» · `AWAITING_FOUNDER`)
  ⇒ فالدورُ **للمالك** — وهذا هو الموضعُ الذي تأخّر فيه دمجُ #119 بلا مالكٍ ظاهر (P-6 صريحاً).

    tools/turn.py                # السطرُ المُشتقّ + سببه
    tools/turn.py --check        # 0 مطابق · 1 متقادم (يطبع الصواب) · 2 تعذّر القياس (فشلٌ مُغلَق)
    tools/turn.py --write        # يُصلح سطرَ `turn:` في handoff/STATE.md

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
NAME_RE = re.compile(r"^(\d{8})-(\d{4})-")
#: علاماتُ «الدورُ عند المالك»: طلبُ قرارٍ صريح لا يملكه غيرُه.
OWNER_SIGNALS = ("بيدك", "AWAITING_FOUNDER", "AWAITING FOUNDER", "قرار المالك", "قرارُ المالك")


def _reports(side: str) -> list[tuple[str, str, Path]]:
    """(الزمنُ من الاسم، الطرف، الملف) — بترتيب الاسم؛ و`STATE.md` ليس تقريراً."""
    out = []
    for p in sorted((ROOT / "handoff" / side).glob("*.md")):
        m = NAME_RE.match(p.name)
        if m and not p.name.upper().startswith("STATE"):
            out.append((f"{m.group(1)}-{m.group(2)}", side, p))
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


def line_for(d: dict[str, object]) -> str:
    label = d["turn_label"] if d["verdict"] == "MEASURED" else "غيرُ مقيس"
    return f"turn: **{label}** (`{d.get('turn', '?')}`) — {d['why']} · يُشتقّ بـ`tools/turn.py`. **لا يُكتب بيد.**"


def _declared(text: str) -> str | None:
    for ln in text.splitlines():
        if ln.startswith("turn:"):
            m = re.search(r"`([a-z]+)`", ln)
            return m.group(1) if m else ln
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="اشتقاقُ الدور من الوقائع (P-6)")
    ap.add_argument("--check", action="store_true", help="يقارن المُشتقّ بسطر الملفّ المشترك")
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
        declared = _declared(shared.read_text(encoding="utf-8"))
        if declared == d["turn"]:
            print(f"✓ الدورُ المُعلَن مطابقٌ للمُشتقّ: {d['turn']} ({d['why']})")
            return 0
        print(f"⛔ الدورُ المُعلَن في {SHARED} = {declared!r} والمُشتقُّ = {d['turn']!r} ⇒ تقادُمٌ مُقاس.")
        print(f"   الصواب: {want}")
        return 1

    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(want)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
