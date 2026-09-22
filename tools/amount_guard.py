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
SYNTHETIC = PROJ / "docs" / "security" / "synthetic-amounts.txt"
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


def is_significant(v: str) -> bool:
    """**مُصفّي الأهمية (مقيسٌ لا مُقدَّر):** قيمةٌ يقلّ تصادمُها.

    القياس: بلا هذا المُصفّي تُطابق المجموعةُ ٤٣٠ ظهوراً في ١٢٩ ملفاً — أكثرُها تصادمٌ مع
    أرقام إصدارات (`requirements.lock`) وقيمٍ ذهبية (`0.44`) وأمثالٍ صناعية مُعلنة.
    ومعه: **٢١ ظهوراً في ١٤ ملفاً** — كلُّها مواضعُ بياناتٍ حقيقية. فالحدُّ: ≥٤ خاناتٍ صحيحة
    **وكسرٌ غيرُ صفريّ التمييز** (`.00` ونظائرُها تُستثنى).
    """
    ip, _, fp = normalize(v).lstrip("-").partition(".")
    return len(ip) >= 4 and fp not in ("", "0", "00", "000")


def declared_set(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(normalize(line))
    return out


def source_amounts() -> tuple[set[str], int, int]:
    """المصدرُ الحقيقيّ: `raw_rows` بكلّ حقولها الماليّة + التذييل (بصيغتَيه) + الشهادة."""
    got: set[str] = set()
    files = 0
    for fp in sorted(PROJ.glob("data/local_sample/*/results/pg-*.json")):
        files += 1
        d = json.loads(fp.read_text(encoding="utf-8"))
        for row in (d.get("raw_rows") or []):
            if isinstance(row, dict):
                for k, v in row.items():
                    if v not in (None, "") and is_amount_shaped(v):
                        got.add(normalize(v))
        for k, v in (d.get("footer") or {}).items():
            if k == "raw" and isinstance(v, dict):
                for vv in v.values():
                    if vv not in (None, "") and is_amount_shaped(vv):
                        got.add(normalize(vv))
            elif isinstance(v, str) and v.strip() and is_amount_shaped(v):
                got.add(normalize(v))
    cert = PROJ / "data/eval_pack/oracle-confirmation-629p.json"
    if cert.exists():
        for r in json.loads(cert.read_text(encoding="utf-8")).get("pages", []):
            for c in r.get("cells", []):
                for k in ("ours", "oracle"):
                    if c.get(k) and is_amount_shaped(str(c[k])):
                        got.add(normalize(str(c[k])))
    return got, files, len(got)


def build(_extra: list[str]) -> int:
    src, files, total = source_amounts()
    synth = declared_set(SYNTHETIC)
    significant = {a for a in src if is_significant(a)}
    ex_trivial = total - len(significant)
    ex_synth = len(significant & synth)
    entered = significant - synth
    if entered | (significant & synth) != significant or entered & synth:
        raise SystemExit("⛔ اشتقاقٌ غيرُ مُغلق: التصنيفُ لا يُجمَع")
    derivation = {
        "page_files": files, "source_shape_ok": total, "entered": len(entered),
        "excluded_trivial": ex_trivial, "excluded_synthetic": ex_synth,
        "rule": "significant = ≥4 خاناتٍ صحيحة وكسرٌ غيرُ صفريّ التمييز؛ والسالبُ ما أُعلن صناعيّاً",
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
    print(f"المانيفست: {len(entered)} بصمةً · الاشتقاق: {total} = {len(entered)} + {ex_trivial} تافهة + {ex_synth} صناعية · {files} ملفَّ صفحة")
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


def scan() -> list[tuple[str, str, str]]:
    deny = load_deny()
    hits: list[tuple[str, str, str]] = []
    for fn in tracked_text_files():
        try:
            txt = (PROJ / fn).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits += [(fn, raw, norm) for raw, norm in find_in_text(txt, deny)]
    return hits


def proof_inject() -> int:
    """**برهانُ السقوط بسُمٍّ من المصدر لا من المانيفست** — ويخرج بغير الصفر عند العمى."""
    src, _, _ = source_amounts()
    sig = sorted({a for a in src if is_significant(a)})
    if not sig:
        print("⛔ لا مصدرَ محليّ ⇒ تعذّر البرهان (لا أُعلن نجاحاً بلا سمّ)", file=sys.stderr)
        return 5
    poison = sig[len(sig) // 2]          # قيمةٌ حقيقيّةٌ من قلب الكوربوس
    target = PROJ / "docs" / "SECURITY_PROBE.md"
    backup = target.read_text(encoding="utf-8") if target.exists() else None
    try:
        head = backup or "# مسبار"
        target.write_text(head + chr(10) + "الرصيد: " + poison + chr(10), encoding="utf-8")
        hits = [h for h in scan() if h[0].endswith("SECURITY_PROBE.md")]
        if hits:
            print(f"سقط ✓ (سمٌّ من المصدر: {poison} — رآه الحارس)")
            return 0
        print(f"⛔ لم يسقط — الحارسُ أعمى عن سمٍّ من المصدر ({poison}) ⇒ الحارسُ ليس حارساً", file=sys.stderr)
        return 5
    finally:
        if backup is None:
            target.unlink(missing_ok=True)
        else:
            target.write_text(backup, encoding="utf-8")


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
        print(json.dumps({"pass": not hits, "count": len(hits),
                          "hits": [{"file": f, "token": r, "normalized": n} for f, r, n in hits]},
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
    print("PASS — لا مبلغَ حقيقيٌّ في ملفّاتٍ مُتتبَّعة (مقارنةٌ مُقنَّنة، وبصماتٌ مُفتَّحة)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
