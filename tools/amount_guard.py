"""حارسُ المبالغ — **الطبقةُ الغائبة** التي جعلت مستودعاً عامّاً يمرّ ومعه ١٢٦ ظهوراً لمبالغ حقيقية.

**الجذرُ المُثبت:** `publish_guard` له قاعدةُ «سلسلة أرقام طويلة» تشترط عشرَ خاناتٍ متّصلة —
والنقطةُ العشرية تكسر السلسلة ⇒ `543210.99` تمرّ. فالحارسُ لم يُخطئ، **بل لم يكن يعرف أنه يجب
أن ينظر** ⇒ وخضرتُه تُقرأ شهادةَ خلوّ. (والأخطرُ: مبالغُ الكوربوس بالعربية `9001.00` تمشي
حتى على قاعدةٍ لاتينية.)

**والقياسُ لا النمط:** المجموعةُ المصدرية **تُشتقّ من الكوربوس** (`results/pg-*.json` + الشهادة)
لا من قائمةٍ يدوية — فالقاعدةُ تعرف ما يجب أن تحرسه. والمانيفستُ المدفوع يحمل **بصماتٍ فقط**.

⚠ **حدُّ الصدق المُعلن:** البصمةُ **كاشفٌ لا تعمية** — فضاءُ المبالغ يُعدّ بالجَرد (وقد سجّلناه
تصحيحاً على أنفسنا سابقاً). فالحمايةُ الحقيقية غيابُ النصّ الصريح، والمانيفستُ يجعل العطبَ
**يُكشف قبل الدفع** لا أن يجعل المبلغ سِرّاً.

    python3 tools/amount_guard.py --build     # يبني المانيفست من الكوربوس (يحتاج data/ — محليّ)
    python3 tools/amount_guard.py             # يفحص الشجرة المُتتبَّعة (يعمل في CI: بصمات فقط)
    python3 tools/amount_guard.py --inject 543210.99   # إثباتُ أنه يسقط (معيار: احقن وأرِ السقوط)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
MANIFEST = PROJ / "docs" / "security" / "amount-denylist.json"
SALT = b"rajhi-rag/amount-guard/v1"
_AR = "0-9\u0660-\u0669\u06f0-\u06f9"
TOKEN = re.compile(rf"-?[{_AR}][{_AR},٬\u060c٫]*(?:\.[{_AR}]{{1,2}})?")
_DIGITS = {**{chr(0x0660 + i): str(i) for i in range(10)},
           **{chr(0x06F0 + i): str(i) for i in range(10)}}
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".xlsx", ".docx"}


def normalize(tok: str) -> str:
    s = "".join(_DIGITS.get(c, c) for c in tok)
    return s.replace("٫", ".").replace("٬", "").replace("،", "").replace(",", "").strip()


def fingerprint(amount: str) -> str:
    return hashlib.sha256(SALT + normalize(amount).encode()).hexdigest()[:32]


def is_amount_shaped(tok: str) -> bool:
    """رقمٌ له أربعُ خاناتٍ صحيحةٌ أو أكثر (وكسرٌ اختياريّ) — فضاءُ المبالغ الحقيقية."""
    v = normalize(tok)
    ip = v.lstrip("-").split(".")[0]
    if not ip.isdigit():
        return False
    return len(ip) >= 4 and (v.count(".") <= 1)


def build(extra: list[str]) -> int:
    """يبني المانيفستَ من الكوربوس الحيّ (المبالغُ الحقيقية) + ما يُمرَّر صريحاً."""
    amounts: set[str] = set()
    run = PROJ / "data/local_sample/slice_629p/results"
    for f in run.glob("pg-*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        for row in (d.get("rows") or []):
            for k in ("amount", "debit", "credit", "balance", "running"):
                if row.get(k):
                    amounts.add(normalize(str(row[k])))
        for k, v in (d.get("footer") or {}).items():
            if isinstance(v, str) and v.strip():
                amounts.add(normalize(v))
    cert = PROJ / "data/eval_pack/oracle-confirmation-629p.json"
    if cert.exists():
        ev = json.loads(cert.read_text(encoding="utf-8"))
        for r in ev.get("pages", []):
            for c in r.get("cells", []):
                v = c.get("ours") or c.get("oracle")
                if v:
                    amounts.add(normalize(str(v)))
    amounts |= {normalize(a) for a in extra}
    amounts = {a for a in amounts if is_amount_shaped(a)}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        "what": "بصماتُ مبالغَ حقيقية — كاشفٌ للمنع، لا تعمية (انظر توثيق الأداة)",
        "how": "python3 tools/amount_guard.py --build",
        "count": len(amounts),
        "fingerprints": sorted({fingerprint(a) for a in amounts}),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    try:
        shown = MANIFEST.relative_to(PROJ)
    except ValueError:
        shown = MANIFEST
    print(f"المانيفست: {shown} · {len(amounts)} مبلغاً (بصماتٍ فقط)")
    return 0


def tracked_text_files() -> list[str]:
    """المُتتبَّع **وغيرُ المتتبَّع غيرُ المُهمَل**: الحارسُ يحرس ما على وشك أن يُدفع.

    الاعتمادُ على `git ls-files` وحدَه كان يجعل الحارس أعمى عن الملفّ الذي لم يُضَف بعد —
    وهو **بالضبط** وقتُ الحاجة إليه (قبل `git add`). وقد كشف ذلك الحقنُ نفسُه: ملفٌّ فيه مبلغٌ
    حقيقيٌّ لم يسقط الحارسُ عليه لأنه غيرُ متتبَّع ⇒ الحارسُ الذي لا يسقط عند حقنِ عطبٍ **لم يُثبت أنه حارس**.
    """
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"],
                         cwd=str(PROJ), capture_output=True, text=True).stdout
    return [f for f in out.split() if Path(f).suffix.lower() not in BINARY]


def find_in_text(txt: str, deny: set[str]) -> list[tuple[str, str]]:
    """النواةُ القابلةُ للاختبار: كلُّ مبلغٍ حقيقيٍّ في نصّ — بالمقارنة المُقنَّنة."""
    out = []
    for m in TOKEN.finditer(txt):
        if not is_amount_shaped(m.group(0)):
            continue
        if fingerprint(m.group(0)) in deny:
            out.append((m.group(0), normalize(m.group(0))))
    return out


def load_deny() -> set[str]:
    if not MANIFEST.exists():
        print("⛔ لا مانيفست — ابنِه بـ`--build` (وإلا فالحارسُ لا يعرف ما يحرس)", file=sys.stderr)
        raise SystemExit(2)
    return set(json.loads(MANIFEST.read_text(encoding="utf-8"))["fingerprints"])


def scan() -> list[tuple[str, str, str]]:
    deny = load_deny()
    hits: list[tuple[str, str, str]] = []
    for fn in tracked_text_files():
        p = PROJ / fn
        try:
            txt = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits += [(fn, raw, norm) for raw, norm in find_in_text(txt, deny)]
    return hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="حارسُ المبالغ: لا مبلغَ حقيقيّ في مستودعٍ عامّ")
    ap.add_argument("--build", action="store_true", help="يبني المانيفستَ من الكوربوس")
    ap.add_argument("--extra", default="", help="مبالغُ تُضاف صريحاً (مفصولةً بفاصلة)")
    ap.add_argument("--inject", default="", help="مبلغٌ يُحقَن مؤقّتاً في ملفٍّ لإثبات السقوط")
    args = ap.parse_args(argv)
    if args.build:
        return build([x for x in args.extra.split(",") if x.strip()])
    if args.inject:
        target = PROJ / "docs" / "SECURITY_PROBE.md"
        backup = target.read_text(encoding="utf-8") if target.exists() else None
        try:
            target.write_text((backup or "") + f"\nمبلغٌ محقون: {args.inject}\n", encoding="utf-8")
            hits = scan()
            print("سقط ✓ (الحارسُ رأى المبلغ)" if hits else "⛔ لم يسقط — الحارسُ أعمى عن المحقون")
            return 1 if hits else 0
        finally:
            if backup is None:
                target.unlink(missing_ok=True)
            else:
                target.write_text(backup, encoding="utf-8")
    hits = scan()
    if hits:
        print("⛔ BLOCK — مبالغُ حقيقيةٌ في ملفّاتٍ مُتتبَّعة (يُطهَّر بمبالغَ صناعية، والدليلُ يبقى في data/):")
        for fn, raw, norm in hits[:25]:
            print(f"   {fn}  ←  {raw}")
        print(f"المجموع: {len(hits)}")
        return 1
    print("PASS — لا مبلغَ حقيقيٌّ في ملفّاتٍ مُتتبَّعة (بالمقارنة المُقنَّنة: لاتينيةٌ وعربيةٌ وفارسية)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
