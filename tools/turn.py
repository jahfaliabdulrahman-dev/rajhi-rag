#!/usr/bin/env python3
"""**مَن الدور الآن — يُشتقّ من الوقائع لا يُكتب بيد** (P-6 · تبنّاه المدقّق في مراجعة ٥٤).

**العلّةُ التي وُلد منها:** `handoff/STATE.md` هو أوّلُ ملفٍّ يُقرأ، وكان يُحدَّث **بيد** الطرف الذي أنهى
دوره (نصُّ §١ من البروتوكول) ⇒ قِيس تقادُمُه: ظلّ يقول «`P-1..P-3` تنتظر قرارَ المدقّق» بعد أن قُرِّرت
ونُفِّذت. والقاعدةُ التي تحكم (J52-1): **ما يُشتقّ لا يُكتب** — فالاشتقاقُ هنا من واقعٍ موجود:

- **آخرُ فاعل**: أحدثُ تقريرٍ اسمُه يحمل زمنَه (`handoff/<طرف>/YYYYMMDD-HHMM-…md`).
- **الدور**: للطرف الآخر… **إلّا** إذا وُجد **إعلانُ توقّفٍ مُصطلَح** ⇒ فالدورُ **للمالك** (البروتوكول §٣) —
  وهذا هو الموضعُ الذي تأخّر فيه دمجُ #119 بلا مالكٍ ظاهر (P-6 صريحاً).
  **وصيغتُه واحدة، وموضعاه مُعلَنان (R57-2 · قاسه المدقّق في مراجعة ٥٧):** الصيغةُ `status: AWAITING_FOUNDER`
  — كما توثّقها `handoff/STATE.md:60` وتكليفُ المدقّق `docs/claude-auditor-directive.md:43` — وتُقرأ من
  **آخر تقرير** ومن **الملفّ المشترك `handoff/STATE.md`** (قفلُ المالك) معاً. وما ليس إعلاناً: اقتباسُها
  في **كتلة شِفرة مُقفَلة** (وليس في سياجٍ يتيم — S-4/ST-6)، و«بيدك» في قائمةِ نهاية التقرير (كلُّ تقريرٍ
  للمنفّذ ينتهي بها ⇒ صارت ضجيجاً يُزيح الدورَ زوراً)، وصيغةٌ حرّةٌ بلا حقل `status:`.
  **ولا يُجرَّد اقتباسٌ داخليّ** (S-4): كان `` `[^`]*` `` يُحذَف قبل المطابقة، وقِيس في مقعد ٥٧ أنّ إسقاطَه
  (أ) لا يُسقط أيَّ ضابط، (ب) ويُبقي الصيغةَ الخامّةَ غيرَ مُطابِقة (السطرُ يبدأ بعلامةٍ خلفيّة) — فالمرساةُ
  وحدَها تكفي، والتجريدُ كان **يوسّع** المطابقةَ لا يضيّقها.

    tools/turn.py                # سطرُ الملفّ المشترك (مُؤشِّر) + الدورُ الآنيّ وسببُه
    tools/turn.py --json         # الحكمُ كاملاً (الطرف · آخرُ فاعل · زمنُه · السبب)
    tools/turn.py --check        # 0 لا قيمةَ محفوظة (لا تقادُمَ ممكن) · 1 قيمةٌ محفوظةٌ ستتقادم · 2 تعذّر القياس
    tools/turn.py --write        # يكتب **المُؤشِّر** في handoff/STATE.md (ولا قيمةَ فيه)

**ولا تُحفَظ قيمتُه** (R55-1 ب): سطرُ الدور في الملفّ المشترك **مُؤشِّرٌ إلى الأمر**، لأنّ قيمًة محفوظةً
يتقادم **بعد كلّ دفعةٍ من الطرف الآخر** (كاتبُ السطر واحدٌ بالبروتوكول) ⇒ فحصٌ يسقط بلا ذنبٍ لأحد. والسطرُ
بنفسه يُقاس: وجودُ قيمةٍ بين علامتين خلفيّتين = عطب.

**وصيغةُ الاسم المقبولة:** `YYYYMMDD-HHMM` **أو** `YYYYMMDD-HHMMSS` (كلتاهما تُوحَّد إلى ستّ خانات قبل
الترتيب)، و`24:00` اصطلاحُ نهايةِ يومٍ يُرتَّب بعد `23:59`.

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
#: **صيغةٌ واحدةٌ في موضعين مُعلَنين (R57-2 · قاسه المدقّق في مراجعة ٥٧ — ثلاثُ حالاتٍ مقيسة):**
#: الصيغةُ الموثّقةُ في المستودع نفسِه هي **`status: AWAITING_FOUNDER`** (`handoff/STATE.md:60` ·
#: `docs/claude-auditor-directive.md:43`)، وموضعاها: **آخرُ تقرير** و**الملفُّ المشترك `handoff/STATE.md`**
#: (قفلُ المالك). والثلاثةُ التي أُغلقت: (أ) الملفُّ المشتركُ **لم يكن يُقرأ أصلًا** ⇒ قفلُ المالك الموثَّق لا
#: يوقف الدور؛ (ب) الصيغةُ الحرّةُ (العلامةُ في أوّل سطر) أسقطت صيغةَ التكليفِ الموثّقة في `ba6c219`
#: (**تراجع**)؛ (ج) الاقتباسُ في كتلةِ شِفرةٍ **يُزيح الدورَ زوراً**. ⇒ الإعلانُ الآن: حقلُ `status:` يحمل
#: العلامة، في الموضعين، **مُرساةً في أوّل السطر** (سطرٌ يبدأ بعلامةٍ خلفيّة لا يُطابق ⇒ الاقتباسُ لا يُعلن)
#: ولا يُقرأ داخلَ كتلةِ شِفرةٍ **مُقفَلة** (أسوارٌ زوجاً).
DECLARATION_RE = re.compile(r"^\s*(?:[-*+]\s*)?status:\s*(AWAITING[ _]FOUNDER)\b", re.I)
#: سياجُ كتلةِ شِفرة (``` أو ~~~) — ويُقابَل **زوجاً** لا قلْباً لحالة: سياجٌ يتيمٌ يُبطِل التسييجَ كلَّه،
#: فلا يُكتم إعلانٌ حقيقيٌّ بسطرِ تنسيقٍ ناقص (ST-6: كان القلْبُ يجعل كلَّ ما بعد سياجٍ يتيمٍ مُهمَلاً).
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")


def stamp_of(name: str) -> str | None:
    """مفتاحُ زمن الاسم موحَّداً (`YYYYMMDD-HHMMSS`) — **مصدرٌ واحد** يستورده الضابطُ أيضاً.

    (كان النمطُ مكرَّراً في ملفّين فوقع العمى مرّتين بأربع خانات مقابل ستّ — R55-1/R55-2.)
    """
    m = NAME_RE.match(name)
    if not m or name.upper().startswith("STATE"):
        return None
    return f"{m.group(1)}-{m.group(2)}{m.group(3) or '00'}"


def as_datetime(key: str):
    """المفتاحُ زمناً — ومع **اصطلاح نهاية اليوم**: `24:00` = آخرُ اليوم ⇒ `00:00` من الغد.

    والاصطلاحُ **مُعلَن** لا مُفترض (اسمٌ حقيقيّ في المستودع: `20260922-240000-…`، أُودِع 20:33 في اليوم
    نفسه — فلا يُدّعى أنّه زمنُ الإيداع، بل اصطلاحٌ للترتيب ذُكر في البروتوكول §٢٤).
    """
    from datetime import datetime, timedelta
    date, hhmmss = key.split("-")
    if hhmmss[:2] == "24" and hhmmss[2:] == "0000":
        return datetime.strptime(date, "%Y%m%d") + timedelta(days=1)
    return datetime.strptime(date + hhmmss, "%Y%m%d%H%M%S")


def _reports(side: str) -> list[tuple[str, str, Path]]:
    """(مفتاحُ الزمن، الطرف، الملف) — و`STATE.md` ليس تقريراً."""
    out = []
    for p in sorted((ROOT / "handoff" / side).glob("*.md")):
        key = stamp_of(p.name)
        if key:
            out.append((key, side, p))
    return out


def declarations(text: str) -> list[str]:
    """إعلاناتُ التوقّف **الحقيقيّة** في نصّ — قاعدتُها مقيسةٌ في ستّ حالات (R57-2 · S-4/ST-6):

    (١) الصيغةُ حقلُ `status:` يحمل العلامة — **مُرساةً في أوّل السطر** (بعد مسافةٍ أو علامةِ قائمة).
    (٢) ولا يُقرأ داخل **كتلة شِفرة مُقفَلة**: الأسوارُ تُقابَل **زوجاً**؛ وسياجٌ يتيمٌ (عددٌ فرديّ) يُبطِل
    التسييجَ كلَّه — فيُقرأ النصُّ كما هو: البديلُ (قلْبُ الحالة) كان يُهمِل كلَّ ما بعد سياجٍ ناقص، وإهمالُ
    إعلانٍ حقيقيٍّ أسوأُ من قراءة اقتباس (ST-6).
    (٣) ولا يُجرَّد اقتباسٌ داخليّ قبل المطابقة: قِيس أنّ إسقاطَ التجريد لا يُسقط ضابطاً، وأنّ الصيغةَ الخامّةَ
    (بين علامتين خلفيّتين) **لا تُطابق** لأنّ السطرَ يبدأ بعلامةٍ خلفيّة — فالمرساةُ وحدَها تكفي (S-4).
    (٤) وصيغةٌ حرّةٌ بلا `status:` ليست إعلاناً. ودالّةٌ خالصةٌ ⇒ تُقاس بسمٍّ في الذاكرة لا بالنيّة.
    """
    lines = text.splitlines()
    fences = [i for i, ln in enumerate(lines) if FENCE_RE.match(ln)]
    inside = [False] * len(lines)
    if len(fences) % 2 == 0:                       # زوجٌ ⇒ التسييجُ مُتحقَّق (سياجٌ يتيم ⇒ لا تسييج)
        for a, b in zip(fences[0::2], fences[1::2]):
            for i in range(a, b + 1):
                inside[i] = True
    out: list[str] = []
    for i, line in enumerate(lines):
        if inside[i]:
            continue
        m = DECLARATION_RE.match(line)
        if m:
            out.append(m.group(1).upper().replace(" ", "_"))
    return out


def derive() -> dict[str, object]:
    """الحكمُ المُشتقّ — بلا كتابة، وبلا افتراض: يُعلن سببَه ومن أين جاء."""
    allreps = _reports("sulaiman") + _reports("claude")
    if not allreps:
        return {"verdict": "UNMEASURED", "why": "لا تقريرَ في أيّ صندوق (لا زمنَ يُقاس)"}
    ts, side, path = max(allreps, key=lambda t: (t[0], t[1]))
    body = path.read_text(encoding="utf-8", errors="replace")
    owner_awaiting = declarations(body)
    where = f"آخرُ تقريرٍ ({side} · {ts})"
    if not owner_awaiting:
        # **قفلُ المالك** (الموضعُ الثاني المُعلَن): يُقرأ من الملفّ المشترك — وكان لا يُقرأ أصلًا ⇒ قفلٌ
        # موثَّقٌ لا يوقف الدور (R57-2أ). والقيمةُ تُقاس لحظةَ الطلب كمثلها في سطر الدور.
        shared = ROOT / SHARED
        if shared.exists():
            owner_awaiting = declarations(shared.read_text(encoding="utf-8", errors="replace"))
            if owner_awaiting:
                where = f"قفلُ المالك في {SHARED}"
    if owner_awaiting:
        turn, why = OWNER, f"{where} يُعلن توقّفاً على قرار المالك («{owner_awaiting[0]}»)"
    else:
        other = "claude" if side == "sulaiman" else "sulaiman"
        turn, why = other, f"آخرُ فاعلٍ {side} ({ts}) ⇒ الدورُ على {other}"
    return {"verdict": "MEASURED", "turn": turn, "turn_label": SIDES.get(turn, turn),
            "last_actor": side, "last_report": str(path.relative_to(ROOT)), "as_of": ts,
            "owner_declared_in": where if owner_awaiting else None, "why": why}


#: **ولا تُحفَظ القيمة** (R55-1 الطبقةُ الثانية): لو كُتبت في الملفّ المشترك لتقادمت **بعد كلّ دفعةٍ من
#: الطرف الآخر** (كاتبُه واحدٌ بالبروتوكول) فيسقط `--check` بلا ذنبٍ لأحد. ⇒ السطرُ **مُؤشِّر** يُشير إلى
#: الأمر، والقيمةُ تُقاس لحظةَ الطلب. وهذا يقتل صنفَ التقادُم من أصله لا حادثتَه.
POINTER = "turn: **يُقاس لا يُكتب** — `python tools/turn.py` يعرض الدورَ الآنيّ وسببَه (ولا قيمةَ محفوظةً تتقادم)"


def _turn_line(text: str) -> str | None:
    """سطرُ الدور كما هو (بلا افتراض صيغة) — وبمقابلة **حرفيّة** مع المُؤشِّر.

    **ولماذا حرفيّة:** نسخةٌ سابقة كانت تبحث عن `` `([a-z]+)` `` فنجت منها صيغٌ أربع لنفس القيمة
    (`` (`Claude`) `` · `` (`sulaiman-2`) `` · `(claude)` بلا علامتين · `Turn:` بحرفٍ كبير) ⇒ «لا قيمةَ
    محفوظة» وهي محفوظة. والقياسُ الحرفيّ يُذيب المساعدَ ويُغلق الصيغَ كلَّها (المقعدُ التركيبيّ: حركةُ جودو).
    """
    for ln in text.splitlines():
        if ln.lower().startswith("turn:"):
            return ln.strip()
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
    want = POINTER                      # لا وسيطَ يُهمَل: السطرُ ثابتٌ بالتصميم (يذوب `line_for`)
    shared = ROOT / SHARED

    if a.write:
        t = shared.read_text(encoding="utf-8")
        lines = t.splitlines(keepends=True)
        for i, ln in enumerate(lines):
            if ln.lower().startswith("turn:"):       # يشمل `Turn:` ⇒ لا سطرَ ثانياً يُترك بقيمةٍ محفوظة
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
        line = _turn_line(shared.read_text(encoding="utf-8"))
        if line is None:
            print(f"⛔ {SHARED}: **لا سطرَ `turn:`** ⇒ القارئُ الأوّل لن يجد الأمرَ (كان مُؤشِّراً وغاب). "
                  f"أصلِحْه بـ`tools/turn.py --write`. والدورُ الآنيّ: `{d['turn']}`")
            return 1
        if line != POINTER:
            print(f"⛔ {SHARED} سطرُ دورِه ليس المُؤشِّر: {line[:70]!r} ⇒ قيمةٌ/صيغةٌ محفوظة (ستتقادم أو "
                  f"تُشوَّه). أصلِحْه بـ`tools/turn.py --write`. والدورُ الآنيّ: `{d['turn']}`")
            return 1
        print(f"✓ {SHARED}: المُؤشِّرُ كما هو (لا قيمةَ محفوظةً ⇒ لا تقادُمَ ممكن). "
              f"والدورُ الآنيّ: {d['turn']} ({d['why']})")
        return 0

    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        # **الوعدُ في المُؤشِّر مُنفَّذٌ هنا** (R56-2): بلا وسيطٍ تُعرض **الدورُ وسببُه**، لا سطرُ الإشارة وحده —
        # وإلّا فالمُؤشِّرُ يعِد بما لا تفعله الأداة (وهو ما قاسه المدقّق في مراجعة ٥٦: أمرٌ موثَّقٌ لا يُخرِج الدور).
        print(f"الدورُ الآنيّ: **{d['turn']}** — {d['why']}")
        print(f"({SHARED}: سطرُ `turn:` مُؤشِّرٌ لا قيمةَ محفوظة ⇒ لا تقادُمَ ممكن)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
