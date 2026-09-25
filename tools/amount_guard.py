"""حارسُ المبالغ — الإصدارُ الثالث: **الإنفاذُ نفسُه صار محروساً**.

**ما أسقطه المدقّق في الإصدار الثاني (مراجعة ٣٨)، وأثبتُّه بنفسي بالأمر قبل أن أكتب هنا:**

1. **لا نقطةَ إنفاذ.** `--pre-push` كان «اسمًا مستعارًا للفحص» يمشي على **الشجرة العاملة** لا على
   المدفوع (صفرُ قراءةٍ من `stdin`)، وبلا مانيفست صار يرجع `rc=0` (**فشلٌ مُغلَقٌ انقلب مفتوحاً**) ⇒
   فالتزامان من الجولة نفسِها (`aa8b70c` · `376f2d1`) نشرا مبلغاً حقيقيًّا إلى `main` العامّ و CI أخضر.
2. **بوابةٌ حمراءُ دائماً ليست بوابة.** كانت تسقط على ٣٩ ظهورًا قائمةً **لا علاقةَ لأيٍّ منها بالدفع**
   ⇒ حافزٌ دائمٌ لتجاوزها (`--no-verify`). العلاجُ **سقاطة** (`docs/security/amount-baseline.json`):
   عددٌ لكلّ ملفّ، بلا قيمٍ ولا بصمات ⇒ يسقط عند أيّ زيادةٍ أو ملفٍّ جديد، ويخضرّ فيما عداه.
3. **المطابِقُ كان أعمى عن ترقيمَين يكتب بهما الكشف:** الفاصلةُ العشريّةُ العتيقة (`N,dd`) لأنّ
   `normalize` كان يحذف كلَّ فاصلة، والإشارةُ لأنّ `canonical` كان يحتفظ بها. المقيس: الحقيقيُّ
   **٤٢ لا ٣٩**، والقيمةُ صارت تُقرأ بـ`norm_num` **الموروث** لا بنسخةٍ ثانية (والقاعدةُ في
   `vlm_reader._parse_amount`: *never re-implement; inherit*).
4. **خريطةُ التطهير كانت بلا حارس:** `SCAN_SKIP` كان يُعفيها بالاسم، و`tracking_audit` لا يفحصها،
   و`publish_guard` يمنع `data/local_sample/` وحدَه ⇒ `git add -f` كان يمرّ من الثلاثة.

**وحدُّ الصدق:** البصماتُ **مُفتَّحةٌ بمفتاحٍ سِرّيّ** (`AMOUNT_GUARD_KEY`) ⇒ لا تُجرَد بغير المفتاح.
**وغيابُ المانيفست فشلٌ مُغلَق** (لا يمرّ صامتاً) إلّا بعلَمٍ صريح `--ci` يعلن أنّ السطحَ العامَّ
بلا أدلّةٍ **بالبناء** فيطبع ما فحصه وما لم يفحصه.

    export AMOUNT_GUARD_KEY=...        # أو ضعه في data/.amount-guard-key (مُهمَل)
    python3 tools/amount_guard.py --build            # يشتقّ من الكوربوس ويُراجع الحساب
    python3 tools/amount_guard.py                    # الفحص (مُتتبَّع + غيرُ متتبَّع)
    python3 tools/amount_guard.py --ratchet           # السقاطة على الشجرة (ملفّاً ملفّاً)
    python3 tools/amount_guard.py --baseline-write    # يكتب خطَّ الأساس (أعدادٌ فقط)
    printf '%s\\n' "$REFS" | python3 tools/amount_guard.py --pre-push   # المدفوع نفسُه
    python3 tools/amount_guard.py --inject            # برهانُ السقوط (سمٌّ من المصدر · سطحان)
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

ROOT = Path(os.environ.get("AMOUNT_GUARD_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT / "src"))


def _data_root() -> Path:
    """**جذرُ الأدلّة (`data/`)**: يُحلّ عبر `git --git-common-dir` فيراه **كلُّ worktree**.

    كان الجذرُ = مكانَ الملفّ ⇒ الدفعُ من worktree (أو من نسخةِ مراجعة) لا يجد المانيفست
    ⇒ `rc=0` صامتًا (وهذا بعينه ما سمح لدفعتين بنشر مبلغٍ حقيقيّ). **والشرطُ يُقاس على
    المانيفست/المفتاح لا على وجود مجلّد `data/`**: نسخةُ العمل فيها `data/sample/` (فيّكسترةٌ
    مُتتبَّعة) ⇒ فحصُ المجلّد وحده كان يوقف التحويل عندها ويُسقط الحارسَ مُغلَقاً بلا داع.
    """
    if _has_evidence(ROOT):
        return ROOT
    r = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                       cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode == 0:
        gd = Path(r.stdout.strip())
        gd = gd if gd.is_absolute() else (ROOT / gd)
        if gd.name == ".git" and _has_evidence(gd.parent):
            return gd.parent
    return ROOT


def _has_evidence(root: Path) -> bool:
    return (root / "data" / "eval_pack" / "amount-manifest.json").exists() or \
           (root / "data" / ".amount-guard-key").exists()


DATA_ROOT = _data_root()
KEY_ENV = "AMOUNT_GUARD_KEY"
MANIFEST = DATA_ROOT / "data" / "eval_pack" / "amount-manifest.json"   # **غيرُ منشور** (مُهمَل)
KEY_FILE = DATA_ROOT / "data" / ".amount-guard-key"                    # **غيرُ منشور** (مُهمَل)
REDACTION_MAP = DATA_ROOT / "data" / "eval_pack" / "amount_redaction_map.json"
BASELINE = ROOT / "docs" / "security" / "amount-baseline.json"         # **منشور**: أعدادٌ فقط
DECLARED_BINARIES = ROOT / "docs" / "security" / "tracked-binaries.txt"
BINARY_DIRS = ("data/", "digital/")
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".xlsx", ".docx"}

_DIGITS = {**{chr(0x0660 + i): str(i) for i in range(10)},
           **{chr(0x06F0 + i): str(i) for i in range(10)}}
_AR = "0-9\u0660-\u0669\u06f0-\u06f9"
TOKEN = re.compile(rf"-?[{_AR}][{_AR},٬\u060c٫]*(?:\.[{_AR}]{{1,2}})?")
#: خاناتُ ما بعد الفاصلة الأخيرة. قاعدةُ الكوربوس (وهي قاعدةُ `norm_num` نفسُها):
#: خانتان = عشريّة · ثلاثٌ = فاصلُ آلاف · أكثرُ من ثلاث = النقطةُ ضاعت · خانةٌ واحدة = عشريّةٌ ناقصة.
FRACTION = re.compile(r"[.,](\d+)-?$")
#: خانةٌ واحدةٌ بعد الفاصلة: تُعاد كتابتُها **بخانتين** فيقرأها المُحلِّل الموروث (لا مُحلِّلٌ ثانٍ).
_ONE_DECIMAL = re.compile(rf"^(-?[{_AR}][{_AR},٬\u060c٫٫.]*[.,٫])([{_AR}])(-?)$")

from statement_qa.legacy.arabic_digit_parser import norm_num   # noqa: E402  (الموروث: لا نسخةَ ثانية)


# ═══════════════════════════ المفتاح ═══════════════════════════

def load_key() -> bytes:
    """مفتاحُ الحارس: بيئة ⇒ ملفٌّ مُهمَل ⇒ **فشلٌ مُغلَق** (لا يمرّ صامتاً)."""
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
    """**درسٌ تكرّر:** تنسيقُ مسارٍ قد يكون خارج المستودع ⇒ `relative_to` ترفع ValueError."""
    for base in (ROOT, DATA_ROOT):
        try:
            return str(path.relative_to(base))
        except ValueError:
            continue
    return str(path)


# ═══════════════════════ القيمةُ والبصمة (الموروث) ═══════════════════════

def normalize(tok: str) -> str:
    """تطبيعٌ **نصّيّ** (للقراءة والبناء الكلّيّ) — لا يُبنى عليه حكمُ مبلغ."""
    s = "".join(_DIGITS.get(c, c) for c in str(tok))
    return s.replace("٫", ".").replace("٬", "").replace("،", "").replace(",", "").strip()


def _pad_fraction(tok: str) -> str:
    """`7777.0` ⇒ `7777.00` — إعادةُ كتابةٍ لا مُحلِّلٌ ثانٍ، والقراءةُ تبقى للموروث."""
    m = _ONE_DECIMAL.match(str(tok))
    return f"{m.group(1)}{m.group(2)}0{m.group(3)}" if m else str(tok)


def parsed_value(tok: str):
    """قيمةُ الرقم **بالمُحلِّل الموروث** (`norm_num`) — وإعادةُ الكتابة عند الخانة الواحدة.

    **وحدُّ المُحلِّل المعلن (قيس هنا ولم يكن معروفاً):** `norm_num` يرفع `ValueError` على أشكالٍ
    مشوّهة (بترَ الأخيرتين فارغاً، مثل `,12345`) — والحارسُ **لا يسقط على بيانات**: يعدّها
    «ليست مبلغاً» ويُعلن عدّها (والعطبُ في المُحلِّل المجمَّد، فيُعلن ولا يُصلح من هنا).
    """
    for cand in (tok, _pad_fraction(tok)):
        try:
            v = norm_num(cand)
        except (ValueError, TypeError, IndexError):
            _PARSER_ERRORS.add(str(tok))
            return None
        if v is not None:
            return v
    return None


#: أشكالٌ رفع فيها المُحلِّلُ الموروث استثناءً — تُعلن بأعدادها ولا تُسقط الحارس
_PARSER_ERRORS: set[str] = set()


def canonical(amount: str) -> str:
    """**الصيغةُ المرجعيّة للبصمة:** المقدارُ (بالإشارة المطلقة) بخانتين — والقيمةُ من `norm_num`.

    **تصحيحُ مراجعة ٣٨ (وهو عطبٌ حاجب):** كان `canonical` يحتفظ بالإشارة ⇒ `X` و`-X` بصمتان،
    وكان `normalize` يحذف الفاصلةَ العشريّةَ العتيقة فيقرأ `300,00` **٣٠٠٠٠** ⇒ المطابِقُ أعمى عن
    ‎`N,dd` وعن الإشارة المقلوبة. **والقيمةُ تُقرأ الآن بالمُحلِّل الموروث** الذي يقرأ الفاصلتين
    ويُعلن الشكّ (`None`) بدل أن يُخمّن — والمقيسُ بعد التصحيح: **٤٢ لا ٣٩**.
    """
    v = parsed_value(amount)
    if v is None:
        return normalize(amount)
    return f"{abs(Decimal(str(v))):.2f}"


def fingerprint(amount: str) -> str:
    return hmac.new(load_key(), canonical(amount).encode(), hashlib.sha256).hexdigest()[:32]


def _decimal_printed(tok: str) -> bool:
    """هل كُتب الرقمُ **بكسرٍ عشريّ**؟ (عددُ خانات آخر مجموعة ≠ ٣ — فالثلاثُ فاصلُ آلاف).

    المُثبتُ مقيس: `300,00` و`543210.99` نعم · `1,234` (آلافٌ) لا · `61,16512` (نقطةٌ ضائعةٌ) نعم.
    """
    s = "".join(_DIGITS.get(c, c) for c in str(tok)).replace("٫", ".")
    m = FRACTION.search(s)
    return bool(m) and len(m.group(1)) != 3


def is_amount_shaped(tok: str) -> bool:
    """**شكلٌ لا قراءة:** الرقمُ كاملٌ من أرقامٍ وفواصل — والقراءةُ للمُحلِّل بعد ذلك.

    **عطبٌ أمسكتُه في هذه الجولة قبل أن يخرج:** أوّلُ صياغةٍ لهذا الشرط استدعت `norm_num` مباشرةً
    ⇒ ومُحلِّلُ البطاقات **يحذف كلَّ ما ليس رقماً** (وهو صحيحٌ لخليّةٍ مقروءة) ⇒ فصار **كلُّ معرّفٍ
    يحمل ٤ أرقام مبلغاً**: المصدرُ قفز من **11,028 إلى 27,309** قيمة. فالشكلُ يُفحَص نصّاً هنا،
    والقيمةُ تُقرأ بالمُحلِّل بعده — **الاثنان معاً، وكلٌّ في موضعه.**
    """
    s = normalize(tok)
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", s):
        return False
    return len(s.lstrip("-").split(".")[0]) >= 4


def is_significant(tok: str) -> bool:
    """**المدى:** ≥٤ خاناتٍ صحيحة **+ كسرٌ عشريّ مقروء** — والقيمةُ يقرّرها `norm_num`.

    (≥٤ خانات: المبالغُ القصيرةُ تتصادم مع أيّ رقم؛ والكسرُ: يفصل المبلغَ عن عدّادٍ أو سنة.
    والاستدارةُ **ليست** شرطًا — القاعدة ١٦.)
    """
    v = parsed_value(tok)
    if v is None or abs(v) < 1000:
        return False
    return _decimal_printed(tok)


def declared_set(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(normalize(line))
    return out


# ═══════════════════════ الاشتقاقُ من المصدر ═══════════════════════

NON_SOURCE = {"data/.amount-guard-key", "data/eval_pack/amount_redaction_map.json",
              "data/eval_pack/amount-manifest.json"}
# **مخرجاتُنا ليست مصدراً** — المانيفستُ وحدَه يُستثنى (قراءةُ ناتجِنا تُدخل رقمَنا في مصدرنا:
# قِيس أنّ ذلك أزاغ `source_shape_ok` بـ+5 وجعل المشيَ يتوقّف على جذر التشغيل). أمّا `pack.json`
# فهو أثرُ قراءةٍ يحمل مبالغَ حقيقيّة ⇒ **يجب** أن يبقى في المدى.


def _walk_amounts(obj, out: set[str]) -> None:
    """**لا نُعدّ المفاتيح — نمشي في الأثر** (الجذرُ الذي أسقط الإصدارَ الأوّل: مفتاحٌ مخمَّن)."""
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


def _artifacts(globs: tuple[str, ...] = ("data/**/*",)):
    """**المصدرُ يُقرأ من `DATA_ROOT` لا من `ROOT` (ثغرةُ مراجعة ٣٩ رقم ١).**

    كان يمشي على `ROOT` ⇒ بناءٌ من worktree مرتبط لا يجد الكوربوسَ ⇒ يكتب **مانيفستاً فارغاً
    إلى النسخة الرئيسيّة** ويُعلن نجاحاً (`rc=0`) ⇒ كلُّ دفعٍ بعده يمرّ. وهذا بعينه نمطُ
    العطب الأصليّ: *مصدرٌ أعمى يُنتج صفراً يُقرأ كنجاح*. والقاعدةُ هنا: **صفرُ مدخلٍ ليس نتيجةً**.
    """
    for pat in globs:
        for f in sorted(DATA_ROOT.glob(pat)):
            if not f.is_file() or f.suffix.lower() not in {".json", ".jsonl"}:
                continue
            rel = str(f.relative_to(DATA_ROOT))
            if rel in NON_SOURCE:
                continue
            yield f, rel


def _artifact_values(path: Path) -> set[str]:
    vals: set[str] = set()
    try:
        if path.suffix.lower() == ".jsonl":
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    _walk_amounts(json.loads(line), vals)
        else:
            _walk_amounts(json.loads(path.read_text(encoding="utf-8")), vals)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        pass
    return vals


def source_amounts() -> tuple[set[str], int, int, dict[str, int]]:
    """المصدرُ = **اتّحادُ كلّ أثرٍ بياناتيّ محليّ** (والأدلّةُ محفوظةٌ في `data/`)."""
    got: set[str] = set()
    files = 0
    per: dict[str, int] = {}
    for f, rel in _artifacts():
        vals = _artifact_values(f)
        if not vals:
            continue
        before = len(got)
        got |= vals
        files += 1
        per[rel] = len(got) - before
    return got, files, len(got), per


def coverage_gaps(deny: set[str]) -> list[tuple[str, str]]:
    """**حارسُ التغطية:** أيُّ مبلغٍ في أثرٍ محليٍّ ليس في المانيفست = ثقبٌ في الاشتقاق."""
    gaps: list[tuple[str, str]] = []
    for f, rel in _artifacts():
        for v in _artifact_values(f):
            if is_significant(v) and fingerprint(v) not in deny:
                gaps.append((rel, v))
    return gaps


def build(_extra: list[str]) -> int:
    src, files, total, per = source_amounts()
    significant = {a for a in src if is_significant(a)}
    entered = significant
    ex_trivial = total - len(significant)   # قصيرةٌ/بلا كسر ⇒ خارجُ المدى بالبناء
    ex_synth = 0
    derivation = {
        "artifact_files": files, "source_shape_ok": total, "entered": len(entered),
        "top_artifacts": dict(sorted(per.items(), key=lambda x: -x[1])[:6]),
        "excluded_trivial": ex_trivial, "excluded_synthetic": ex_synth,
        "published": False,
        "published_because": "البصماتُ لا تُنشر: الجردُ يحتاج المفتاح، ونشرُها دفاعٌ في العمق لا ضرورة",
        "scope": "≥٤ خاناتٍ صحيحة + كسرٌ عشريّ مقروء (فاصلةٌ عتيقةٌ أو نقطة) — والقيمةُ من norm_num",
        "rule": "الاستدارةُ صفةُ المبلغ لا دليلُ صناعيّته (تصحيح مراجعة ٣٦) · المقدارُ لا الإشارة (٣٨)",
    }
    if total != len(entered) + ex_trivial + ex_synth:
        raise SystemExit(f"⛔ فجوةٌ غيرُ مُعلَنة: {total} ≠ {len(entered)}+{ex_trivial}+{ex_synth}"
                         " ⇒ البناءُ يسقط (لا يُنشر مانيفستٌ ناقص)")
    if files == 0:
        raise SystemExit(
            f"⛔ صفرُ ملفَّ مصدرٍ في {_shown(DATA_ROOT)} ⇒ البناءُ يسقط ولا يُكتب مانيفست.\n"
            "   (صفرٌ يُقرأ كانجاحٍ كان يُفرغ الحارسَ صامتاً — القاعدة: صفرُ مدخلٍ ليس نتيجة.)")
    if not entered:
        raise SystemExit(
            f"⛔ صفرُ قيمةٍ داخلةٍ في المدى من {files} ملفّاً ⇒ البناءُ يسقط (لا مانيفستَ فارغ).")
    fps = sorted({fingerprint(a) for a in entered})
    # **بصمةُ المجموعة:** تُكشف تبديلَ قيمةٍ بأخرى (وهو ما لا يراه عدّادٌ يقارن الأعداد وحدها).
    digest = hmac.new(load_key(), "\n".join(fps).encode(), hashlib.sha256).hexdigest()
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        "what": "بصماتُ مبالغَ حقيقية — مُفتَّحةٌ بمفتاحٍ سِرّيّ (خارج الشجرة) ⇒ لا تُجرَد بلا مفتاح",
        "how": "AMOUNT_GUARD_KEY=… python3 tools/amount_guard.py --build",
        "keyed": True,
        "count": len(fps),                 # البصماتُ الفريدة (المقاسُ الحقيقيّ)
        "source_formats": len(entered),    # صيغُ المصدر الداخلة (قد تتعدّد للقيمة الواحدة)
        "set_digest": digest,
        "derivation": derivation,
        "fingerprints": fps,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"المانيفست: {len(entered)} صيغةً ⇒ {len(fps)} بصمةً فريدة · "
          f"الاشتقاق: {total} = {len(entered)} + {ex_trivial} تافهة + {ex_synth} صناعية · {files} أثراً")
    gaps = coverage_gaps({fingerprint(a) for a in entered})
    if gaps:
        print(f"⛔ فجوةُ تغطية: {len(gaps)} مبلغاً في أثرٍ محليٍّ خارجَ المانيفست ⇒ الاشتقاقُ ناقص:")
        for rel, v in gaps[:8]:
            print(f"   {rel} ← {_mask(v)}")
        return 1
    print("تغطية ✓ — كلُّ مبلغٍ في آثار data/ داخلَ المانيفست (لا مفتاحَ مفقود)")
    return 0


def _mask(v) -> str:
    """**لا يُطبع مبلغٌ حقيقيّ** في أيّ مخرَجٍ يمكن أن يُقرأ أو يُلتقط في سجلّ."""
    s = str(v)
    return s[0] + "#" * (len(s) - 1) if s else ""


def load_deny() -> set[str] | None:
    """**None = سطحٌ عامٌّ بلا أدلّة** ⇒ يُعلن **ويسقط مُغلَقاً**، إلّا بعلَمٍ صريح `--ci`."""
    if not MANIFEST.exists():
        return None
    fps = set(json.loads(MANIFEST.read_text(encoding="utf-8"))["fingerprints"])
    # **مانيفستٌ فارغٌ ليس أدلّة** (أمسكه مقعدُ المعايير): كان set() ⇒ كلُّ عدّادٍ صفر ⇒ PASS بلا فحص.
    return fps or None


def _manifest_blind() -> str:
    return ("⚠ سطحٌ عامٌّ بلا أدلّة: لا مانيفستَ (لا يُنشر بالتصميم — بصمةٌ منشورةٌ معها سِرٌّ "
            "تُجرَد). الإنفاذُ محليٌّ: في `.githooks/pre-push` حيث توجد `data/`.")


# ═══════════════════════ الفحص ═══════════════════════

def find_in_text(txt: str, deny: set[str]) -> list[tuple[str, str]]:
    """**المدى شرطُ المطابقة، والبصمةُ تتولّى فروقَ الكتابة** — و`deny` يُمرَّر صريحاً.

    (كان `scan()` يُعيد قراءة المانيفست داخلَه، ويمرّره إلى هنا **None** عند السطح العامّ
    ⇒ `TypeError` غامض. صار المعاملُ إلزاميًّا: لا مسارَ صامتَ إلى `None`.)
    """
    out: list[tuple[str, str]] = []
    for m in TOKEN.finditer(txt):
        t = m.group(0)
        if not is_significant(t):
            continue
        if fingerprint(t) in deny:
            out.append((t, canonical(t)))
    return out


def tracked_text_files() -> list[str]:
    """المُتتبَّع **وغيرُ المتتبَّع غيرُ المُهمَل**: الحارسُ يحرس ما على وشك أن يُدفع."""
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"],
                         cwd=str(ROOT), capture_output=True, text=True).stdout
    return [f for f in out.split() if Path(f).suffix.lower() not in BINARY]


def tracked_files() -> list[str]:
    return subprocess.run(["git", "ls-files"], cwd=str(ROOT),
                          capture_output=True, text=True).stdout.split()


def _text_of_rel(rel: str) -> str | None:
    try:
        return (ROOT / rel).read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def counts_by_file(deny: set[str], files: list[str] | None = None) -> dict[str, int]:
    """عددُ الظهورات **ملفّاً ملفّاً** — لا قيمةَ ولا بصمة. هذا هو ما تُقارنه السقاطة."""
    counts: dict[str, int] = {}
    for rel in (files if files is not None else tracked_text_files()):
        txt = _text_of_rel(rel)
        if txt is None:
            continue
        n = len(find_in_text(txt, deny))
        if n:
            counts[rel] = n
    return counts


def pre_push_checks() -> int:
    """فحصا **كلّ** مسار دفع — التعفّنُ والثنائياتُ غيرُ المُعلَنة (T-5 · مراجعة ٤٥ S-3).

    كانا بعد `return` فرعَي `--pre-push` و`--ratchet` ⇒ **لا يبلغهما الخطّاف أبداً**. وبعد النقل
    صارا في موضعٍ واحدٍ يُستدعى من كلّ مسار — **ولهما سمٌّ**: مانيفستٌ متعفّن ⇒ يُخرج ١ بالاسم.
    """
    if undeclared_binaries():
        print("⛔ BLOCK — ثنائيٌّ مدفوعٌ تحت data/ أو digital/ بلا إعلان:")
        for f in undeclared_binaries()[:10]:
            print(f"   {f}")
        return 1
    stale = staleness()
    if stale:
        print(stale)
        return 1
    return 0


def undeclared_binaries() -> list[str]:
    declared = declared_set(DECLARED_BINARIES)
    out = subprocess.run(["git", "ls-files"], cwd=str(ROOT), capture_output=True, text=True).stdout
    return [f for f in out.split()
            if f.startswith(BINARY_DIRS) and Path(f).suffix.lower() in BINARY and f not in declared]


# ═══════════════════════ السقاطة (الخطّاف الذي يخضرّ) ═══════════════════════

def _baseline_norm(obj: dict | None) -> dict[str, dict]:
    """**القارئُ يطبّع الصيغتين:** العدّادُ المجرّد (ما نُشر سابقاً) و(عدّادٌ + بصمةُ مجموعة)."""
    out: dict[str, dict] = {}
    for rel, v in ((obj or {}).get("counts") or {}).items():
        out[rel] = {"count": int(v)} if isinstance(v, int) else {
            "count": int(v["count"]), "commitment": v.get("commitment")}
    return out


def baseline_at(rev: str) -> dict[str, dict] | None:
    """**العتبةُ من التزامٍ بعينه، لا من الشجرة العاملة (ثغرةُ ٣٩ رقم ٣أ/٣ب).**

    كان `--pre-push` يقرأها من الشجرة ⇒ الدافعُ يرفع عتبتَه فيمرّ. الآن العتبةُ =
    **المنشورُ على `origin/main`**، وما سينشره الدفعُ يُقارَن به ولا يرفعه.
    """
    r = _git("show", f"{rev}:{REL_BASELINE}")
    if r.returncode != 0:
        return None                       # غيرُ موجود ⇒ غيرُ مقروء (يُسقط)
    try:
        return _baseline_norm(json.loads(r.stdout))   # **فارغٌ شرعاً ≠ غيرُ مقروء**: {} = صفرُ دَين
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def baseline_audit(ref: str) -> int:
    """**مقارنةُ عتبةٍ بمفتاحٍ صفر:** خطُّ الأساس في هذه الشجرة مقابل خطٍّ منشورٍ في `ref`.

    لا مانيفستَ ولا مفتاحَ ولا دفعَ — **ملفّان مُتتبَّعان يُقارَنان**، ولذلك موضعُها في `main()`
    **قبل** أيّ فرعٍ يعتمد على الأدلّة. وكانت بعدها ⇒ في CI (بلا مانيفست) يخرج البرنامجُ من
    فرع «السطح العامّ» قبل أن يبلغها، فتُطبع «PASS (بما أُمكن فحصُه)» على عتبةٍ مرفوعة
    (مراجعة ٤٠، البند ١ — مقيسٌ في السجلّ وفي نسخةٍ نظيفة).
    """
    base = baseline_at(ref)
    if base is None:
        # عتبةٌ غيرُ مقروءة ⇒ لا أستبدلها بخطّ الشجرة العاملة، ولا أمرّ صامتاً.
        print(f"⛔ BLOCK — لا أساسَ مقروءاً من {ref} ⇒ لا أُثبت شيئاً "
              "(بوّابةٌ لا تستطيع العمل لا تمرّ)")
        return 2
    here = read_baseline()
    bad_rows = ratchet_violations(here, base, f"خطُّ الأساس المدفوع مقابل {ref}")
    if bad_rows:
        print(f"⛔ BLOCK — خطُّ الأساس في هذه الشجرة يرفع العتبةَ عن {ref}:")
        for b in bad_rows[:25]:
            print("   " + b)
        return 1
    print(f"PASS — خطُّ الأساس لا يرفع عتبةً عن {ref} "
          f"({sum(v['count'] for v in here.values())} ظهوراً مُعلَناً، بلا مفتاحٍ ولا أدلّة)")
    return 0


def read_baseline() -> dict[str, dict]:
    if not BASELINE.exists():
        return {}
    try:
        return _baseline_norm(json.loads(BASELINE.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError, KeyError):
        return {}


def _commitment(fps: set[str]) -> str:
    """**بصمةُ المجموعة** (مُفتَّحةٌ بالمفتاح): تكشف تبديلَ قيمةٍ بأخرى عند العدّاد نفسِه،
    ولا تُجرَد بلا مفتاح ⇒ يجوز نشرُها في خطّ الأساس العامّ."""
    return hmac.new(load_key(), "\n".join(sorted(fps)).encode(), hashlib.sha256).hexdigest()[:16]


def counts_with_commitment(deny: set[str], files: list[str] | None = None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for rel in (files if files is not None else tracked_text_files()):
        txt = _text_of_rel(rel)
        if txt is None:
            continue
        hits = find_in_text(txt, deny)
        if hits:
            out[rel] = {"count": len(hits),
                        "commitment": _commitment({fingerprint(t) for t, _ in hits})}
    return out


def write_baseline(deny: set[str], accept_increase: bool = False) -> int:
    """**ولا يُرفع أبداً (ثغرةُ ٣٩ رقم ٣):** كتابةٌ تزيد عدداً أو تبدّل بصمةً عند العدّ نفسِه
    تُرفَض؛ وما عدا ذلك يجوز (التخفيضُ بالتصحيح لا بالمسح)."""
    counts = counts_with_commitment(deny)
    cur = read_baseline()
    raised = ratchet_violations(counts, cur, "كتابةُ خطّ الأساس")
    if raised and not accept_increase:
        print("⛔ BLOCK — خطُّ الأساس لا يُرفع (القاعدة ١٢: لا يُعفى موضع، تُغيَّر القيمة):")
        for b in raised[:25]:
            print("   " + b)
        print("   ⇒ وإن كان الرفعُ مقصوداً: --accept-increase \"السبب\" (والخطّافُ يمنع دفعه)")
        return 1
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps({
        "what": "خطُّ أساسِ الظهورات — **أعدادٌ فقط**: لا قيمةَ ولا بصمةَ مبلغٍ (فلا يُنشر ما يُجرَد)",
        "how": "python3 tools/amount_guard.py --baseline-write   # يُخفَّض بالتصحيح لا بالمسح",
        "rule": ("لا يُعفى موضع (القاعدة ١٢) — الخطُّ مؤقّتٌ يُخفَّض بإعادة كتابة القيم، "
                 "ولا يُرفع أبداً: أداةُ --build لا تلمسه"),
        "counts": {k: v for k, v in sorted(counts.items())},
        "total": sum(v["count"] for v in counts.values()),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"خطُّ الأساس: {sum(v['count'] for v in counts.values())} ظهوراً في {len(counts)} ملفّاً ⇒ {_shown(BASELINE)}")
    return 0


def block_claim(bad: list[str], subject: str = "الدفعُ يحمل") -> tuple[str, list[str], bool]:
    """**وسمٌ لا يعدو دليله:** تُصنَّف بنودُ الإسقاط قبل أن تُصاغ اللافتة.

    «مدخلٌ غيرُ مقروء في السقاطة» (عتبةٌ أو خطُّ أساسٍ مفقودٌ في الفرع) **ليس** ظهورًا لمبلغ؛ وكانت
    اللافتةُ تحكم «مبالغَ حقيقيّة» على هذا السبب وحده فتعدو دليلَها. الآن:
    - بنودٌ حقيقيّة موجودة ⇒ اللافتةُ نفسُها (ومعها عددُ غير المقروء صريحًا).
    - ولا بنودَ حقيقيّة ⇒ لافتةٌ تقول «لا أُثبت نظافةً ولا ظهورًا» — **بلا** ادّعاءٍ على المبالغ.
    """
    unreadable = [b for b in bad if "غيرُ مقروء" in b]
    real = [b for b in bad if b not in unreadable]
    if real:
        extra = f" — ومعه {len(unreadable)} مدخلٌ غيرُ مقروء" if unreadable else ""
        return (f"⛔ BLOCK — {subject} ظهوراتٍ لمبالغَ حقيقيّة (نصوصٌ لا تُطبع){extra}:",
                real + unreadable, True)
    return (f"⛔ BLOCK — {subject} لا يُثبت نظافةً ولا ظهورًا: مدخلُ السقاطة غيرُ مقروء "
            f"({len(unreadable)}) ⇒ «غيرُ المقروء ليس نظيفاً» (القاعدة ١٢) — ولا ادّعاءَ على المبالغ هنا:",
            unreadable, False)


def ratchet_violations(counts: dict[str, dict] | None, base: dict[str, dict] | None,
                       where: str) -> list[str]:
    """**السقاطة:** تسقط عند زيادةِ عددٍ · ملفٍّ جديد · **أو تبديلِ قيمةٍ بأخرى عند العدّ نفسِه**
    (ببصمة المجموعة — وهو ما لا يراه عدّادٌ يقارن الأعدادَ وحدها)، وتخضرّ فيما عدا ذلك.

    **وغيابُ العتبة أو العدّاد يُسقط باسمه ولا يُنهي البرنامج** (عطبٌ صنفيّ · الجولة ٦١):
    `baseline_at()` تُعيد `None` شرعاً حين لا يكون خطُّ الأساس موجوداً في ذلك الالتزام (فرعٌ
    أساسُه أقدمُ من الخطّ) — وكان `None` يُمرَّر إلى `.items()` فيسقط الخطّافُ بـ`AttributeError`
    **قبل** أن يحكم، فكان يُقرأ **انهيارٌ** مكان **حُكمٍ**، ويمنع دفعاً مشروعاً بلا اسمِ سبب.
    والقاعدةُ المعلنة: «غيرُ المقروء ليس نظيفاً» ⇒ **BLOCK بالاسم**.
    """
    if counts is None or base is None:
        # **ولا يُخمَّن الدورُ من موضعِ الوسيط** (تصحيحٌ بعد قياس): في `--pre-push` يُنادى
        # بهذه الدالّة مرّتان بترتيبين مختلفَي المعنى — فالأولُ هناك **خطُّ الأساس المنشورُ في
        # الالتزام** لا «العدّاد»؛ فكان وسمُ «العدّاد» يُشير إلى غير موضعه. الوسمُ الآن دورٌ
        # محايد، والموضعُ المُصلَح يُسمّيه `where` بنفسه.
        return [f"⛔ مدخلٌ غيرُ مقروء في السقاطة (عتبةٌ أو عدّاد) ⇒ لا أُثبت نظافةَ الظهورات — "
                f"«غيرُ المقروء ليس نظيفاً» (القاعدة ١٢) — {where}"]
    bad: list[str] = []
    for rel, cur in sorted(counts.items(), key=lambda x: -x[1]["count"]):
        b = base.get(rel)
        n, n0 = cur["count"], (b or {}).get("count")
        if b is None:
            bad.append(f"⛔ ملفٌّ جديدٌ يحمل ظهوراتٍ حقيقيّة: {rel} ({n}) — {where}")
        elif n > n0:
            bad.append(f"⛔ زادت الظهوراتُ: {rel} {n0} → {n} — {where}")
        elif n == n0 and b.get("commitment") and cur.get("commitment") != b["commitment"]:
            bad.append(f"⛔ تبديلُ قيمةٍ بأخرى عند العدد نفسِه: {rel} ({n}) — {where}")
    return bad


# ═══════════════════════ المدفوعُ نفسُه ═══════════════════════

def _git(*args: str, text: bool = True):
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=text)


def _git_here(*args: str):
    """git في **المستودع الذي أُنفِّذ فيه الأمر** (لا في جذر الأداة).

    (لماذا: مسحُ التاريخ يقيس المستودعَ المقصود؛ ولو مشى على `ROOT` لكان مسحُ مستودعٍ آخر
    يمرّ كأنّه مسحُ هذا ⇒ **فشلٌ مفتوحٌ صامت**.)
    """
    return subprocess.run(["git", *args], capture_output=True, text=True)


class UnresolvedRange(RuntimeError):
    """**ثغرةُ مراجعة ٣٩ رقم ٢:** رأسٌ بعيدٌ غيرُ مجلوب ⇒ `rev-list` يفشل ⇒ كان الخطأُ مُهمَلاً
    فيمرّ الدفعُ `rc=0` بلا فحص. **مدىً لم أُثبته ليس مدىً نظيفاً.**"""


REL_BASELINE = "docs/security/amount-baseline.json"


# ── طبقةٌ واحدةٌ لسؤالٍ واحد: **ما يُنشَر؟** (مُحلِّلٌ واحد · وجهةٌ واحدة · قرارٌ واحد) ──
HEX = set("0123456789abcdef")


def _is_sha(s: str) -> bool:
    """sha1 (٤٠ خانة) **وsha256 (٦٤)** — مقيسٌ أنّ git 2.54 على مستودعٍ `--object-format=sha256`
    يرسل ٦٤ خانة، فاشتراطُ ٤٠ وحدَها يُسقط كلَّ دفعٍ `rc=2` (مقعدُ المعايير، مراجعة ٤١/٢)."""
    return len(s) in (40, 64) and set(s.lower()) <= HEX


def _remote_names() -> list[str]:
    return _git("remote").stdout.split()


def _zero(s: str) -> bool:
    return set(s) <= {"0"}


def parse_refs(stream: str) -> tuple[list[tuple[str, str]], int]:
    """`stdin` مرّةً واحدة ⇒ (مراجعُ (محلي, بعيد), عددُ الأسطر التي **لم أقرأها**).

    **«لم أقرأ» ≠ «لا شيءَ يُدفع»:** شكلُ سطر `pre-push` أربعةُ حقولٍ بالضبط، فكلُّ سطرٍ آخر
    (مقصوصٌ أو مبتور) **يُعَدّ** فاسداً لا مُهمَلاً — ومجرى مقصوص (القاعدة ١٩) يُسقَط مُغلَقاً
    لا أن يمرّ بمدىً فارغٍ يُقرأ «لا شيءَ يُنشر». ومُحلِّلٌ واحدٌ يعني أنّ `pushed_revs` و
    `_local_heads` لا يمكن أن يفترقا على الحالة نفسها. (مقعدا المواصفة والبنية، مراجعة ٤١.)
    """
    pairs: list[tuple[str, str]] = []
    bad = 0
    for line in stream.splitlines():
        if not line.strip():
            continue
        p = line.split()
        # **الحقلُ الأول ليس مرجعاً دائماً** — مقيسٌ من git نفسِه (لا من ظنٍّ):
        #   `git push origin HEAD:refs/heads/x` ⇒ `HEAD <sha> refs/heads/x <zeros>`
        #   `git push origin <sha>:refs/heads/y` ⇒ `<sha> <sha> refs/heads/y <zeros>`
        #   `git push origin --delete x`        ⇒ `(delete) <zeros> refs/heads/x <sha>`
        # واشتراطُ `refs/` في الحقل الأول **رفض ثلاثَ صيغٍ مشروعة** بـ`rc=2` (وفيها الحذفُ الذي
        # ادّعيتُ أنّه يمرّ — فسقط الادّعاء بالقياس). فيُفحَص **الشكل**: حقلان sha صحيحان، ومقصدٌ مرجع.
        if len(p) != 4 or not p[2].startswith("refs/") or not _is_sha(p[1]) or not _is_sha(p[3]):
            bad += 1
            continue
        pairs.append((p[1], p[3]))
    return pairs, bad


def _rev_list(args: list[str], what: str) -> list[str]:
    r = _git("rev-list", *args)
    if r.returncode != 0:
        last = (r.stderr.strip().splitlines() or ["rev-list فشل"])[-1][:120]
        raise UnresolvedRange(f"{what} :: {' '.join(args)} :: {last}")
    return r.stdout.split()


def _unpublished(local_sha: str, remote_sha: str, remote: str | None) -> list[str]:
    """ما يُنشَر من مرجعٍ واحد: **مقيساً مقابل وجهة الدفع** لا مقابل كلّ الريموتات.

    (هذا إغلاقُ فتحٍ أدخلته هذه الجولة: `--not --remotes` **تطرح مراجعَ كلِّ ريموت**، فالتزامٌ
    يعرفه ريموتٌ ثانٍ — نسخةٌ احتياطيّة — يُقرأ «منشوراً» ⇒ `PASS` بينما الدفعُ إلى `origin`
    ينشره. الفراغُ يجب أن يُقاس مقابل **الوجهة** وحدَها. مقعدُ البنية، مراجعة ٤١.)

    وكلُّ اشتقاقٍ متدهورٍ يُعلَن بجملة — لا صمتٌ: العدّادُ في سطر النجاح لا يجوز أن يوصف
    بأنّه «ما فُحص» إن كان مدىً مُستبدَلاً. (مقعدُ المعايير، ٤١.)
    """
    if _zero(local_sha):
        return []                                    # حذفُ فرع: لا شيءَ يُنشَر
    if not _zero(remote_sha):
        r = _git("rev-list", f"{remote_sha}..{local_sha}")
        if r.returncode == 0:
            return r.stdout.split()                  # الوجهةُ تعرف الأساس ⇒ المدى مضبوطٌ بالتعريف
    if remote and remote in _remote_names():
        # **بدون نجمة:** `rev-list <sha> --not refs/remotes/R/*` **لا يوسّع النجمةَ كمرجع**
        # (تُقرأ `pathspec` ⇒ مدىً فارغٌ كاذب — مقيسٌ في sandbox) ⇒ تُعدَّد مراجعُ الوجهة صراحةً.
        tracked = _git("for-each-ref", "--format=%(objectname)", f"refs/remotes/{remote}/").stdout.split()
        if tracked:
            return _rev_list([local_sha, "--not", *tracked], f"ما لم تعرفه وجهةُ الدفع `{remote}`")
        # اسمُ ريموتٍ **معروف** ولم تُجلَب مراجعُه ⇒ لا أُثبت المدى، والوصفةُ موجودة (fetch).
        raise UnresolvedRange(f"وجهةُ الدفع `{remote}` معروفةٌ ولم تُجلَب مراجعُها ({local_sha[:8]})")
    if remote:
        # **وجهةٌ مُسمّاةٌ لا أعرفها محليّاً** (رابطٌ أو مسارٌ في `$1`): لا مراجعَ لها نستثنيها،
        # **ولا `--not --remotes`** — فهي تطرح مراجعَ ريموتٍ آخر (نسخةٍ احتياطيّة) فتُفرغ المدى
        # ⇒ `PASS` كاذب (قِيس: ١ ← ٠ التزام). فيُفحَص **كلُّ ما يمكن أن يُنشَر**، ويُعلَن مع الوصفة.
        print(f"⚠ الوجهة `{remote}` ليست اسمَ ريموتٍ معروفاً محليّاً ⇒ المدى = كلُّ ما يمكن أن يُنشَر "
              f"({local_sha[:8]}) بلا استثناء — وللدقّة: أضِفها ريموتاً باسم (`git remote add`) "
              f"وادفع بالاسم. يُعلن ولا يُخفى.")
        return _rev_list([local_sha], "المدى الكامل لوجهةٍ مُسمّاةٍ لا أعرفها محليّاً")
    # **ولا وجهةَ مُعلَنة** (خطّافٌ قديمٌ لا يمرّرها): التقريبُ بطرح مراجع الريموتات المعروفة —
    # **ويُعلَن** لأنّه قد يُخفي ما تعرفه وجهةٌ أخرى (وهو الحدُّ المقيس في هذه الطبقة).
    print("⚠ لا وجهةَ دفعٍ مُعلَنة ⇒ المدى تقريباً بطرح مراجع الريموتات المعروفة (قد يُخفي ما "
          "تعرفه وجهةٌ أخرى) — للدقّة: مرّر وجهةَ الدفع. يُعلن ولا يُخفى.")
    return _rev_list([local_sha, "--not", "--remotes"], "احتياطُ --not --remotes (بلا وجهةٍ مُعلَنة)")


def pushed_revs(refs: str, remote: str | None = None) -> list[str]:
    """**مراجعُ الدفع من `stdin`** — طبقةٌ واحدةٌ **هنا**: `parse_refs` ثم `_unpublished` لكلّ مرجع.

    **وحدُّها المُعلَن (دَينٌ بمالك):** `publish_guard` ما زال يحمل مُحلِّلاً ثانياً ومدىً لا يعرف وجهةَ
    الدفع ⇒ الحارسان **قد يريان مجموعتين** (مقعدُ البنية، مراجعة ٤١/٣: قِيس ٠ التزامات مقابل ١ على
    التزامٍ تعرفه نسخةٌ احتياطيّة). توحيدُهما في وحدةٍ مشتركة دفعةٌ قائمةٌ بذاتها.
    (وكانت هنا دعوى «حتى لا يرى حارسان مجموعتين» — **أسقطها القياسُ فصُحّحت**.

    (وهنا كان العطبُ: `--pre-push` في الإصدار الثاني **لا يقرأ `stdin` إطلاقاً** ⇒ لا يرى التزاماً
    وسيطًا مثل `e819e65` الذي حمل المبلغ. وكان سؤالُ «ما لم يعرفه الريموت» **ثلاثَ نسخٍ جزئيّة**
    بعباراتٍ مختلفة ⇒ أُعيد إلى طبقةٍ واحدة: `parse_refs` ثم `_unpublished` لكلّ مرجع.)
    """
    pairs, _bad = parse_refs(refs)
    revs: set[str] = set()
    for local_sha, remote_sha in pairs:
        revs.update(_unpublished(local_sha, remote_sha, remote))
    return sorted(revs)


def _local_heads(refs: str) -> list[str]:
    return [local for local, _ in parse_refs(refs)[0] if not _zero(local)]


def _range_from_heads(heads: list[str], remote: str | None = None) -> list[str] | None:
    """**المدى من المراجع المدفوعة أنفسِها — لا من `HEAD`** (مراجعة ٤٠، البند ٢).

    كان الاحتياطُ يشترط `rev-list HEAD --not --remotes`: فرعٌ متسرّبٌ يُدفع و`HEAD` يحمل
    التزاماً نظيفاً ⇒ **فحصَ فرعاً آخر** ومرّ التسرّبُ `rc=0` (مقيسٌ في sandbox). و`HEAD` ليس
    ما يُدفع؛ والمراجعُ على `stdin` هي المصدرُ الوحيدُ لِما يُدفع ⇒ غيابُها عطبُ سباكةٍ
    **يُسقَط مُغلَقاً**، لا يُخمَّن له بديل. والمدى هنا يُقاس **مقابل وجهة الدفع** كذلك.
    """
    if not heads:
        return None
    revs: set[str] = set()
    for sha in heads:
        try:
            revs.update(_unpublished(sha, "0" * 40, remote))
        except UnresolvedRange:
            return None
    return sorted(revs)


def pushed_counts(deny: set[str], revs: list[str]) -> dict[str, dict]:
    """**كلُّ blob يُدفع** (لا الشجرةُ العاملة): أحدثَ ظهورٍ لكلّ مسار داخل المدى.

    والقارئُ **لا يفترض أنّ المدفوعَ نصّ**: أيُّ blobٍ لا يُفكّ بـ`utf-8` يُتخطّى بصمتٍ مقصود
    (كما يفعل `publish_guard` مع الثنائيّات غيرِ القابلة للفكّ). وقِيس ذلك حيًّا: **الدفعُ الحقيقيّ
    أسقط هذا الحارسَ بـ`UnicodeDecodeError`** لأنّ `text=True` يفترض نصًّا — والخطّافُ منعه
    (fail-closed) فأمسك العطبَ قبل أن يخرج.
    """
    counts: dict[str, dict] = {}
    for rev in revs:
        names = _git("diff-tree", "-r", "--no-commit-id", "--name-only", "--root", rev).stdout.split()
        for rel in names:
            if Path(rel).suffix.lower() in BINARY:
                continue
            r = _git("show", f"{rev}:{rel}", text=False)
            if r.returncode != 0:
                continue
            try:
                txt = r.stdout.decode("utf-8")
            except UnicodeDecodeError:
                continue
            hits = find_in_text(txt, deny)
            if hits:
                cur = {"count": len(hits),
                       "commitment": _commitment({fingerprint(t) for t, _ in hits})}
                if rel not in counts or cur["count"] > counts[rel]["count"]:
                    counts[rel] = cur          # أحدثُ ظهورٍ للمسار داخل المدى
    return counts


# ═══════════════════════ حارسُ الإهمال ═══════════════════════

def tracking_audit() -> list[str]:
    """**الحارسُ الذي كان غائباً:** الإهمالُ **واقعٌ يُقاس** لا اعتقادٌ يُكتب.

    ١) المفتاحُ والمانيفستُ **وخريطةُ التطهير** غيرُ متتبَّعة · ٢) و`git check-ignore` يُهملها فعلاً ·
    ٣) **وقيمةُ المفتاح لا تظهر في أيّ ملفٍّ متتبَّع** · ٤) **ولا بصماتٍ منشورة** — **ويُعلن ما لم يُفحَص**.
    """
    bad: list[str] = []
    for path in (KEY_FILE, MANIFEST, REDACTION_MAP):
        rel = _shown(path)
        if subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel],
                          cwd=str(ROOT), capture_output=True, text=True).returncode == 0:
            bad.append(f"⛔ متتبَّعٌ في git: {rel} — أخرِجه بـ`git rm --cached` (والملفُّ باقٍ محليًّا)")
        if subprocess.run(["git", "check-ignore", "-q", "--", rel],
                          cwd=str(ROOT), capture_output=True, text=True).returncode != 0:
            bad.append(f"⛔ `git check-ignore` لا يُهمله: {rel} — «مُهمَل» في التوثيق ليست واقعةً")
    key = os.environ.get(KEY_ENV, "").strip()
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip()
    fps: set[str] = set()
    if MANIFEST.exists():
        fps = set(json.loads(MANIFEST.read_text(encoding="utf-8"))["fingerprints"])
    for rel in tracked_files():
        p = ROOT / rel
        if p.suffix.lower() in BINARY:
            continue
        try:
            txt = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if key and key in txt:
            bad.append(f"⛔ قيمةُ المفتاح ظاهرةٌ في ملفٍّ متتبَّع: {rel} ⇒ المفتاحُ محروقٌ (دوّرْه)")
        if fps and sum(1 for f in fps if f in txt) >= 20:
            bad.append(f"⛔ البصماتُ منشورةٌ في {rel} (≥٢٠ بصمة) ⇒ تُجرَد بمن يملك المفتاح ⇒ احتفظ بها داخل data/")
    return bad


def tracking_audit_message() -> str:
    """**لا يُدَّعى فحصٌ لم يُجرَ:** كانت الرسالةُ تقول «ولا بصماتٍ منشورة» في CI حيث لا مانيفست."""
    if MANIFEST.exists():
        return "PASS — المفتاحُ والمانيفستُ وخريطةُ التطهير غيرُ متتبَّعة ومُهمَلة واقعاً، ولا بصماتٍ منشورة"
    return ("PASS (بما أُمكن فحصُه) — الثلاثةُ غيرُ متتبَّعة ومُهمَلة واقعاً · "
            "**والبصماتُ لم تُفحَص: لا مانيفستَ على هذا السطح**")


# ═══════════════════════ التعفّن ═══════════════════════

def staleness() -> str | None:
    """**المانيفستُ يتعفّن:** إن تغيّر المصدرُ ولم يُبِن أحدٌ ⇒ الفحصُ يسقط.

    **تصحيحُ مراجعة ٣٨:** كان يقارن العددين وحدَهما ⇒ **تبديلُ قيمةٍ بأخرى يمرّ** (٤,٢٧٢ = ٤,٢٧٢).
    صار يقارن **بصمةَ المجموعة المرتّبة** كذلك، وهي تكشف أيَّ تبديل.
    """
    if not MANIFEST.exists():
        return None
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    want = data["derivation"]["source_shape_ok"]
    src, _, total, _ = source_amounts()
    if total == 0:
        return None
    if total != want:
        return (f"⛔ المانيفستُ متعفّن: المصدرُ اليوم {total} قيمةً والمانيفستُ يقول {want} ⇒ أعِد البناءَ")
    fps = sorted(data["fingerprints"])
    digest = hmac.new(load_key(), "\n".join(fps).encode(), hashlib.sha256).hexdigest()
    if digest != data.get("set_digest"):
        return "⛔ المانيفستُ متعفّن: بصمةُ المجموعة لا تطابق نفسها ⇒ العددُ ثابتٌ والمحتوى تبدّل ⇒ أعِد البناءَ"
    return None


# ═══════════════════════ برهانُ السقوط (سطحان · worktree مؤقّت) ═══════════════════════

#: **السطحان** اللذان يُدَّعى سقوطُ الحقن عليهما: سطحُ دليل (`docs/`) وسطحُ صناعة (`tests/`).
PROBE_SURFACES = ("docs/SECURITY_PROBE.md", "tests/SECURITY_PROBE.py")


def _strata(in_scope: list[str]) -> dict[str, str | None]:
    """الأصنافُ **مقيسةٌ من المصدر** لا مُختارة: ستُّ طبقات، منها طبقتا مراجعة ٣٨."""
    rounds = [v for v in in_scope if v.split(".")[-1] in ("00", "0")]
    fracs = [v for v in in_scope if v.split(".")[-1] not in ("00", "0")]
    negs = [v for v in in_scope if v.startswith("-")]
    poss = [v for v in in_scope if not v.startswith("-")]
    #: فاصلةٌ عشريّةٌ عتيقة: القيمةُ نفسُها مكتوبةً بـ`N,dd` — الصيغةُ التي كان المطابِقُ يجهلها
    comma = f"{rounds[0].lstrip('-').split('.')[0]},00" if rounds else None
    #: إشارةٌ مقلوبة: قيمةٌ موجبةٌ في المصدر تُكتب سالبةً (والبصمةُ للمقدار ⇒ يجب أن تسقط)
    flipped = f"-{poss[0]}" if poss else None
    return {
        "مستدير": rounds[0] if rounds else None,
        "كسريّ": fracs[0] if fracs else None,
        "سالب": negs[0] if negs else None,
        "طويل": max(in_scope, key=lambda v: len(v.split(".")[0])) if in_scope else None,
        "فاصلةٌ عشريّة": comma,
        "إشارةٌ مقلوبة": flipped,
    }


def probe(rel: str, deny: set[str]) -> int:
    """يفحص **ملفًّا واحدًا** بمكانه النسبيّ — تستعمله حزمةُ الحقن داخل نسخةٍ مؤقّتة."""
    txt = _text_of_rel(rel)
    if txt is None:
        print(f"⛔ لا ملفَّ للفحص: {rel}", file=sys.stderr)
        return 5
    hits = find_in_text(txt, deny)
    if hits:
        print(f"   سقط ✓ [{len(hits)} ظهوراً] · {rel}")
        return 1
    print(f"   ⛔ نجا (لم يُطابَق) · {rel}", file=sys.stderr)
    return 0


def proof_inject() -> int:
    """**برهانٌ طبقيّ على سطحين، داخل worktree مؤقّت** — فلا يُكتب سمٌّ حقيقيّ في شجرةٍ مشتركة.

    (كان يكتب في `docs/SECURITY_PROBE.md` **غيرِ المُهمَل** داخل الشجرة التي يعمل عليها عدّةُ وكلاء
    ⇒ `git add -A` متزامنٌ أو قتلٌ قبل `finally` يُدرجه. صار الحقنُ في نسخةٍ مؤقّتةٍ تُحذف كاملةً.)
    """
    deny = load_deny()
    if deny is None:
        print("⚠ لا مانيفستَ ⇒ البرهانُ الطبقيُّ غيرُ قابلٍ للتنفيذ هنا (يُعلن ولا يُدَّعى)", file=sys.stderr)
        return 5
    src, _, _, _ = source_amounts()
    in_scope = sorted({a for a in src if is_significant(a)})
    if not in_scope:
        print("⛔ لا مصدرَ محليّ ⇒ تعذّر البرهان (لا أُعلن نجاحاً بلا سمّ)", file=sys.stderr)
        return 5
    strata = _strata(in_scope)
    if any(v is None for v in strata.values()):
        missing = [k for k, v in strata.items() if v is None]
        print(f"⛔ لا سمَّ لصنف: {missing}", file=sys.stderr)
        return 5
    wt = Path(tempfile.mkdtemp(prefix="amount-probe-", dir=str(ROOT.parent)))
    survivors: list[str] = []
    try:
        r = _git("worktree", "add", "--detach", str(wt), "HEAD")
        if r.returncode != 0:
            print(f"⛔ تعذّر إنشاءُ النسخة المؤقّتة: {r.stderr.strip()[:120]}", file=sys.stderr)
            return 5
        (wt / "data" / "eval_pack").mkdir(parents=True, exist_ok=True)
        shutil.copy2(MANIFEST, wt / "data" / "eval_pack" / "amount-manifest.json")
        # المفتاحُ يُكتب من الذاكرة: لا نفترض وجودَ ملفّ (قد يأتي من البيئة في CI)
        (wt / "data" / ".amount-guard-key").write_text(load_key().decode() + "\n", encoding="utf-8")
        # **درسٌ دُفع ثمنُه قبل هذه الجولة:** نسخةٌ مؤقّتةٌ مبنيةٌ من `HEAD` تقيس **ما التُزم** لا
        # ما هو على وشك أن يكون ⇒ تنسخ شجرةُ العمل نفسُها فوقها (وقيس: أوّلُ تشغيلٍ حقن ١٢ سمًّا
        # على نسخةٍ قديمةٍ فـ«نجت» كلُّها، لأنّ `--probe` لم يكن بعدُ في الملفّ المُلتزَم).
        for d in ("tools", "src"):
            if (ROOT / d).exists():
                shutil.copytree(ROOT / d, wt / d, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        env = {**os.environ, "AMOUNT_GUARD_ROOT": str(wt), KEY_ENV: load_key().decode()}
        for surface in PROBE_SURFACES:
            target = wt / surface
            backup = target.read_text(encoding="utf-8") if target.exists() else None
            for name, poison in strata.items():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text((backup or "# مسبار\n") + "\nالرصيد: " + str(poison) + "\n",
                                  encoding="utf-8")
                p = subprocess.run([sys.executable, "tools/amount_guard.py", "--probe", surface],
                                   cwd=str(wt), capture_output=True, text=True, env=env)
                tag = f"{surface} × {name}"
                print(f"   {'سقط ✓' if p.returncode == 1 else 'نجا ⛔'} [{name}] · {surface}")
                if p.returncode != 1:
                    survivors.append(tag)
            if backup is None:
                target.unlink(missing_ok=True)
            else:
                target.write_text(backup, encoding="utf-8")
    finally:
        _git("worktree", "remove", "--force", str(wt))
        shutil.rmtree(wt, ignore_errors=True)
    if survivors:
        print(f"⛔ أصنافٌ نجت: {survivors} ⇒ الحارسُ ليس حارساً", file=sys.stderr)
        return 5
    print(f"سقطت كلُّ الأصناف ✓ ({' · '.join(strata)}) على سطحين: {' · '.join(PROBE_SURFACES)}")
    return 0


# ═══════════════════════ الواجهة ═══════════════════════

def history_forms(deny: set[str] | None = None, repo: Path | None = None) -> tuple[int, int]:
    """**مسحُ كلّ تاريخ المستودع** (`--all --objects`) عن صيغِ مبالغَ حقيقيّة.

    (لماذا: تطهيرُ الملفّات لا يكفي — المفتاحُ وبصماتُه ونسخُ الفيكسترات في *التزاماتٍ سابقة*
    تبقى قابلةً للاسترجاع ما لم تُكشف الشجرةُ كلُّها. والفرقُ عن `--pre-push` أنّ هذا لا يسأل عن
    مدى دفعٍ بل عن التاريخ نفسِه ⇒ هو الفحصُ الصالحُ بعد **إعادة كتابة** لا مدى لها.)

    يُعيد (عددُ الـblobs، عددُ الصيغ) — **أعداداً لا نصوصاً**.
    """
    deny = load_deny() if deny is None else deny
    # **سطحُ المسح يُقاس لا يُفترض (مراجعةُ ٤٣):** كان `--history-audit` يقرأ المستودعَ الحاليّ أبداً
    # وإن مُرِّر `--mirror` ⇒ «PASS» عن سطحٍ لم يُطلَب فحصُه. أُثبت بزرعٍ حقيقيّ: rc=0 والعددُ نفسُه.
    prefix = ["-C", str(repo)] if repo is not None else []
    if repo is not None:
        probe = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-dir"],
                               capture_output=True, text=True)
        if probe.returncode != 0:
            raise UnresolvedRange(f"سطحُ المسح المُعلَن ليس مستودعاً ({_shown(Path(repo))}) ⇒ لا أمرّ")
    # **سطحٌ واحدٌ للقراءة والكتابة:** بلا وجهةٍ يُقرأ المستودعُ الذي أُنفِّذ فيه الأمر (سلوكُ
    # `_git_here` نفسُه)، وبوجهةٍ `-C <المسار>`. (وأوّلُ صياغةٍ لي استعملت `_git(*)` أي `cwd=ROOT`
    # ⇒ أشارت القراءةُ إلى مستودعٍ آخر، فسقط اختبارُ «كلّ التاريخ يُفحَص» — قِيسَ لا تُخُمّ.)
    listing = subprocess.run(["git", *prefix, "rev-list", "--all", "--objects"],
                             capture_output=True, text=True)
    if listing.returncode != 0:
        raise UnresolvedRange("rev-list --all --objects فشل ⇒ لا تاريخَ أُثبته")
    shas = sorted({line.split()[0] for line in listing.stdout.splitlines() if line.split()})
    batch = subprocess.run(["git", *prefix, "cat-file", "--batch"], input="\n".join(shas).encode(),
                           capture_output=True)
    if batch.returncode != 0:
        raise UnresolvedRange(f"cat-file --batch فشل (rc={batch.returncode}) ⇒ مسحٌ لم يقع ⇒ لا أمرّ")
    data, i, seen, nblobs, forms = batch.stdout, 0, 0, 0, set()
    while i < len(data):
        nl = data.find(b"\n", i)
        if nl < 0:
            break
        head = data[i:nl].decode("utf-8", "replace").split()
        if len(head) < 3:
            break
        try:
            size = int(head[2])
        except ValueError:
            break
        body = data[nl + 1:nl + 1 + size]
        if len(body) != size:
            break
        i = nl + 1 + size + 1
        seen += 1
        if head[1] != "blob":
            continue
        nblobs += 1
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if deny:
            for tok, _ in find_in_text(text, deny):
                forms.add(tok)
    # **قيدٌ واحدٌ يُغني عن ثلاثةِ شروطٍ دفاعيّة:** قُرئ كلُّ كائنٍ؟ وإلّا فالمسحُ ناقصٌ (كائنٌ مفقود،
    # تدفّقٌ مقصوص، أو ترويسةٌ غيرُ متوقَّعة) ⇒ يُسقط. و«الصفرُ علامةُ قياسٍ ميّت»: صفرُ blobٍ ليس نظافة.
    if seen != len(shas):
        raise UnresolvedRange(f"قُرئ {seen} كائناً من {len(shas)} ⇒ مسحٌ ناقصٌ أو كائنٌ مفقود ⇒ لا أمرّ")
    if nblobs == 0 and len(shas):
        raise UnresolvedRange("صفرُ blobٍ مقروء ⇒ قياسٌ ميّتٌ لا نظافةٌ ⇒ لا أمرّ")
    return nblobs, len(forms)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="حارسُ المبالغ: لا مبلغَ حقيقيّ في مستودعٍ عامّ")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--pre-push", action="store_true",
                    help="فحصُ المدفوع نفسِه: المراجعُ من stdin ⇒ rev-list <local> --not --remotes")
    ap.add_argument("--ratchet", action="store_true", help="السقاطةُ على الشجرة (ملفّاً ملفّاً)")
    ap.add_argument("--baseline-write", action="store_true", help="كتابةُ خطّ الأساس (أعدادٌ فقط)")
    ap.add_argument("--tracking-audit", action="store_true", help="فحصُ الإهمال واقعاً (بلا سرّ)")
    ap.add_argument("--accept-increase", metavar="REASON", default="",
                    help="رفعُ خطّ الأساس عمداً (يُعلَن؛ والخطّاف يُسقط دفعه)")
    ap.add_argument("--baseline-audit", metavar="BASE_REF", default="",
                    help="سطحٌ عامّ بلا أدلّة: خطُّ الأساس المدفوع لا يتجاوز الأساس (بلا مفتاح)")
    ap.add_argument("--history-audit", action="store_true",
                    help="مسحُ **كلّ تاريخ المستودع** عن صيغِ مبالغَ حقيقيّة (لا يسأل عن مدى)")
    ap.add_argument("--history-rewrite", metavar="OLD_SHA", default="",
                    help="إعادةُ كتابةٍ مُعلَنة: تُثبت الأصلَ في النسخة الاحتياطيّة ثم تمسح التاريخ كلَّه")
    ap.add_argument("--mirror", metavar="PATH", default="",
                    help="نسخةٌ مرآتيّةٌ احتياطيّةٌ يُثبَت منها أصلُ إعادة الكتابة")
    ap.add_argument("--probe", metavar="REL", default="", help="فحصُ ملفٍّ واحد بمكانه النسبيّ")
    ap.add_argument("--ci", action="store_true", help="سطحٌ عامٌّ بلا أدلّة **بالبناء** (يُعلن ولا يُخفي)")
    ap.add_argument("--extra", default="")
    ap.add_argument("--inject", action="store_true", help="برهانُ السقوط (سمٌّ من المصدر · سطحان)")
    ap.add_argument("--json", action="store_true", help="المخرَجُ الآليُّ الكامل (لا يُقصّ)")
    ap.add_argument("--remote", default=None,
                    help="اسمُ وجهة الدفع كما يمرّرها الخطّاف من `$1` — المدى يُقاس مقابلها لا "
                         "مقابل كلّ الريموتات؛ وغيابُها يُعلَن تقريباً لا يُخفى.")
    args = ap.parse_args(argv)

    if args.tracking_audit:
        bad = tracking_audit()
        if bad:
            print("⛔ BLOCK — حارسُ الإهمال:")
            for b in bad:
                print("   " + b)
            return 1
        print(tracking_audit_message())
        return 0
    if args.build:
        return build([x for x in args.extra.split(",") if x.strip()])
    if args.inject:
        return proof_inject()
    if args.baseline_audit:
        # **قبل كلّ ما يعتمد على الأدلّة** (مراجعة ٤٠، البند ١): كانت الكتلةُ **بعد** فرعِ
        # «السطح العامّ»، وذلك الفرعُ **يُرجِع** في CI (لا مانيفستَ بالتصميم) ⇒ تُطبَع
        # «PASS (بما أُمكن فحصُه)» بلا أن تُقرأ عتبةٌ أصلاً. وهي لا تحتاج مفتاحاً: **ملفّان
        # مُتتبَّعان يُقارَنان** ⇒ لا عُذرَ لوقوعها خلف بوابةٍ تعتمد على سرّ.
        return baseline_audit(args.baseline_audit)

    deny = load_deny()
    if deny is None and not args.ci:
        # **الفشلُ المُغلَق:** غيابُ المانيفست لا يمرّ صامتاً — إلّا بعلَمٍ صريح يعلن السطحَ العامّ.
        print("⛔ " + _manifest_blind().lstrip("⚠ "))
        print("   (وبلا `--ci`: الحارسُ **يسقط مُغلَقاً** — لا يمرّ صامتاً. في CI: `--ci`.)")
        return 2
    if deny is None:
        # السطحُ العامُّ **بالبناء**: يُعلن ما فُحص وما لم يُفحَص (لا يُدَّعى إنفاذٌ غيرُ ممكن).
        print(_manifest_blind())
        bad = tracking_audit()
        for b in bad:
            print("   " + b)
        print("   " + tracking_audit_message())
        return 1 if bad else 0

    if args.probe:
        return probe(args.probe, deny)
    if args.baseline_write:
        return write_baseline(deny, accept_increase=bool(args.accept_increase))
    if args.history_audit or args.history_rewrite:
        if args.history_rewrite:
            if not args.mirror:
                print("⛔ BLOCK — إعادةُ كتابةٍ مُعلَنةٌ بلا نسخةٍ احتياطيّةٍ أُثبت منها الأصل ⇒ لا أمرّ")
                return 2
            proof = _git("-C", args.mirror, "cat-file", "-e", f"{args.history_rewrite}^{{commit}}")
            if proof.returncode != 0:
                print(f"⛔ BLOCK — الأصلُ المُعلَن {args.history_rewrite[:12]} غيرُ موجودٍ في النسخة "
                      f"الاحتياطيّة ⇒ إعادةُ كتابةٍ لا تُثبت أصلَها")
                return 2
            print(f"✓ أصلُ إعادة الكتابة مُثبَتٌ في النسخة الاحتياطيّة: {args.history_rewrite[:12]}")
        if deny is None:
            if args.ci:
                print("⚠ سطحٌ عامٌّ بلا أدلّة: مسحُ التاريخ لا يُقاس بلا مفتاح ⇒ **يُعلن ولا يُخفى**")
                return 0
            print("⛔ BLOCK — لا أدلّةَ (مفتاح/مانيفست) ⇒ لا أستطيع مسحَ التاريخ ⇒ لا أُثبت شيئاً")
            return 2
        scan_repo = Path(args.mirror) if args.mirror else None
        print(f"· سطحُ المسح: {_shown(scan_repo) if scan_repo else 'المستودع الحالي'}")
        nblobs, forms = history_forms(deny, repo=scan_repo)
        if forms:
            print(f"⛔ BLOCK — التاريخُ يحمل {forms} صيغةً لمبالغَ حقيقيّة داخل {nblobs} blobاً "
                  f"(النصوصُ لا تُطبع؛ استعمل `--json` للأعداد فقط)")
            return 5
        print(f"PASS — مسحُ كلّ التاريخ: {nblobs} blobاً · ولا صيغةَ مبلغٍ حقيقيّ واحدة")
        return 0
    # **الفحصانِ فوق كلّ تفريع (مراجعة ٤٤):** كانا بعد `return` فرعَي `--pre-push` و`--ratchet`
    # ⇒ الخطّافُ لا يبلغهما أبداً، ومانيفستٌ متعفّن يمرّ من بوابة الدفع بلا سقوط.
    if pre_push_checks():
        return 1
    if args.pre_push:
        refs = sys.stdin.read()
        if not refs.strip():
            # **فارغٌ شرعاً:** git يُنفّذ `pre-push` و`stdin` فارغٌ حين لا مرجعَ يُحدَّث (دفعٌ
            # لفرعٍ متزامن — مقيسٌ: bytes=0). فلا شيءَ يُنشر ⇒ لا شيءَ أُثبته، **ويُعلَن**.
            # (كان يسقط `rc=2` ⇒ حافزُ `--no-verify` لعملٍ روتينيّ — وهو الصنفُ الذي حذّرت منه
            # المراجعةُ في البند ٣. المقعدُ يمنع سقوطاً كاذباً، والمقعدُ الآخر يمنع مروراً كاذباً
            # ⇒ والفصلُ بين الحالتين هو الجواب: **الفرقُ بين «لا شيءَ» و«لم أقرأ»**.)
            print("PASS — لا مراجعَ على stdin ⇒ دفعٌ لا يُحدّث مرجعاً ⇒ لا شيءَ يُنشر (يُعلن)")
            return 0
        _pairs, _bad = parse_refs(refs)
        if _bad or not _pairs:
            print(f"⛔ BLOCK — stdin غيرُ فارغٍ ولم أُقرأ منه مرجعاً ({_bad} سطراً خارج شكل"
                  f" `pre-push` رباعيّ الحقول) ⇒ «لم أقرأ» ليست «لا شيءَ يُنشر»"
                  f" (القاعدة ١٩: المجرى المقصوص يُسقَط مُغلَقاً)")
            print("   ⇒ الخطّافُ يمرّر أربعةَ حقولٍ في السطر (مقيسٌ في دفعٍ حقيقيّ):"
                  " أعد الدفع، أو `--ratchet` للفحص بلا دفع.")
            return 2
        try:
            revs = pushed_revs(refs, args.remote)
        except UnresolvedRange as e:
            declared = os.environ.get("AMOUNT_GUARD_HISTORY_REWRITE", "").strip()
            if declared:
                print("⚠ إعادةُ كتابةِ التاريخ **مُعلَنة**: لا مدى لها ⇒ يُفحَص التاريخُ كلُّه بدلاً منه"
                      " (بإعلانٍ لا بصمت)")
                return main(["--history-rewrite", declared,
                             "--mirror", os.environ.get("AMOUNT_GUARD_MIRROR", "")])
            salvaged = _range_from_heads(_local_heads(refs), args.remote)  # المراجعُ نفسُها، لا `HEAD`
            if salvaged:
                print(f"⚠ المراجعُ غيرُ محلولة ({e}) ⇒ اشتُقّ المدى من المراجع المدفوعة نفسِها "
                      f"({len(salvaged)} التزاماً لم تعرفها وجهةُ الدفع) — يُعلن ولا يُخفى")
                revs = salvaged
            else:
                print(f"⛔ BLOCK — لم أُثبت نظافةَ المدى ⇒ لا أمرّ (ثغرةُ ٣٩ رقم ٢): {e}")
                print("   ⇒ `git fetch <وجهة الدفع>` (وإن كانت رابطاً: أضِفها ريموتاً باسمٍ "
                      "`git remote add <اسم> <رابط>` ثم `git fetch <اسم>`) وأعِد الدفع:"
                      " مدىً غيرُ محلولٍ ليس مدىً نظيفاً.")
                return 2
        if not revs:
            # **الفارغُ شرعاً ≠ غيرُ المقروء** (مراجعة ٤٠/٣): مدىً **حُلّ** فارغاً قياسٌ يقول
            # «لا التزامَ جديداً يُنشر» — فرعٌ جديدٌ عند التزامٍ منشورٍ أصلاً، أو **حذفُ فرع** —
            # فيُمرّ بإعلانٍ لا بسقوط؛ والسقوطُ يبقى لحالةٍ واحدة: **فشلُ حلّ المدى** (أعلاه).
            print("PASS — المدى فارغٌ **بالقياس مقابل وجهة الدفع**: لا التزامَ جديداً يُنشر "
                  "(فرعٌ تعرف الوجهةُ أساسَه، أو حذفُ فرع) ⇒ لا شيءَ يُنشر فلا شيءَ أُثبته")
            return 0
        counts = pushed_counts(deny, revs)
        base = baseline_at("origin/main")
        if base is None:
            # **البابُ ٣أ/٣ب (أمسكه مقعدان):** كان يسقط إلى خطّ الشجرة العاملة ⇒ الدافعُ يضع عتبتَه.
            print("⛔ BLOCK — عتبةُ origin/main غيرُ مقروءة ⇒ لا أستبدلها بخطّ الشجرة العاملة "
                  "(العتبةُ ممن نُشر لا ممّا في يد الدافع) ⇒ `git fetch origin` ثم أعِد الدفع")
            return 2
        bad = ratchet_violations(counts, base, f"دفعُ {len(revs)} التزاماً مقابل origin/main")
        for head in _local_heads(refs):
            pushed_base = baseline_at(head)
            bad += ratchet_violations(pushed_base, base, f"خطُّ الأساس المنشورُ في {head[:8]}")
        if bad:
            head, shown, remedy = block_claim(bad)
            print(head)
            for b in shown[:25]:
                print("   " + b)
            if remedy:
                print("   ⇒ صحّح القيمةَ أو خفّض خطَّ الأساس بعد إعادة الكتابة (القاعدة ١٢: لا يُعفى موضع)")
            return 1
        print(f"PASS — مدى الدفع ({len(revs)} التزاماً) لا يزيد ظهوراً واحداً على خطّ الأساس، "
              f"ولا بصمةَ مجموعةٍ تبدّلت")
        return 0
    if args.ratchet:
        counts = counts_with_commitment(deny)
        bad = ratchet_violations(counts, read_baseline(), "الشجرةُ العاملة")
        if bad:
            head, shown, _ = block_claim(bad, subject="الشجرةُ تحمل")
            print(head)
            for b in shown[:25]:
                print("   " + b)
            return 1
        print(f"PASS — لا ملفَّ تجاوز خطَّ الأساس ({sum(v['count'] for v in counts.values())} ظهوراً مُعلَنٌ في "
              f"{len(counts)} ملفّاً كما هو)")
        return 0

    hits = counts_with_commitment(deny)
    if args.json:
        # **القاعدة ١٥:** المخرَجُ الآليُّ لا يُقصّ أبداً. **والقيمةُ لا تُطبع**: الوحدةُ ملفٌّ+عددها.
        print(json.dumps({"pass": not hits, "count": len(hits),
                          "total": sum(v["count"] for v in hits.values()),
                          "files": {k: v["count"] for k, v in sorted(hits.items())}},
                         ensure_ascii=False, indent=1))
        return 1 if hits else 0
    if hits:
        bad = ratchet_violations(hits, read_baseline(), "الشجرةُ العاملة")
        print("⛔ BLOCK — مبالغُ حقيقيّةٌ في ملفّاتٍ مُتتبَّعة (تُعرض الأعدادُ لا القيم):")
        for rel, v in sorted(hits.items(), key=lambda x: -x[1]["count"])[:25]:
            print(f"   {rel}  ←  {v['count']} ظهوراً")
        print(f"المجموع: {sum(v['count'] for v in hits.values())}")
        if bad:
            print("   ⇒ وفيها ما تجاوز خطَّ الأساس ⇒ امنع الدفع حتى التصحيح")
        return 1
    print("PASS — لا مبلغَ حقيقيٌّ في أيّ ملفٍّ مُتتبَّعٍ أو غيرِ مُهمَل (بلا إعفاءٍ بالمسار)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
