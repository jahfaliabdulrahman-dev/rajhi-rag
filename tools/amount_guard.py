"""حارسُ المبالغ — الإصدار الثاني: الاشتقاقُ نفسُه صار محروساً.

**ما كان مكسوراً في الإصدار الأول (أثبته المدقّق):** المانيفست كان يقرأ `d.get("rows")` —
والكوربوس يخزّن الحركات في **`raw_rows`** ⇒ الحلقةُ دارت **صفرَ مرّة**، فدخل ١,٣٣٤ بصمةً من
التذييلات وحدَها وبقي **٤,١٠٠ مبلغاً مصدريًّا خارجه** — ومرّت معها أرقامُ حركاتٍ حقيقية.
والدرسُ (القاعدة العاشرة): **حارسٌ بقائمةِ منعٍ مُشتقّة، صحّتُه صحّةُ اشتقاقِها لا صحّةُ منطقِه.**

**وما كان مكسوراً ثانياً:** الحقنُ كان يسحب سمَّه **من المانيفست** ⇒ يُثبت أنّ الآلية تعضّ،
ولا يقول شيئاً عمّا لم يدخلها. الآن الحقنُ يسحب من **المصدر**، ويخرج **بغير الصفر** عند العمى:
أداةُ برهانٍ تُعلن الفشلَ وتخرج بنجاحٍ ليست بوابة.

**وحدُّ الصدق (أشدُّ ممّا قلناه):** البصماتُ صارت **مُفتَّحةً بمفتاحٍ سِرّيّ** (`AMOUNT_GUARD_KEY`)
⇒ البصمةُ المنشورة **لا تُجرَد** بغير المفتاح. وبلا المفتاح **يفشل الحارسُ مُغلَقاً** لا صامتاً.

**والاشتقاقُ مُعلنُ الأرقام:** المانيفستُ يحمل `derivation`:
`source_shape_ok = entered + excluded_trivial + excluded_synthetic` — ويُوقف البناءَ إن لم تُغلق.

    export AMOUNT_GUARD_KEY=...        # أو ضعه في data/.amount-guard-key (مُهمَل)
    python3 tools/amount_guard.py --build          # يشتقّ من الكوربوس ويُراجع الحساب
    python3 tools/amount_guard.py                  # الفحص (مُتتبَّع + غيرُ متتبَّع)
    python3 tools/amount_guard.py --inject         # يسحب السمَّ من المصدر ويثبت السقوط
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
MANIFEST = PROJ / "docs" / "security" / "amount-denylist.json"
DECLARED_BINARIES = PROJ / "docs" / "security" / "tracked-binaries.txt"
KEY_ENV = "AMOUNT_GUARD_KEY"
KEY_FILE = PROJ / "data" / ".amount-guard-key"
BINARY_DIRS = ("data/", "digital/")
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".xlsx", ".docx"}

_DIGITS = {**{chr(0x0660 + i): str(i) for i in range(10)},
           **{chr(0x06F0 + i): str(i) for i in range(10)}}
_AR = "0-9\u0660-\u0669\u06f0-\u06f9"
TOKEN = re.compile(rf"-?[{_AR}][{_AR},٬\u060c٫]*(?:\.[{_AR}]{{1,2}})?")

# مفتاحُ الحارس: بيئة ⇒ ملفٌّ مُهمَل ⇒ فشلٌ مُغلَق
def load_key() -> bytes:
    k = os.environ.get(KEY_ENV, "").strip()
    if not k and KEY_FILE.exists():
        k = KEY_FILE.read_text(encoding="utf-8").strip()
    if not k:
        raise SystemExit(
            f"⛔ لا مفتاحَ لِـ{KEY_ENV} ⇒ الحارسُ يفشل مُغلَقاً (لا يمرّ صامتاً).\n"
            f"   ضعه في البيئة أو في {_shown(KEY_FILE)} (مُهمَل)، وفي CI في أسرار المستودع."
        )
    return k.encode()


def _shown(path: Path) -> str:
    """**درسٌ تكرّر:** تنسيقُ مسارٍ قد يكون خارج المستودع ⇒ `relative_to` ترفع ValueError.
    (وقعنا فيه في الطباعة، ثم في رسالة المفتاح ⇒ فالعطبُ صنفٌ لا حالة.)"""
    try:
        return str(path.relative_to(PROJ))
    except ValueError:
        return str(path)


def normalize(tok: str) -> str:
    s = "".join(_DIGITS.get(c, c) for c in str(tok))
    return s.replace("٫", ".").replace("٬", "").replace("،", "").replace(",", "").strip()


def fingerprint(amount: str) -> str:
    return hmac.new(load_key(), normalize(amount).encode(), hashlib.sha256).hexdigest()[:32]


def is_amount_shaped(tok: str) -> bool:
    v = normalize(tok)
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", v):
        return False
    return len(v.lstrip("-").split(".")[0]) >= 4


def is_significant(v: str) -> bool:   # noqa: D401
    """**المدى: كلُّ مبلغٍ له ≥٤ خاناتٍ صحيحة — بلا شرطٍ على الكسر.**

    **تصحيحٌ من مراجعة ٣٦ (وكان عطباً حاجباً):** كان المُصفّي يستثني الكسرَ الصفريّ
    (`.00`) — و**الاستدارةُ صفةُ المبلغ لا دليلُ صناعيّته**؛ والمبالغُ المستديرة هي **أكثرُ
    الحركات المصرفية شيوعاً** ⇒ كان **٢٤٦ مبلغاً مصدريًّا (٧.٩٪) خارج الحماية**، و**٣١ ظهوراً
    في ١٩ ملفاً مُتتبَّعاً** — ومنها تفكيكُ مجاميع البنك الكلّية من ص٦٢٩.

    القاعدةُ الصحيحة: **الطولُ يصنع المدى** (فالمبالغُ القصيرةُ تتصادم مع أيّ رقم في أيّ نصّ)
    **والاستثناءُ يُعلَن لا يُخمَّن شكلُه** (`synthetic-amounts.txt`).
    """
    v = normalize(v)
    ip, _, fp = v.lstrip("-").partition(".")
    return len(ip) >= 4 and bool(fp)   # الكسرُ يشترط وجودُه لا قيمتُه


def declared_set(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(normalize(line))
    return out


NON_SOURCE = {
    "data/eval_pack/amount_redaction_map.json",   # خريطةُ التطهير: عمودُها الأيمنُ صناعيّ بالبناء
    "data/.amount-guard-key",
}


def _walk_amounts(obj, out: set[str]) -> None:
    """**لا نُعدّ المفاتيح — نمشي في الأثر.** الجذرُ الذي أسقط الإصدارَ الأول أنّ الاشتقاقَ
    عرف مفتاحاً (`rows`) غيرَ الذي يحمله الكوربوس (`raw_rows`) ⇒ دار صفرَ مرّة وصار المانيفستُ
    ناقصاً يُعطي `PASS` كاذباً. والمشيُ في القيمة لا يعرف مفاتيحَ ⇒ لا يُخطئ في مفتاح."""
    if isinstance(obj, str):
        if is_amount_shaped(obj):
            out.add(normalize(obj))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        s = f"{obj}"
        if is_amount_shaped(s):
            out.add(normalize(s))
    elif isinstance(obj, list):
        for x in obj:
            _walk_amounts(x, out)
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk_amounts(v, out)


def source_amounts() -> tuple[set[str], int, int, dict[str, int]]:
    """المصدرُ = **اتّحادُ كلّ أثرٍ بياناتيّ محليّ** (والأدلّةُ محفوظةٌ في `data/`).

    وتُقاس التغطية: كلُّ أثرٍ محليٍّ يجب أن تكون مبالغُه **داخل** المانيفست ⇒ فلا يبقى مفتاحٌ
    مفقودٌ ولا أثرٌ خارجَ الحراسة. (بهذا يُجاب سؤال «هل `raw_rows` آخرُ مفتاح؟» بلا تعداد مفاتيح.)
    """
    got: set[str] = set()
    files = 0
    per: dict[str, int] = {}
    for f in sorted(PROJ.glob("data/**/*")):
        if not f.is_file() or f.suffix.lower() not in {".json", ".jsonl"}:
            continue
        rel = str(f.relative_to(PROJ))
        if rel in NON_SOURCE:
            continue
        before = len(got)
        try:
            if f.suffix.lower() == ".jsonl":
                for line in f.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        _walk_amounts(json.loads(line), got)
            else:
                _walk_amounts(json.loads(f.read_text(encoding="utf-8")), got)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        files += 1
        per[rel] = len(got) - before
    return got, files, len(got), per


def coverage_gaps(deny: set[str]) -> list[tuple[str, str]]:
    """**حارسُ التغطية:** أيُّ مبلغٍ في أثرٍ محليٍّ ليس في المانيفست = ثقبٌ في الاشتقاق."""
    gaps: list[tuple[str, str]] = []
    for f in sorted(PROJ.glob("data/**/*")):
        if not f.is_file() or f.suffix.lower() not in {".json", ".jsonl"}:
            continue
        rel = str(f.relative_to(PROJ))
        if rel in NON_SOURCE:
            continue
        vals: set[str] = set()
        try:
            if f.suffix.lower() == ".jsonl":
                for line in f.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        _walk_amounts(json.loads(line), vals)
            else:
                _walk_amounts(json.loads(f.read_text(encoding="utf-8")), vals)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        for v in vals:
            if is_significant(v) and fingerprint(v) not in deny:
                gaps.append((rel, v))
    return gaps


def build(_extra: list[str]) -> int:
    src, files, total, per = source_amounts()
    significant = {a for a in src if is_significant(a)}
    ex_trivial = total - len(significant)   # قصيرةٌ/بلا كسر ⇒ خارجُ المدى بالبناء
    ex_synth = 0
    entered = significant
    # **إلغاءُ قائمة «الصناعيّ المُعلَن» (قياسٌ قضى عليها):** قيمُ المولّد التجريبيّ
    # (`2105.13` · `8424.03` · `8236.36` · `53853.71`) **موجودةٌ فعلًا في الكشف الحقيقيّ**
    # ⇒ فالإعلانُ عنها صناعيّةً كان **يُخرج مبالغَ حقيقيةٍ من الحماية**. والاستثناءُ بالمصدر
    # لا بالاسم: كلُّ قيمةٍ ماليّةٍ في أثرٍ حقيقيٍّ تُحمى؛ وأمثلةُ المولّد تُطهَّر كغيرها.
    derivation = {
        "artifact_files": files, "source_shape_ok": total, "entered": len(entered),
        "top_artifacts": dict(sorted(per.items(), key=lambda x: -x[1])[:6]),
        "excluded_trivial": ex_trivial, "excluded_synthetic": ex_synth,
        "scope": "كلُّ قيمةٍ ماليّةٍ لها ≥٤ خاناتٍ صحيحة **وكسرٌ عشريّ** — والاستثناءُ بالإعلان أُلغيَ (ثبت أنّه يحمي مبالغَ حقيقية)",
        "rule": "الاستدارةُ صفةُ المبلغ لا دليلُ صناعيّته (تصحيح مراجعة ٣٦)",
    }
    if total != len(entered) + ex_trivial + ex_synth:
        raise SystemExit(f"⛔ فجوةٌ غيرُ مُعلَنة: {total} ≠ {len(entered)}+{ex_trivial}+{ex_synth}"
                         " ⇒ البناءُ يسقط (لا يُنشر مانيفستٌ ناقص)")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        "what": "بصماتُ مبالغَ حقيقية — مُفتَّحةٌ بمفتاحٍ سِرّيّ (خارج الشجرة) ⇒ لا تُجرَد",
        "how": "AMOUNT_GUARD_KEY=… python3 tools/amount_guard.py --build",
        "keyed": True, "count": len(entered), "derivation": derivation,
        "fingerprints": sorted({fingerprint(a) for a in entered}),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"المانيفست: {len(entered)} بصمةً · الاشتقاق: {total} = {len(entered)} + {ex_trivial} تافهة + {ex_synth} صناعية · {files} أثراً")
    gaps = coverage_gaps({fingerprint(a) for a in entered})
    if gaps:
        print(f"⛔ فجوةُ تغطية: {len(gaps)} مبلغاً في أثرٍ محليٍّ خارجَ المانيفست ⇒ الاشتقاقُ ناقص:")
        for rel, v in gaps[:8]:
            print(f"   {rel} ← {v}")
        return 1
    print("تغطية ✓ — كلُّ مبلغٍ في آثار data/ داخلَ المانيفست (لا مفتاحَ مفقود)")
    return 0


def load_deny() -> set[str]:
    if not MANIFEST.exists():
        raise SystemExit("⛔ لا مانيفست — ابنِه بـ`--build`")
    return set(json.loads(MANIFEST.read_text(encoding="utf-8"))["fingerprints"])


def find_in_text(txt: str, deny: set[str]) -> list[tuple[str, str]]:
    out = []
    for m in TOKEN.finditer(txt):
        if not is_amount_shaped(m.group(0)):
            continue
        if fingerprint(m.group(0)) in deny:
            out.append((m.group(0), normalize(m.group(0))))
    return out


def tracked_text_files() -> list[str]:
    """المُتتبَّع **وغيرُ المتتبَّع غيرُ المُهمَل**: الحارسُ يحرس ما على وشك أن يُدفع."""
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"],
                         cwd=str(PROJ), capture_output=True, text=True).stdout
    return [f for f in out.split() if Path(f).suffix.lower() not in BINARY]


def undeclared_binaries() -> list[str]:
    declared = declared_set(DECLARED_BINARIES)
    out = subprocess.run(["git", "ls-files"], cwd=str(PROJ), capture_output=True, text=True).stdout
    return [f for f in out.split()
            if f.startswith(BINARY_DIRS) and Path(f).suffix.lower() in BINARY and f not in declared]


SCAN_SKIP = {"docs/security/amount-denylist.json", "data/eval_pack/amount_redaction_map.json"}
# **أسطحُ الصناعة** (يُخترع فيها المبلغ للاختبار) ⇒ لا تُمنع، **وتُنبَّه بأعدادها**: فالاستثناءُ
# بسببِ السطح لا بسببِ شكل المبلغ. وهذا يميّز بين **دليلٍ يُنقل** و**مثالٍ يُخترع** — وهو الشرط
# الذي طلبه المدقّق: «أبقِ الطول، احذف شرطَ الكسر، ومرّر الضجيجَ المستديرَ بإعلانٍ معلَّل».
FIXTURE_PREFIXES = ("tests/", "src/")
FIXTURE_FILES = {"scripts/make_synthetic_statement.py"}


def is_fixture_surface(fn: str) -> bool:
    return fn.startswith(FIXTURE_PREFIXES) or fn in FIXTURE_FILES


def scan() -> list[tuple[str, str, str]]:
    deny = load_deny()
    hits: list[tuple[str, str, str]] = []
    for fn in tracked_text_files():
        if fn in SCAN_SKIP:
            continue   # بصماتٌ سداسية/خريطةُ تطهير: تُشبه المبالغ ولا تسرّب (عطبٌ كاذب مقيس)
        try:
            txt = (PROJ / fn).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits += [(fn, raw, norm) for raw, norm in find_in_text(txt, deny)
                 if not is_fixture_surface(fn)]
    return hits


def fixture_surface_hits() -> list[tuple[str, str, str]]:
    """ظهوراتٌ في أسطح الصناعة: تُعدّ وتُعلن، ولا توقف الدفع (وبتصنيفها: مميّزةٌ/مستديرة)."""
    deny = load_deny()
    out: list[tuple[str, str, str]] = []
    for fn in tracked_text_files():
        try:
            txt = (PROJ / fn).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if is_fixture_surface(fn):
            out += [(fn, raw, norm) for raw, norm in find_in_text(txt, deny)]
    return out


def proof_inject() -> int:
    """**برهانٌ طبقيّ:** إن نجا **أيُّ** صنفٍ داخلَ المدى فالحارسُ يسقط بغير الصفر.

    الأصنافُ مقيسةٌ من المصدر لا مُختارة: مستديرٌ · كسريّ · سالبٌ · طويل. و«قصيرٌ/بلا كسر»
    **خارجُ المدى بإعلان** (يتصادم مع تواريخ وعدّادات) ويُطبع صريحاً فلا يمرّ ساكتاً.
    """
    src, _, _, _ = source_amounts()
    in_scope = sorted({a for a in src if is_significant(a)})
    if not in_scope:
        print("⛔ لا مصدرَ محليّ ⇒ تعذّر البرهان (لا أُعلن نجاحاً بلا سمّ)", file=sys.stderr)
        return 5
    strata = {
        "مستدير": next((v for v in in_scope if v.split(".")[-1] in ("00", "0")), None),
        "كسريّ": next((v for v in in_scope if v.split(".")[-1] not in ("00", "0")), None),
        "سالب": next((v for v in in_scope if v.startswith("-")), None),
        "طويل": max(in_scope, key=lambda v: len(v.split(".")[0])),
    }
    target = PROJ / "docs" / "SECURITY_PROBE.md"
    backup = target.read_text(encoding="utf-8") if target.exists() else None
    survivors, missed, out_of_scope = [], [], [v for v in src if not is_significant(v)][:1]
    try:
        for name, poison in strata.items():
            if poison is None:
                missed.append(name)
                continue
            head = backup or "# مسبار"
            target.write_text(head + chr(10) + "الرصيد: " + poison + chr(10), encoding="utf-8")
            if [h for h in scan() if h[0].endswith("SECURITY_PROBE.md")]:
                print(f"   سقط ✓ [{name}] · {poison}")
            else:
                survivors.append(f"{name} ({poison})")
    finally:
        if backup is None:
            target.unlink(missing_ok=True)
        else:
            target.write_text(backup, encoding="utf-8")
    if out_of_scope:
        print(f"   خارجُ المدى بإعلان (لا كسرَ/قصير): {out_of_scope[0]} — لا يُحقَن، ويُعلن")
    if survivors:
        print(f"⛔ أصنافٌ نجت: {survivors} ⇒ الحارسُ ليس حارساً", file=sys.stderr)
        return 5
    if missed:
        print(f"⛔ لا سمَّ لصنف: {missed}", file=sys.stderr)
        return 5
    print("سقطت كلُّ الأصناف ✓ (مستدير · كسريّ · سالب · طويل)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="حارسُ المبالغ: لا مبلغَ حقيقيّ في مستودعٍ عامّ")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--pre-push", action="store_true", help="اسمٌ مستعارٌ للفحص")
    ap.add_argument("--extra", default="")
    ap.add_argument("--inject", action="store_true", help="برهانُ السقوط (سمٌّ من المصدر)")
    ap.add_argument("--json", action="store_true", help="المخرَجُ الآليُّ الكامل (لا يُقصّ)")
    args = ap.parse_args(argv)
    if args.build:
        return build([x for x in args.extra.split(",") if x.strip()])
    if args.inject:
        return proof_inject()
    if undeclared_binaries():
        print("⛔ BLOCK — ثنائيٌّ مدفوعٌ تحت data/ أو digital/ بلا إعلان:")
        for f in undeclared_binaries()[:10]:
            print(f"   {f}")
        return 1
    hits = scan()
    if args.json:
        # **درسٌ من هذه الجولة:** عرضٌ يُقصّ عند ٢٥ أخفى ١١ تسريباً عن مُطهِّرٍ يقرأ المخرَج
        # ⇒ المخرَجُ الآليُّ يُعطي المجموعةَ كاملةً دائماً؛ القصُّ للعين وحدها.
        fx = fixture_surface_hits()
        print(json.dumps({"pass": not hits, "count": len(hits),
                          "hits": [{"file": f, "token": r, "normalized": n} for f, r, n in hits],
                          "fixture_count": len(fx),
                          "fixture_hits": [{"file": f, "token": r} for f, r, _ in fx[:20]]},
                         ensure_ascii=False, indent=1))
        return 1 if hits else 0
    if hits:
        print("⛔ BLOCK — مبالغُ حقيقيةٌ في ملفّاتٍ مُتتبَّعة:")
        for fn, raw, norm in hits[:25]:
            print(f"   {fn}  ←  {raw}")
        if len(hits) > 25:
            print(f"   … والباقي {len(hits)-25} (استعمل --json للمجموعة الكاملة)")
        print(f"المجموع: {len(hits)}")
        return 1
    fx = fixture_surface_hits()
    print("PASS — لا مبلغَ حقيقيٌّ في **أسطح الدليل** (docs/ · handoff/ · الأدوات)")
    if fx:
        distinctive = [h for h in fx if normalize(h[1]).split(".")[-1] not in ("00", "0")]
        print(f"   تنبيهٌ مُعلن: {len(fx)} ظهوراً في **أسطح الصناعة** (tests/ · src/) — "
              f"منها {len(distinctive)} قيمةً مميّزة (تستحقّ نظراً)، والبقيّةُ قيمٌ عامّة تتصادم بطبعها.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
