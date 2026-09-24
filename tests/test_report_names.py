"""**اسمُ التقرير يحمل زمنَ وصوله** — القاعدةُ صارت تُقاس لا تُتذكَّر (ملاحظةُ مراجعة ٥٤).

**الحادثة:** تقريرٌ اسمُه `20260925-0130` وأُودِع في `01:18` — خالف قاعدةً كُتبت الليلةَ نفسَها.
والقياسُ على ١٢٤ تقريراً أظهر أنّ العلّة **صنفيّة لا فرديّة**: **٥٥** تقريراً اسمُه منزاحٌ > ٢٠ دقيقة
(بعضُها بالساعات) ⇒ فالقاعدةُ كانت **عادةً تُنسى** لا إنفاذاً.

**والعلاجُ على نمط المستودع نفسه** (استثناءٌ تاريخيٌّ يُعلَن ويُقاس):
- ما أُودِع **قبل** `CUTOFF` (لحظةُ كتابة القاعدة الميكانيكيّة) ⇒ **مُعفىً بتاريخه**, ويُقاس اتّساقُه:
  لو ظهر «مُعفىً» أُودِع **بعد** القطع ⇒ تناقضٌ يُكشَف.
- وما أُودِع **بعد** القطع ⇒ يجب أن يطابق الاسمُ زمنَ الإيداع (المؤلف **أو** المُودِع، بتسامح ٢٠ دقيقة —
  فيصدُق على مراجعات المدقّق التي تُعاد تركيبُها بـ`--rebase` مع حفظ تواريخها).
"""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = datetime(2026, 9, 25, 1, 0, tzinfo=timezone(timedelta(hours=3)))
TOLERANCE = timedelta(minutes=20)
#: أربعُ خانات أو ستّ — **ولا يُتخطّى صندوقٌ بصمت** (R55-2: النمطُ الرباعيّ كان يقفز فوق ملفّات المدقّق
#: كلِّها فيمرّ «unchecked» بلا أن يُقاس عليه شيء).
NAME = re.compile(r"^(\d{8})-(\d{4})(\d{2})?-")


def _reports() -> list[Path]:
    out: list[Path] = []
    for side in ("sulaiman", "claude"):
        out += [p for p in sorted((ROOT / "handoff" / side).glob("*.md")) if NAME.match(p.name)]
    return out


def _landing_times(path: Path) -> list[datetime]:
    """أزمنةُ أوّلِ إيداعٍ للملفّ (مؤلف ومُودِع). و`--follow` يتجاوز إعادة التسمية."""
    rel = str(path.relative_to(ROOT))
    r = subprocess.run(["git", "log", "--follow", "--diff-filter=A", "--format=%aI|%cI", "--", rel],
                       cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        return []
    out: list[datetime] = []
    for line in r.stdout.strip().splitlines():
        for part in line.split("|"):
            try:
                out.append(datetime.fromisoformat(part.strip()).replace(tzinfo=None))
            except ValueError:
                pass
    return out


def _stamp(path: Path) -> datetime:
    """زمنُ الاسم موحَّداً على مقياس واحد (ستّ خانات)، ومع **اصطلاح نهاية اليوم**.

    `24:00` (كما في `20260922-240000-…`) يقتل `strptime` باستثناء `ValueError` ⇒ وضابطٌ ينهار على أوّل
    اسمٍ بهذا الاصطلاح **لا يحرس شيئاً**. فيُقارَب: `24:00` = `00:00` من الغد (نفسُ اليوم المعنويّ).
    """
    m = NAME.match(path.name)
    assert m is not None
    date, hhmm, ss = m.group(1), m.group(2), m.group(3) or "00"
    if hhmm[:2] == "24" and hhmm[2:] == "00" and ss == "00":
        return datetime.strptime(date, "%Y%m%d") + timedelta(days=1)
    return datetime.strptime(date + hhmm + ss, "%Y%m%d%H%M%S")


def test_every_recent_report_name_matches_when_it_landed():
    """**الضابطُ الحيّ**: كلُّ تقريرٍ أُودِع بعد القطع يحمل زمنَه (±٢٠ دقيقة)."""
    after_cutoff = [(p, _landing_times(p)) for p in _reports()]
    after_cutoff = [(p, ts) for p, ts in after_cutoff if ts and min(ts) > CUTOFF.replace(tzinfo=None)]
    assert after_cutoff, ("لا تقريرَ أُودِع بعد القطع ⇒ الحوضُ الحيّ فارغٌ **بقياس** لا بافتراض "
                          "(والتاريخُ السابق مُعفىً بالتاريخ: ٥٥ اسماً منزاحاً كُتبت بيد قبل القاعدة)")
    late = []
    for p, times in after_cutoff:
        stamped = _stamp(p)
        if not any(abs((t - stamped).total_seconds()) <= TOLERANCE.total_seconds() for t in times):
            late.append((p.name, [t.isoformat() for t in times]))
    assert not late, f"اسمُ التقرير لا يطابق زمنَ إيداعه: {late} (أعِدْ تسميتَه بـ`git mv` على الزمن الصحيح)"


def test_both_boxes_are_actually_checked_not_skipped():
    """**صنفُ R55-2**: نمطٌ لا يفهم صيغةَ صندوقٍ يتخطّاه بصمت ⇒ «نجاحٌ» لم يُقَس عليه شيء.

    والقياسُ هنا: **كلُّ طرفٍ له ملفٌّ مُطابَقٌ فعلاً** (لا مفترض).
    """
    from_name = {"sulaiman": 0, "claude": 0}
    for p in _reports():
        side = p.parent.name
        from_name[side] += 1
    assert from_name["claude"] > 0, (
        f"لا ملفَّ واحدٍ من صندوق المدقّق يُطابَق النمط — وهو ما كان يُخفي مراجعاته كلَّها "
        f"(أسماءُ المدقّق بستّ خانات HHMMSS · المقيس: {from_name})")
    assert from_name["sulaiman"] > 0, f"لا ملفَّ من صندوق المنفّذ يُطابَق: {from_name}"


def test_an_end_of_day_name_does_not_break_the_parser():
    """ضابطٌ على **حدِّ البيانات الحقيقيّ**: الاسمُ ذو `24:00` يُقارَب `00:00` من الغد ولا يُسقط الفحص.

    (قِيس على `handoff/sulaiman/20260922-240000-item4-…md` — كان يُتخطّى صمتاً بالنمط الرباعيّ، فلمّا
    صار يُرى ظهر الاستثناء.)
    """
    p = ROOT / "handoff/sulaiman/20260922-240000-item4-ONE-DELIVERY-three-commitments-price-and-outside-witness.md"
    if p.exists():
        assert _stamp(p) == datetime(2026, 9, 23, 0, 0), _stamp(p)


def test_no_historic_exemption_has_outlived_its_reason():
    """**الاستثناءُ يُقاس**: تقريرٌ اسمُه منزاحٌ لكنّه **أُودِع بعد القطع** = تناقضٌ لا يُعفى."""
    contradicted = []
    for p in _reports():
        times = _landing_times(p)
        if not times or min(times) > CUTOFF.replace(tzinfo=None):
            continue                              # ليس مُعفىً بتاريخه ⇒ فحصُه في الضابط السابق
        if any(abs((t - _stamp(p)).total_seconds()) > TOLERANCE.total_seconds() for t in times):
            if max(times) > CUTOFF.replace(tzinfo=None) + timedelta(days=1):
                contradicted.append(p.name)      # أُعيدَ إيداعُه لاحقاً ولم يُصحَّح اسمُه
    assert not contradicted, f"استثناءٌ تاريخيٌّ زال سببُه (أُعيد إيداعُه بعد القطع) ⇒ صحِّح الاسم: {contradicted}"
