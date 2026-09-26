#!/usr/bin/env python3
"""Publish guard — the last line of defense before anything goes PUBLIC.

What-if workshop #8/#9 (the catastrophic tier): one careless push puts real
family data, account numbers, or personal paths into a public repository —
an effect that cannot be undone. This scanner runs on every push (git hook),
on CI, and manually:

    python3 tools/publish_guard.py --tree        # what is tracked now
    python3 tools/publish_guard.py --history     # everything ever committed
    python3 tools/publish_guard.py --pre-push    # refs fed by the git hook
    python3 tools/publish_guard.py --tree --history --ci
    python3 tools/publish_guard.py --tracked-real-data   # فشلٌ إن كان ملفُّ بياناتٍ حقيقيّةٍ مُتتبَّعًا
                                                   # (قائمٌ بذاته: لا يُجمع مع الأنماط الأخرى)

Severity model (practical by design — a guard that cries wolf gets disabled):
- BLOCK: personal home paths · the original statement filename · real family
  names appearing in the document · ≥10-digit runs (account/card numbers) —
  **including runs a plain scan cannot see**: runs broken by a grouping
  separator (uniform groups of 3 or 4 wide, joined by space/dot/hyphen/
  underscore) and runs rebuilt by adding two string literals together ·
  real-data paths (the three dirs of REAL_DATA_DIRS — `data/local_sample` · `data/training` ·
  `data/eval_pack` — **at any depth**, including a nested `data/data/…` copy, and matched from git's
  path output **unquoted** so a non-ASCII name cannot hide) · .env files · media binaries that
  are not explicitly allowed · unscannable binaries (archives/databases/
  fonts) with no allowlist line of their own · any tracked blob that cannot
  be decoded as text. Any BLOCK fails the run (exit 1).
- WARN: the owner's name/handle tokens in prose, docs and commit messages
  (usually attribution — review, don't panic). WARN does NOT fail the run by
  default; `--strict-warn` makes it fail, and the output always prints an
  explicit advisory block so a WARN can never pass unnoticed.

WHAT THIS GUARD CANNOT SEE (documented, not hidden): the bytes inside media
binaries and allowlisted archives are skipped, never read. An allowlist line
is therefore a *claim by a human*, not a scan — which is exactly why every
line in `.publish-allowlist` carries a written reason. Nor does it see the
outside world (a value already indexed elsewhere), and its self-exclusion is
a HOLE, not a feature: this file is never scanned by itself, so its text is
policed by `test_guard_source_passes_its_own_rules` in the suite instead —
the rule exists because a real account number once sat in this very docstring
as two added literals, invisible to the guard that excluded itself.

ALLOWLIST: `.publish-allowlist` — one entry per line:
    <rule_id> :: <path-glob> :: <why>
Self-exclusion: this script, the allowlist, and the hooks dir are never
scanned (their pattern sources would otherwise self-trip).

Stdlib only — it must run in CI and inside git hooks with bare python3.
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_AR = "0-9\u0660-\u0669\u06f0-\u06f9"  # western + arabic-indic + persian

LONG_DIGITS_RX = re.compile("[" + _AR + "]{10,}")
#: معرّفُ كائنٍ في مخزن git — `sha1` (٤٠) أو `sha256` (٦٤). يُستعمل لقراءة صيغة `-z` **بشكلها**:
#: كلُّ سجلٍّ إمّا معرّفٌ وإمّا `path=<مسار>` يتبعه؛ فسجلٌّ ثالثٌ = الصيغةُ تغيّرت ⇒ لا حكم (جولة ٦٨ب).
OBJECT_ID_RX = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
LONG_DIGITS_DESC = "سلسلة ارقام طويلة (رقم حساب/بطاقة؟)"

# A long run can be written in uniform groups — the IBAN/card/cheque idiom
# (four-wide groups for IBANs and cards, three-wide for some cheque formats).
# The signature used here is groups of EQUAL width, 3 or 4 digits, joined by
# one separator:
#   · equal width  → two unrelated amounts on one line are never welded;
#   · width 3 or 4 → "١٤٣٩٠٧٢٢ ٢٠١٨٠٤٠٨" (two 8-digit dates) and
#                    "20260917-172327" (a timestamp) stay two numbers.
# Both of those were FALSE POSITIVES produced by the first draft of this
# rule — found by running it against the repository itself, which is why the
# width test exists at all.
# Commas are deliberately not grouping separators: "1000,2000,3000,4000" is a
# CSV row of four amounts, not one number. Stated consequence (honest limit):
# "1,234,567,890" — non-uniform groups — is NOT caught by this rule.
_GROUP_SEP = " \t._-"
_GROUPED_RUN = re.compile("[" + _AR + "]{3,}(?:[" + _GROUP_SEP + "]"
                          "[" + _AR + "]{3,})+")
# The two-literal trick: 'aaaa' + 'bbbb' → one run the plain rule never sees.
_STRING_CONCAT = re.compile("""["']\\s*\\+\\s*["']""")

TEXT_RULES = [
    ("home_path", "BLOCK", re.compile(r"/Users/[A-Za-z0-9_.-]+"),
     "مسار منزل مطلق (اسم مستخدم حقيقي)"),
    ("orig_filename", "BLOCK", re.compile(r"[Rr]ajehi\s+[Oo]riginal"),
     "اسم ملف الكشف الاصلي"),
    ("name_full", "BLOCK", re.compile(r"عبده\s*جحفلي"),
     "اسم عائلي من الكشف الحقيقي"),
    ("long_digits", "BLOCK", LONG_DIGITS_RX, LONG_DIGITS_DESC),
    ("name_token", "WARN",
     re.compile(r"عبد\s*الرحمن|جحفلي|jahfali|abdurrahman", re.IGNORECASE),
     "اسم/معرف المالك — راجعه"),
]
# rule id recorded when the run only appears AFTER joining string literals
CONCAT_RULE = ("concat_digits", "BLOCK",
               "رقم مبني بتجميع شطرين نصيّين (يتخطى فحص السلاسل)")

BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".tif",
               ".tiff", ".bmp", ".pdf", ".ttf", ".otf", ".woff", ".woff2",
               ".mp4", ".mov", ".zip", ".gz", ".tar", ".ico", ".icns",
               ".pyc", ".so", ".dylib", ".sqlite", ".db"}
MEDIA_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".tif",
              ".tiff", ".bmp", ".pdf", ".mp4", ".mov"}
# Binaries the guard cannot read as text: archives, exports, databases, fonts.
# They are not "safe" — they are *opaque*. Each one needs an allowlist line.
OPAQUE_EXTS = {".zip", ".xlsx", ".xlsm", ".xls", ".docx", ".doc", ".pptx",
               ".ppt", ".sqlite", ".db", ".tar", ".gz", ".tgz", ".7z", ".rar",
               ".pickle", ".pkl", ".bin", ".ttf", ".otf", ".woff", ".woff2"}

# **ثلاثةُ مستودعاتٍ للبيانات الحقيقيّة، لا واحد** (مراجعة ٣٨): `.gitignore` يعلن
# `data/local_sample/` و`data/training/` و`data/eval_pack/` بياناتٍ حقيقيّة — وكان هذا الحارس
# يمنع الأوّلَ وحدَه ⇒ `git add -f` يمرّ على الاثنين الآخرين، وفيهما خريطةُ التطهير التي تربط
# كلَّ قيمةٍ مُقنَّعةٍ بأصلها الحقيقيّ.
REAL_DATA_DIRS = ("data/local_sample", "data/training", "data/eval_pack")


def real_data_path(p: str) -> bool:
    """هل المسارُ ملفُّ بياناتٍ حقيقيّةٍ **في أيّ عمق** — لا في الجذر وحدَه؟ (مراجعة ٦٧)

    كان القيدُ على بادئة المسار (`p.startswith("data/local_sample/")`) ⇒ نسخةٌ متداخلةٌ
    (`data/data/local_sample/…`) تمرّ من هذا الحارس **ومن خطوة الـCI معًا**. **والتداخلُ يقع طبيعيًّا:**
    `cp -R data <نسخةٍ فيها data/>` تُنتج `data/data/`، فتخرج **٣٦١٠ ملفًا حقيقيّةً (منها المفتاح)**
    من `.gitignore` الجذريّ وتصير قابلةً للإيداع بأمر `git add .` واحد.
    فالمقابلةُ على **مقاطع المسار** لا على بادئته — والتداخلُ لا يُعفي.
    """
    parts = Path(p).parts
    for d in REAL_DATA_DIRS:
        want = tuple(d.split("/"))
        n = len(want)
        if any(parts[i:i + n] == want for i in range(len(parts) - n + 1)):
            return True
    return False


PATH_RULES = [
    ("local_data", "BLOCK", real_data_path,
     "ملف بيانات حقيقية (لقطات/تدريب/تقييم/خريطة تطهير) — ممنوع رفعه نهائياً، ولو متداخلاً"),
    ("env_file", "BLOCK", lambda p: Path(p).name == ".env", "ملف اسرار"),
    ("media_file", "BLOCK",
     lambda p: Path(p).suffix.lower() in MEDIA_EXTS
     and not fnmatch.fnmatch(p, "data/sample/*.pdf"),
     "وسائط/مستند ثنائي غير مسموح — راجع قائمة المسموح"),
    ("opaque_binary", "BLOCK",
     lambda p: Path(p).suffix.lower() in OPAQUE_EXTS,
     "ثنائي لا يمكن فحصه كنص (ارشيف/قاعدة/خط) — لا يُدفع بلا سطر استثناء مبرَّر"),
    ("undecodable", "BLOCK",
     lambda p: False,  # decided in _scan_blobs, where the bytes are known
     "ملف لا يُفك كنص ولم يُدرج في قوائم الوسائط — لا يُدفع بصمت"),
]

SKIP_PATHS = {"tools/publish_guard.py", ".publish-allowlist"}


def _run_git(args: tuple[str, ...], z: bool = False, data: bytes | None = None) -> bytes:
    """قراءةٌ واحدةٌ من git — **ورفضُ ما لم يُقرأ** (مراجعة ٦٨ + مقعدا المعايير والبنية · جولة ٦٨).

    **العلّةُ المقيسة:** كانت `_git` تُعيد `''` على أمرٍ فاشل، و`_git_z` تُعيد قائمةً فارغة ⇒ فيُقرأ
    «تعذّرُ قراءة» «صفرَ مطابقات» ثم «نظيفًا». وقِيس على الأمر الفاشل نفسِه: `_git` ⇒ `''` بلا استثناء،
    `_git_z` ⇒ `GitReadError` — أي أنّ السياسةَ نُفِّذت في قارئٍ واحدٍ فبقيت أنصافُ المسح الثلاثة
    (الرسائل · `pre-push` · الملفّاتُ المُتتبَّعة) عائدةً «نظيفةً صامتة». فالآن **سياسةٌ واحدة**
    لكلّ مسارِ قراءة: رمزُ خروجٍ غيرُ صفريّ ⇒ `GitReadError` ⇒ لا حكم. **والنواةُ تُعيد بايتات**
    (لا نصًّا) لأنّ قراءةَ `cat-file --batch` ثنائيّةٌ أصلًا؛ فالترميزُ في `_git` وحدَها.
    """
    proc = subprocess.run(["git", *args, *(["-z"] if z else [])], cwd=ROOT,
                          input=data, capture_output=True)
    if proc.returncode != 0:
        raise GitReadError(
            f"`git {' '.join(args)}{' -z' if z else ''}` ⇒ rc={proc.returncode}: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()[:160]}")
    return proc.stdout


def _git(*args: str) -> str:
    return _run_git(args).decode("utf-8", "replace")


class GitReadError(RuntimeError):
    """قراءةٌ من git لم تكتمل أو أعطت ما لا يُعقل ⇒ **لا حكم** (فشلٌ مُغلَق) بدل «صفرُ مطابقات».

    **مصدرُها (مراجعة ٦٨ · R68-1):** «عددُ المطابقات = صفر» كانت تُقرأ «نظيفًا»، وهي في الحقيقة
    قد تعني «لم أقرأ شيئًا». والقاعدة: **رقمٌ لا يُقاس لا يُصادَق عليه**.
    """


def _git_z(*args: str) -> list[str]:
    """مخرَجُ git **بفواصل NUL وبلا تقويس** — لمقابلة المسارات (جولة ٦٧ · مقعدُ المواصفة).

    **العلّةُ المقيسة:** `core.quotePath` يقوّس كلَّ مسارٍ فيه محرفٌ غيرُ ASCII فيُخرجه
    `"data/training/\\331\\203\\330\\264…"` ⇒ فمقابلةُ مقاطع المسار تفشل و**يُفلت الملفُّ**:
    قِيس في نسخةٍ حقيقيّة أنّ مسارًا عربيًّا واحدًا تحت `data/training/` أعطى
    «0 تحت مجلّدات البيانات الحقيقيّة» و`rc=0` — أي أنّ **الخطوةَ التي أُضيفت لسدّ R67-1 كانت هي
    التي تمرّ منه**. و`git -c core.quotePath=false ls-files` أعطى `flagged=1` — فالعلاجُ قراءةٌ واحدة.
    و`-z` أصحُّ من `-c`: لا يقوّس **ولا** يستعمل فاصلًا يمكن أن يظهر في اسم ملفّ (سطرٌ جديد).

    **وفشلٌ مُغلَق (مراجعة ٦٨):** كانت تُعيد المخرَجَ بلا فحصِ رمزِ الخروج ⇒ فأمرٌ فاشلٌ يُقرأ
    «قائمةً فارغةً» = «نظيفًا». والآن تمرّ على `_run_git` (سياسةٌ واحدة مع `_git`) ويرفع الاستثناءَ.
    """
    return [x for x in _run_git(args, z=True).decode("utf-8", "replace").split("\0") if x]


def _history_pairs() -> list[tuple[str, str]]:
    """أزواجُ (المسار، المعرّف) لكلّ كائنٍ في التاريخ — بصيغة `-z` **كما هي مقيسة**.

    **مراجعة ٦٨ · R68-1 — العلّةُ المقيسة:** `rev-list --objects --all -z` **لا يُخرج الأسطرَ
    نفسَها بفاصلٍ آخر**؛ بُنيَتُه تتغيّر إلى **سجلّاتٍ منفصلة**:
    `<sha>\\0<sha>\\0<sha>\\0path=<المسار>\\0` (والمسارُ في سجلٍّ **مسبوقٍ بـ`path=`** بلا فراغٍ يفصل).
    وكان القارئُ يفصل كلَّ سجلٍّ على أوّل فراغ ⇒ لم يُطابق شيئًا ⇒ **آلافُ الكائنات تُتخطّى بصمت**
    (قِيس ٣٢٨١ في شجرة هذه الجولة، و٣٢٢٦ في مهمّة الـCI — والعددُ يتحرّك مع الشجرة، فالرقمُ بلا بيئته
    لا يُعتمد)، ويُخرج الحارسُ «نظيف» وهو لم يقرأ شيئًا (قِيس: `tree: 462 · history: 0 · 0 BLOCK · rc=0`).
    أمّا `ls-tree -r -z` فبُنيَتُه لم تتغيّر (‎`\\t` باقٍ) ⇒ الشجرةُ كانت سليمة، وهو سببُ غياب الأثر.

    **ومقياسُ «قُرئ أم لا» على **شكلِ** ما قرأته git — لا على الصفر (مقعدا البنية والمواصفة · ٦٨ب):**
    صفرُ السجلّاتِ ليس فشلًا بذاته (مستودعٌ بلا التزاماتٍ ⇒ لا تاريخَ يُمسح)، وصفرُ الأزواجِ ليس
    فشلًا بذاته أيضًا (تاريخٌ بلا كائنٍ مسمّى: التزامٌ فارغ — قِيس `history: 0 · rc=0`) ⇒ فالحكمُ على
    **شكلِ كلّ سجلّ**: إمّا معرّفُ كائنٍ (`sha1`/`sha256`) وإمّا `path=<مسار>` يتبع معرّفًا. وسجلٌّ لا
    هذا ولا ذاك ⇒ الصيغةُ تغيّرت أو القارئُ خالفها ⇒ لا حكم. (وهو بعينِه ما فات في R68-1: الأزواجُ
    صفرٌ والسجلّاتُ مقروءة ⇒ مُرَّ الأمرُ «نظيفًا».)

    **وحدُّ هذا الحكم مُعلَن (مقعدُ البنية F-4 · ٦٨ج):** يبقى مفتوحًا شكلٌ واحد — **بثُّ معرّفاتٍ
    خالصةً بلا سجلّ `path=` إطلاقًا**: كلُّ سجلٍّ يجتاز فحصَ الشكل ⇒ `history: 0 · 0 BLOCK · rc=0`
    («تاريخٌ بلا كائنٍ مسمّى»). قِيس بمُزيِّفٍ يُسقط سجلّات `path=` جملةً (قبل الإصلاح وبعده سواء)،
    وهو **ليس انحدارًا** (كان يمرّ قبل الإصلاح أيضًا) لكنّه **ليس مُغلقًا** ⇒ ولا يُدَّعى إغلاقُه.
    والتضييقُ الممكن (فحصُ وجود بلوباتٍ فعلًا في المخزن عند صفرِ الأزواج) لم يُنفَّذ: ثمنُه عمليةُ
    git إضافيّة على كلّ مسحٍ مقابلِ احتمالٍ **مجهولِ الوقوع** في git مستقبليّ.
    """
    records = _git_z("rev-list", "--objects", "--all")
    pairs: list[tuple[str, str]] = []
    sha = ""
    for rec in records:
        if OBJECT_ID_RX.fullmatch(rec):
            sha = rec
        elif rec.startswith("path="):
            if not sha:
                raise GitReadError(
                    f"مسحُ التاريخ قرأ `path=` بلا معرّفٍ يسبقه ({rec[:60]!r}) ⇒ بنيةُ `-z` تغيّرت")
            pairs.append((rec[5:], sha))
        else:
            raise GitReadError(
                f"مسحُ التاريخ قرأ سجلًّا لا معرّفَ كائنٍ ولا `path=`: {rec[:60]!r} ⇒ صيغةُ `-z` "
                f"تغيّرت (فشلٌ مُغلَق: لا حكمَ على ما لم يُقرأ)")
    return pairs


def _read_blobs(shas: list[str]) -> dict[str, bytes]:
    """Batch-read blobs in ONE git process (fast even for history mode).

    **وعلى النواة نفسِها (مقعدا المعايير والبنية · الجولة ٦٨ب):** كانت هذه القراءةُ الرابعة — وهي
    التي تُنزل محتوى الكائنات، أي **موضعُ الحكم نفسه** — تنادي git مباشرةً بلا فحصِ رمز خروج ⇒ فشلٌ
    متكرّرٌ يُقرأ «صفرَ نصوص» = «نظيفًا»، وهو عينُ الصنف الذي أُغلق في المسارات الثلاثة الأخرى.

    **والكائنُ الغائبُ يُعلَن ولا يُتخطّى (قياسُ المقاعد الثلاثة · ٦٨ب):** `cat-file --batch` يُخرج
    `… missing` **برمز خروجٍ صفر** ⇒ فحصُ الرمز وحدَه لا يكفي، والمستهلكُ كان يُسقط الغائبَ بصمت
    (`data is None ⇒ continue`) ⇒ **تسريبٌ مزروعٌ يمرّ**. قِيس بحذف جسم بلوبٍ واحد: قَبلٌ `1 BLOCK`
    و`rc=1`، وبعدُ `0 BLOCK` و«آمن للدفع» `rc=0`. فالآن: صفرُ بايتٍ أو سجلٌّ غيرُ مفهوم ⇒ `GitReadError`.

    **والمعلَنُ يُقابَل بالمقروء (مقعدُ البنية · ٦٨ج):** الترويسةُ تعلن حجمَ الكائن، فبثٌّ مقطوعٌ كان
    يُعاد قصيرًا بصمت (`nl < 0 ⇒ break` والشرائحُ بلا فحص طول) ⇒ يُفحَص الآن أنّ المقطعَ بعددِ البايتات
    المعلَن بالضبط، وإلّا `GitReadError`. **والكائنُ الفارغُ ليس عطبًا** (الترويسةُ تُعلن `size = 0`
    فيُقرأ صفرُ بايتٍ مقصودًا)، والفرقُ بينهما: `if not out` يفحص **المخرَجَ كلَّه** لا الكائن.
    """
    if not shas:
        return {}
    out = _run_git(("cat-file", "--batch"), data="\n".join(shas).encode())
    if not out:
        raise GitReadError(
            f"`git cat-file --batch` قرأ صفرَ بايت لـ{len(shas)} كائنًا ⇒ الأمرُ لم يُنفَّذ (فشلٌ مُغلَق)")
    result: dict[str, bytes] = {}
    i = 0
    while i < len(out):
        nl = out.find(b"\n", i)
        if nl < 0:
            raise GitReadError(
                f"بثُّ `cat-file --batch` انتهى بترويسةٍ لم تُغلق ({len(out) - i} بايتًا متبقّية) "
                f"⇒ مخرَجٌ مقطوع (فشلٌ مُغلَق: لا حكمَ على ما لم يُقرأ)")
        header = out[i:nl].decode("utf-8", "replace").split()
        if len(header) == 3 and header[1] in ("blob", "tree", "commit", "tag"):
            size = int(header[2])
            end = nl + 1 + size
            if end > len(out):
                raise GitReadError(
                    f"بثُّ `cat-file --batch` مقطوع: الترويسةُ تعلن {size} بايتًا والمقروءُ "
                    f"{len(out) - nl - 1} ⇒ لا حكمَ على كائنٍ ناقص (فشلٌ مُغلَق)")
            if header[1] == "blob":
                result[header[0]] = out[nl + 1: end]
            i = end + 1
        elif len(header) == 2 and header[1] == "missing":
            raise GitReadError(
                f"كائنٌ غائبٌ من مخزن git ({header[0][:12]}) ⇒ لا حكمَ على ما لم يُقرأ (فشلٌ مُغلَق)")
        else:
            raise GitReadError(
                f"سجلُّ `cat-file --batch` غيرُ مفهوم: {header[:3]} ⇒ صيغةُ المخرَج تغيّرت (فشلٌ مُغلَق)")
    return result


def load_allowlist() -> list[tuple[str, str]]:
    p = ROOT / ".publish-allowlist"
    if not p.exists():
        return []
    entries = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split("::")]
        if len(parts) >= 2:
            entries.append((parts[0], parts[1]))
    return entries


_SCOPES = {"tree", "history", "push", "message", "worktree"}


def _allowed(entries, rule_id: str, path: str, where: str = "") -> bool:
    """Is this rule waived for this path — and, when scoped, in this pass?

    A glob may carry a scope prefix (`history:tests/x.py`). An exemption that
    only exists because OLD commits carry the value must not also blind the
    working tree: the tree is what a future edit lands in, and that is exactly
    where the account number slipped through the first time (audit S1).
    An unprefixed glob keeps the old meaning — every pass.
    """
    for rid, glob in entries:
        if rid != rule_id:
            continue
        scope, _, rest = glob.partition(":")
        if rest and scope in _SCOPES:
            if where and where != scope:
                continue
            glob = rest
        if fnmatch.fnmatch(path, glob):
            return True
    return False


def _snippet(line: str) -> str:
    s = line.strip()
    s = re.sub("[" + _AR + "]{6,}", lambda m: m.group(0)[:2] + "…", s)
    return s[:90]


_JOIN_RX = re.compile(r"""(['"])(.*?)\1\s*\.join\s*\(\s*[\[\(]([^\]\)]*)[\]\)]""")
_LIT_RX = re.compile(r"""(['"])(.*?)\1""")


def _joined_literals(line: str) -> str:
    """«"".join([...])» of string literals — the idiom `concat_digits` cannot see.

    The rule was born from a split account number (`"a" + "b"`), and the very
    file it caught later moved to `"".join(_PARTS)`, which walked straight past
    it. Detecting a rule's blind spot is part of the rule (external audit, S1).
    """
    built: list[str] = []
    for m in _JOIN_RX.finditer(line):
        sep, body = m.group(2), m.group(3)
        # The real value uses the separator: `" ".join(("١٤٣٩٠٧٢٢", "٢٠١٨٠٤٠٨"))`
        # is two dates, not a sixteen-digit run — welding them would be the same
        # false positive the first draft of the digit rule produced.
        built.append(sep.join(lit for _q, lit in _LIT_RX.findall(body)))
    return "".join(built)


# The pieces need not sit inside the join(): `_PARTS = ("a", "b")` on one line
# and `"".join(_PARTS)` on the next is the shape THIS repository adopted after
# the first rule caught `"a" + "b"` — so the file the rule was born from walked
# past it a second time (audit, round 3). A registry of name -> literal pieces
# closes it without needing a full parser.
_ASSIGN_SEQ_RX = re.compile(
    r"""^\s*([A-Za-z_][A-Za-z_0-9]*)\s*=\s*[\[\(]([^\]\)]*)[\]\)]""", re.M)
_JOIN_NAME_RX = re.compile(
    r"""(['"])(.*?)\1\s*\.join\s*\(\s*([A-Za-z_][A-Za-z_0-9]*)\s*\)""")
# Python welds adjacent string literals at PARSE time: `"a" "b"` is one string
# and no operator appears between them, so `concat_digits` never sees it.
_ADJACENT_LIT_RX = re.compile(r"""(['"])([^'"]*)\1[ \t]+(['"])([^'"]*)\3""")


def _literal_registry(text: str) -> dict[str, list[str]]:
    """`NAME = ("a", "b")` / `["a", "b"]` -> the pieces a later join() welds."""
    reg: dict[str, list[str]] = {}
    for m in _ASSIGN_SEQ_RX.finditer(text):
        lits = [lit for _q, lit in _LIT_RX.findall(m.group(2))]
        if lits:
            reg[m.group(1)] = lits
    return reg


def _joined_names(line: str, registry: dict[str, list[str]]) -> str:
    """`sep.join(NAME)` -> the string it builds, using the registered pieces."""
    built: list[str] = []
    for m in _JOIN_NAME_RX.finditer(line):
        sep, name = m.group(2), m.group(3)
        if name in registry:
            built.append(sep.join(registry[name]))
    return "".join(built)


def _weld_adjacent_literals(line: str) -> str:
    """`"a" "b"` -> `"ab"`, repeatedly (three or more pieces weld too)."""
    prev = None
    while prev != line:
        prev = line
        line = _ADJACENT_LIT_RX.sub(
            lambda m: m.group(1) + m.group(2) + m.group(4) + m.group(1), line)
    return line


# **حروفٌ صغيرة فقط** — والقياس هو الذي فرضها: بصمةُ sha256 تُكتب صغيرةً،
# والمعرّفاتُ التي نطاردها (IBAN · بطاقة · مرجع مُبطَّن) تُكتب **كبيرة** أو أرقاماً
# لا غير. فلو قبل العُرف الحروفَ الكبيرة لمرّ IBAN كامل تحت اسم «بصمة» — وهو ما
# أمسكه اختبارُ `test_an_upper_case_iban_is_still_blocked` بعد أن كان يمرّ.
HEX_CHARS = "0123456789abcdef"
HEX_LETTERS = "abcdef"


def _in_hex_token(src: str, match, min_len: int = 16) -> bool:
    """A ten-digit run inside a long hexadecimal token is a hash, not an account.

    Both auditors hit this: a commit sha blocked the message that documented it,
    and a guard that teaches its own team to omit evidence works against itself.

    TWO conditions, and the second one is the whole point. Length alone is not a
    discriminator, because DIGITS ARE HEXADECIMAL CHARACTERS: with length only,
    any digit run of `min_len` or more became "a hash" and walked out — measured
    at 30 of the 31 real statement descriptions that carry a ≥24-digit run
    (audit, 2026-09-17). A hash also carries at least one a–f letter; an account
    number, a card, an IBAN's digits and a padded reference never do. Requiring
    a letter keeps the sha exemption and closes the hole, and it fails SAFE: an
    all-digit token is scanned, not waived.

    و`min_len` نزل من 24 إلى **16**: القياس أراه — ملفُّ دليلٍ يحمل بصماتِ صفحاتٍ
    **مقتطعة** (16 محرفاً) حُجب ثلاث مرات، فصار الدليل يُحجب **لأنه دليل**. وشرطُ
    الحرف اللاتيني (a–f صغيرة) هو الفاصل الحقيقي: الحسابُ والبطاقة أرقامٌ بلا حروف،
    والـIBAN بحروفٍ **كبيرة** — فالبصمةُ الصغيرة تمرّ والمعرّفُ لا.
    """
    a = match.start()
    while a > 0 and src[a - 1] in HEX_CHARS:
        a -= 1
    b = match.end()
    while b < len(src) and src[b] in HEX_CHARS:
        b += 1
    token = src[a:b]
    return len(token) >= min_len and any(c in HEX_LETTERS for c in token)


def _is_digit_table(text: str) -> bool:
    """«٠١٢٣٤٥٦٧٨٩»-style translation tables are ramps, not account numbers.
    Rotations count too («۱۲۳۴۵۶۷۸۹۰»): the doubled-string check catches
    every cyclic shift of 0123456789 / 9876543210."""
    t = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
                                     "01234567890123456789"))
    doubled = t + t
    return "0123456789" in doubled or "9876543210" in doubled


def _digit_variants(line: str) -> list[str]:
    """The line plus every way a grouped run can hide inside it.

    A number a human reads as one value is often printed in uniform groups
    (IBANs, cards, cheques). Joining is allowed only when every group has the
    SAME width and that width is 3 or 4 — the two conditions that keep a pair
    of adjacent dates, a hyphenated timestamp and a row of equal-width
    amounts from being welded into a false account number.
    """
    out = [line]
    for m in _GROUPED_RUN.finditer(line):
        groups = re.split("[" + _GROUP_SEP + "]", m.group(0))
        if len(groups) < 2 or len(groups[0]) not in (3, 4):
            continue
        if len({len(g) for g in groups}) != 1:
            continue
        # ⚠️ **تراجعٌ مقصود (حكم المدقّق · الجولة ١٩):** كان هنا استثناءٌ يُسقط
        # «ثلاثاتٍ مفصولةً بفراغ» فتمرّ **أرقامُ حسابٍ من 15 و18 رقماً** مكتوبةً
        # بثلاثات — أي أنّ **قاعدةً أمنيةً وُسِّعت ليُرضى ملفٌّ واحد**. والعلاجُ
        # الصحيح: `.publish-allowlist` — سطرٌ لملفٍ بعينه **بسببٍ مكتوب**، فلا
        # تُوسَّع القاعدةُ على الشجرة كلها. وسمُّ الحالة في الاختبارات يمنع رجوعها.
        joined = line[:m.start()] + "".join(groups) + line[m.end():]
        if joined not in out:
            out.append(joined)
    return out


def _join_string_concat(line: str) -> str:
    """'aaaa' + 'bbbb' → 'aaaabbbb' (the trick that hid a real account)."""
    return _STRING_CONCAT.sub("", line)


def _scan_text(path: str, text: str, where: str, findings, entries) -> None:
    def record(sev, rid, lineno, src_line, desc):
        if _allowed(entries, rid, path, where):
            return
        findings.append((sev, rid, path, where, lineno, _snippet(src_line), desc))

    # Python-only welds: a registry of `NAME = (pieces…)` for a later join(),
    # and parse-time concatenation of adjacent literals. Restricted to .py
    # because both are Python semantics — applying them to prose would invent
    # numbers out of two quoted words that merely sit side by side.
    is_py = path.endswith(".py")
    registry = _literal_registry(text) if is_py else {}

    for lineno, line in enumerate(text.splitlines(), 1):
        if is_py:
            line = _weld_adjacent_literals(line)
        for rid, sev, rx, desc in TEXT_RULES:
            if rid == "long_digits":
                continue  # handled below over the digit-joined variants
            for _m in rx.finditer(line):  # every match, not just the first
                record(sev, rid, lineno, line, desc)
        named = _joined_names(line, registry) if registry else ""
        if named and LONG_DIGITS_RX.search(named) and not _is_digit_table(named):
            record("BLOCK", "joined_digits", lineno, line,
                   "رقم مبني بـ join على شظائف مُسمّاة")
        for src in _digit_variants(line):
            matches = [m for m in LONG_DIGITS_RX.finditer(src)
                       if not _is_digit_table(m.group(0))
                       and not _in_hex_token(src, m)]
            if matches:
                for _m in matches:  # every occurrence, not just the first
                    record("BLOCK", "long_digits", lineno, line,
                           LONG_DIGITS_DESC)
                break  # the joined variant already reported this line
        built = _joined_literals(line)
        if built and LONG_DIGITS_RX.search(built) and not _is_digit_table(built):
            record("BLOCK", "joined_digits", lineno, line,
                   "رقم مبني بـ join على شظائف نصية")
        joined = _join_string_concat(line)
        if joined != line:
            for m in LONG_DIGITS_RX.finditer(joined):
                if _is_digit_table(m.group(0)):
                    continue
                record(CONCAT_RULE[1], CONCAT_RULE[0], lineno, line,
                       CONCAT_RULE[2])
                break


def _binary_verdict(path: str, entries) -> tuple | None:
    """Decision for a tracked blob whose bytes are not decodable text.

    Pure and testable: media are handled by PATH_RULES, opaque binaries are
    handled by PATH_RULES too, so anything left here is an unknown binary —
    and silence is the one answer that is never acceptable.
    """
    ext = Path(path).suffix.lower()
    if ext in MEDIA_EXTS or ext in OPAQUE_EXTS:
        return None
    if _allowed(entries, "undecodable", path):
        return None
    return ("BLOCK", "undecodable", path, "", 0, "",
            "ملف لا يُفك كنص ولم يُدرج في قوائم الوسائط — لا يُدفع بصمت")


def _check_path(path: str, where: str, findings, entries) -> None:
    if path in SKIP_PATHS or path.startswith(".githooks/"):
        return
    for rid, sev, pred, desc in PATH_RULES:
        try:
            hit = pred(path)
        except Exception:
            hit = False
        if hit and not _allowed(entries, rid, path, where):
            findings.append((sev, rid, path, where, 0, "", desc))


def _tree_entries(rev: str) -> list[tuple[str, str]]:
    """[(path, blob_sha)] for a commit tree — **بلا تقويس** (`_git_z`).

    **والحكمُ على شكل السجلّ كما في التاريخ (مقعدُ المعايير · ٦٨ج):** كانت السجلَّاتُ غيرُ المفهومة
    تُسقَط بـ`continue` ⇒ مخرجٌ **برمز خروجٍ صفرٍ** وشكلٌ تغيّر يُقرأ «شجرةً نظيفةً» بصمت — وهو
    الصنفُ نفسُه الذي حُصّن ضدَّه `_history_pairs`، فصار القارئان على سياسةٍ واحدة: كلُّ سجلٍّ إمّا
    يُفهَم أو يُوقف الحكم. و`tree`/`commit` في `ls-tree` **مشروعةٌ** (وحدةٌ فرعيّة/submodule) فتُتخطّى
    صراحةً بلا استثناء — والفرقُ بين «مشروعٌ لا يُمسح» و«غيرُ مفهوم» مقيسٌ في الضابط.

    **وحدٌّ متبقٍّ مُعلَن كما في التاريخ (مقعدُ البنية T6 · ٦٨د):** إذا كانت **كلُّ** سجلّات الشجرة
    مشروعةً وغيرَ بلوبات (وحداتٌ فرعيّة فقط) فالنتيجةُ `tree: 0 · 0 BLOCK · «آمن للدفع» · rc=0` —
    أي لا يفترق «لا بلوبَ يُمسح» عن «لم تُقرأ سجلّاتُ البلوبات». وهو **تصميمٌ مقصود** (التزامٌ بشجرةٍ
    فارغةٍ مشروع — `test_an_empty_tree_commit_is_not_a_measurement_failure`) لكنّه **حدٌّ يُعلَن لا
    يُخفي**، وقياسُه في `not_proven` ما لم تُوجد إشارةٌ تُفرّق الحالتين بلا صرخةٍ كاذبة.
    """
    pairs = []
    for rec in _git_z("ls-tree", "-r", rev):
        if "\t" not in rec:
            raise GitReadError(
                f"`ls-tree -r -z` قرأ سجلًّا بلا مسارٍ مفصولٍ بـTAB: {rec[:60]!r} ⇒ صيغةُ المخرَج "
                f"تغيّرت (فشلٌ مُغلَق: لا حكمَ على ما لم يُقرأ)")
        meta, path = rec.split("\t", 1)
        parts = meta.split()
        if not (len(parts) >= 3 and parts[1] in ("blob", "tree", "commit")):
            raise GitReadError(
                f"`ls-tree -r -z` قرأ سجلًّا غيرَ مفهوم: {meta[:60]!r} ⇒ لا نوعَ كائنٍ ولا معرّف "
                f"(فشلٌ مُغلَق)")
        if parts[1] == "blob":
            pairs.append((path, parts[2]))
    return pairs


def _scan_blobs(pairs: list[tuple[str, str]], where: str,
                findings, entries, seen: set[str]) -> None:
    """**وحدٌّ ثالثٌ مُعلَن من الصنف نفسه (مقعدُ البنية T6 · ٦٨د):** كلُّ كائنٍ لا يكون بلوبًا
    (شجرةٌ · وسمٌ · التزامٌ) يُسقَط بـ`continue` أدناه بلا عدّادٍ ولا حكم — أي **«ما لم يُقرأ يُقرأ
    نظيفًا»** في صورةٍ ثالثة، أُعلن شقيقاها (حدُّ التاريخ · حدُّ الشجرة). والمُعلَنُ الآن هو حدُّه
    المقيسُ **صنفًا لا لقطة:** كلُّ معرّفٍ يعود من `git rev-list --objects --all` ولا يكون بلوبًا
    يُسقَط هنا. وعددُه **يتحرّك مع المخزن** (قِيس عند مقعد البنية **1381 من 3350** على نسخةٍ نقيّة،
    وفي قياسي **1363 من 3315**) ⇒ **فلا يُنقل الرقمُ بلا بيئته**، والأمرُ هو الشاهد:
    `git rev-list --objects --all | wc -l` مقابل ما يقرؤه `_read_blobs`.
    **وحدُّه:** الأشجارُ/الأوسمةُ لا تحمل نصًّا يُمسح في هذا الفحص، فالإسقاطُ لا يُخفي نصًّا كان
    يجب مسحُه — وهذا **مُعلَنٌ لا مُغلَقٌ**: لو صار للوسم/الشجرة نصٌّ يهمّ الفحص، يُعاد النظرُ فيه.
    """
    blob_of = {}
    for path, sha in pairs:
        _check_path(path, where, findings, entries)
        if path in SKIP_PATHS or path.startswith(".githooks/"):
            continue
        if Path(path).suffix.lower() in (BINARY_EXTS | OPAQUE_EXTS):
            continue  # unreadable by design; their verdict comes from PATH_RULES
        blob_of.setdefault(sha, path)
    fresh = [sha for sha in blob_of if sha not in seen]
    blobs = _read_blobs(fresh)
    for sha in fresh:
        seen.add(sha)
        data = blobs.get(sha)
        if data is None:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            verdict = _binary_verdict(blob_of[sha], entries)
            if verdict:
                findings.append(verdict[:-1] + (where,) + verdict[-1:])
            continue
        _scan_text(blob_of[sha], text, where, findings, entries)


def scan_tree(findings, entries, seen) -> int:
    # **ولا شرطَ صفرٍ هنا (مقعدا البنية والمواصفة · ٦٨ب):** كان الشرطُ على الأزواج **المشتقّة** ⇒
    # فالتزامٌ بشجرةٍ فارغة (`commit --allow-empty`) يُصنَّف «تعذّرَ قياس» برمز ٢، بينما `--history`
    # على المستودع نفسِه يقول «آمن» برمز ٠ — حكمان متناقضان لحالتين متماثلتين في مشروعيّتهما، وصرخةٌ
    # كاذبةٌ في مسار الدفع أيضًا (`scan_pre_push` تنادي هذه الدالّة). والمقياسُ الصادقُ هو **ما قرأته git**:
    # `ls-tree` تُخرج صفرًا برمز ٠ لشجرةٍ فارغة (قِيس)، والقراءةُ التي لم تقع يرفعها `_run_git` نفسُه.
    pairs = _tree_entries("HEAD")
    _scan_blobs(pairs, "tree", findings, entries, seen)
    return len(pairs)


def scan_history(findings, entries, seen) -> int:
    # Every object ONCE (rev-list dedupes objects); the same path appears
    # many times across commits with different blob shas — ALL versions must
    # be scanned, or an older commit that still carries PII slips through.
    # (An earlier version deduped by path and kept only the newest blob —
    # caught by running it: older test fixtures with real names were masked.)
    pairs, dedup = [], set()
    for path, sha in _history_pairs():
        if (path, sha) in dedup:
            continue
        dedup.add((path, sha))
        pairs.append((path, sha))
    _scan_blobs(pairs, "history", findings, entries, seen)
    return len(pairs)


_GIT_GENERATED_MESSAGES = (
    re.compile(r"^Merge [0-9a-f]{7,40} into [0-9a-f]{7,40}"),
    re.compile(r"^Merge (pull request|remote-tracking branch|branch) "),
    re.compile(r"^Revert "),
)


def _is_git_generated(body: str) -> bool:
    """رسالة كتبها git/GitHub لا بشر: تجزئاتها الطويلة تُشبه رقم حساب.

    قاعدة `joined_digits` تجمع الأرقام عبر الفواصل، فالتزام الدمج الذي يولّده
    GitHub («Merge <sha> into <sha>») يُنتج سلسلة ٣٦ رقماً ويُرفض ظلماً ⇒ كل طلب
    دمج يسقط على رسالة لا كتبها إنسان ولا تحمل بيانات. والتخطّي **معلن** ويُطبع
    عدده، فلا يصير ثقباً صامتاً: كل رسالة يكتبها بشر تبقى مفحوصة كما هي.
    """
    first = body.strip().splitlines()[0] if body.strip() else ""
    return any(rx.match(first) for rx in _GIT_GENERATED_MESSAGES)


def scan_messages(findings, entries, revs: list[str] | None = None) -> int:
    """Commit messages carry text too — an account number pasted into a
    message body is exactly as public as one pasted into a file, and until
    now messages were never scanned at all. The public repo URL already
    carries the owner's handle, so `name_token` findings here are WARN at
    worst (attribution), never a block. Author/committer identities are NOT
    scanned for the same reason: they are already public on the remote."""
    args = ["log", "--format=%H%x09%B%x1e"]
    if revs:
        args += list(revs)
    else:
        args.append("--all")
    out = _git(*args)
    n = 0
    synthetic = 0
    for chunk in out.split("\x1e"):
        sha, _, body = chunk.partition("\t")
        sha = sha.strip()
        if not sha or not body.strip():
            continue
        n += 1
        if _is_git_generated(body):
            synthetic += 1
            continue
        pseudo = f"git-msg/{sha[:10]}"
        for rid, sev, rx, desc in TEXT_RULES:
            for m in rx.finditer(body):
                if rid == "long_digits" and _is_digit_table(m.group(0)):
                    continue
                if _allowed(entries, rid, pseudo):
                    continue
                findings.append((sev, rid, pseudo, "message", 0,
                                 _snippet(m.group(0)), desc))
        joined = _join_string_concat(body)
        if joined != body:
            for m in LONG_DIGITS_RX.finditer(joined):
                if _is_digit_table(m.group(0)):
                    continue
                findings.append(("BLOCK", CONCAT_RULE[0], pseudo, "message",
                                 0, _snippet(body), CONCAT_RULE[2]))
                break
    if synthetic:
        print(f"[publish-guard] تخطّي {synthetic} رسالة دمج/استرجاع ولّدها git أو "
              f"GitHub (تجزئاتها الطويلة تُشبه رقم حساب، ولا يكتبها بشر)")
    return n


def _commits_not_on_remotes(sha: str) -> set[str]:
    """الالتزاماتُ الموصولةُ بـ`sha` وغيرُ الموجودة على أيّ ريموتٍ معروف.

    **قاعدةٌ واحدةٌ في موضعٍ واحد (مقعدُ البنية · ٦٨ج):** كان هذا التعبيرُ مكتوبًا مرّتين في
    `scan_pre_push` (فرعُ المرجع الجديد وفرعُ البديل المحافظ) ⇒ استُخرج ليُعلن أنّ المسلكين
    قاعدةٌ واحدة لا نسختان.
    """
    return set(_git("rev-list", sha, "--not", "--remotes").split())


def scan_pre_push(findings, entries, seen) -> int:
    refs = [l.split() for l in sys.stdin.read().splitlines() if l.strip()]
    revs: set[str] = set()
    for parts in refs:
        if len(parts) < 4:
            continue
        local_sha, remote_sha = parts[1], parts[3]
        if set(local_sha) <= {"0"}:
            continue  # branch deletion
        if set(remote_sha) <= {"0"}:
            # مدى الدفع لكامل القائمة الحالية: نطبعها لكل مرجع على حدة.
            revs.update(_commits_not_on_remotes(local_sha))
        else:
            try:
                _run_git(("cat-file", "-e", remote_sha))
            except GitReadError:
                # **مرجعٌ على الريموت لم يُجلَب ليس عطبًا يمنع دفعًا مشروعًا (مقعدُ البنية · ٦٨ب):**
                # حالتان مشروعتان: فرعٌ أُنشئ على الريموت · وتاريخٌ أُعيد كتابتُه فجُلب ناقصًا ⇒
                # `remote_sha..local_sha` يُسقط git برمز 128 ⇒ فكانت السياسةُ الموحَّدة تُخرج ٢،
                # والخطّافُ `|| exit 1` **يمنع دفعًا مشروعًا** — وهو ما يمنعه `.githooks/pre-push`
                # بنصّه («خطّافٌ يمنع دفعًا مشروعًا يُصنع به الحافزُ على --no-verify»). فالعلاجُ في
                # موضعه لا في السياسة: يُعلَن المرجعُ ويُمسح **كلُّ ما هو موجودٌ محليًّا** (بديلٌ محافظ
                # كان يعمل قبل التوحيد)، و«لا حكم» تبقى لِما لم يُقرأ فعلًا.
                print(f"[publish-guard] مرجعٌ على الريموت غيرُ موجودٍ محليًّا ({remote_sha[:12]}) "
                      f"⇒ يُمسح كلُّ ما هو موجودٌ محليًّا (لا «لا حكم» على دفعٍ مشروع)")
                revs.update(_commits_not_on_remotes(local_sha))
            else:
                revs.update(_git("rev-list", f"{remote_sha}..{local_sha}").split())
    # No sampling: a commit that carried PII and was later rewritten is
    # exactly the case this mode exists for, and picking "the first 200 by
    # SHA text" is a random sample dressed up as coverage. Blob dedup (`seen`)
    # keeps the cost linear in NEW blobs, not in commits.
    pairs = []
    for rev in sorted(revs):
        pairs.extend(_tree_entries(rev))
    _scan_blobs(pairs, "push", findings, entries, seen)
    n = len(pairs)
    n += scan_messages(findings, entries, sorted(revs))
    n += scan_tree(findings, entries, seen)
    return n


def main() -> None:
    """**نقطةُ سياسةٍ واحدة لتعذّر القراءة (مقعدا البنية والمواصفة · جولة ٦٨):** كان حدُّ
    `GitReadError` موضعيًّا حول مسح الشجرة/التاريخ ⇒ ففرعُ `--tracked-real-data` — وهو خطوةُ الـCI
    للبوّابة ٨ بنفسه — يُخرج أثرًا (traceback) برمز ١، ورمزُ ٢ المُعلَن في `docs/GATES.md` لا يصله.
    فالسياسةُ الآن على **متن التقرير كلِّه**: تعذّرُ قراءةٍ ⇒ رسالةٌ مُعلَنة ورمزُ **٢** (لا حكمَ على
    ما لم يُقرأ)، و**١** يبقى محجوزًا لـ«وُجد ما يُحجب».
    """
    try:
        _run_report()
    except GitReadError as exc:
        print(f"⛔ تعذّر إتمامُ القراءة ⇒ **لا حكم**: {exc}")
        print("   (فشلٌ مُغلَق: لا تُقرأ «صفرُ مطابقات» على أنّها نظافة.)")
        sys.exit(2)


def _run_report() -> None:
    ap = argparse.ArgumentParser(description="publish-time PII guard")
    ap.add_argument("--tree", action="store_true", help="scan HEAD tree")
    ap.add_argument("--history", action="store_true",
                    help="scan every blob in every commit")
    ap.add_argument("--pre-push", action="store_true", dest="pre_push",
                    help="read refs from stdin (git hook) and scan them")
    ap.add_argument("--ci", action="store_true",
                    help="tree + history + commit messages (CI mode)")
    ap.add_argument("--messages", action="store_true",
                    help="scan every commit message body")
    ap.add_argument("--strict-warn", action="store_true", dest="strict_warn",
                    help="treat WARN as blocking (opt-in; default is advisory)")
    ap.add_argument("--report-only", action="store_true",
                    help="print findings but always exit 0")
    ap.add_argument("--tracked-real-data", action="store_true", dest="tracked_real_data",
                    help="فشلٌ إن كان أيُّ ملفٍّ مُتتبَّعٍ تحت مجلّد بياناتٍ حقيقيّة (بأيّ عمق)")
    args = ap.parse_args()

    if args.tracked_real_data:
        # **مالكٌ واحد للقاعدة (مراجعة ٦٧):** كانت خطوةُ الـCI تحمل نمطًا جذريًّا خاصًّا بها
        # (`^data/(local_sample|training|eval_pack)/`) ⇒ فاتها التداخلُ — وفات التداخلُ هذا الحارسَ أيضًا.
        # فصار الاثنان يستدعيان `real_data_path` نفسَها: قاعدةٌ واحدة، ولا نمطَ ثانٍ يزيح معها.
        # **ولا يُسكِت نمطًا آخر بصمت (مقعدُ البنية · جولة ٦٧):** كان `return` في النهاية يُهمل
        # `--tree/--history/--ci` إن اجتمعت معه ⇒ فإمّا تُستدعى وحدَها، وإمّا يُعلَن الرفض.
        others = [n for n, v in (("--tree", args.tree), ("--history", args.history),
                                 ("--ci", args.ci), ("--pre-push", bool(args.pre_push))) if v]
        if others:
            print(f"⛔ `--tracked-real-data` نمطٌ **واحدٌ قائمٌ بذاته**: لا يُجمع مع {others} "
                  f"(وإلّا أُهمل الآخرُ بصمت) ⇒ شغّلهما في استدعاءَين.")
            sys.exit(2)
        # **بلا تقويس (جولة ٦٧):** `git ls-files` وحدَه يقوّس المسارَ العربيَّ فيُفلت ⇒ `_git_z`.
        tracked = _git_z("ls-files")
        # **ولا شرطَ صفرٍ هنا (مقعدا المواصفة والبنية · ٦٨ب — وتصحيحٌ لما أدخلتُه في الطلب نفسِه):**
        # «مستودعٌ يُدفع منه ليس بلا ملفّاتٍ مُتتبَّعة» مقدّمةٌ **مُكذَّبةٌ بالقياس**: مستودعٌ بلا ملفّاتٍ
        # مُتتبَّعة حالةٌ مشروعة (‏`git init` قبل أول إضافة)، وعداها كان يُخرج رمزَ ٢ عليها ويُخرِج
        # «آمن» على تاريخها نفسِه ⇒ تناقضٌ وصرخةٌ كاذبة. والمقياسُ الصادقُ: `ls-files` تُخرج صفرًا
        # برمز ٠ لحالةٍ فارغةٍ حقيقةً، والقراءةُ التي لم تقع يرفعها `_run_git`.
        bad = [p for p in tracked if real_data_path(p)]
        print(f"[publish-guard] tracked-real-data: {len(tracked)} ملفًّا مُتتبَّعًا — "
              f"{len(bad)} تحت مجلّدات البيانات الحقيقيّة")
        for p in bad:
            print(f"  BLOCK  local_data    [tracked] {p}")
        if bad:
            print("\nالحكم: BLOCK — ملفُّ بياناتٍ حقيقيّةٍ مُتتبَّع (ولو متداخلًا): يُزال من الفهرس "
                  "ويُضاف إلى `.gitignore`.")
            if not args.report_only:
                sys.exit(1)
        else:
            print("الحكم: لا ملفَّ بياناتٍ حقيقيّةٍ مُتتبَّع — بأيّ عمق.")
        return

    if not (args.tree or args.history or args.pre_push or args.ci
            or args.messages):
        args.tree = True

    entries = load_allowlist()
    findings: list[tuple] = []
    seen: set[str] = set()
    scanned = []

    if args.pre_push:
        scanned.append(("push", scan_pre_push(findings, entries, seen)))
    if args.tree or args.ci:
        scanned.append(("tree", scan_tree(findings, entries, seen)))
    if args.history or args.ci:
        scanned.append(("history", scan_history(findings, entries, seen)))
        scanned.append(("messages", scan_messages(findings, entries)))
    if args.messages and not (args.history or args.ci):
        scanned.append(("messages", scan_messages(findings, entries)))

    blocks = [f for f in findings if f[0] == "BLOCK"]
    warns = [f for f in findings if f[0] == "WARN"]
    print("[publish-guard] " +
          " · ".join(f"{label}: {n}" for label, n in scanned) +
          f" — {len(blocks)} BLOCK / {len(warns)} WARN")
    if warns:
        print("[publish-guard] تنبيه معلن (لا يوقف الدفع):")
        for sev, rid, path, where, lineno, snip, desc in warns:
            loc = f"{path}:{lineno}" if lineno else path
            print(f"  WARN  {rid:<12} [{where}] {loc}"
                  + (f"  | {snip}" if snip else "") + f"  — {desc}")
        print("  → للمنع الصارم: أضف --strict-warn، أو استثناءً مبرَّراً "
              "في .publish-allowlist (كل سطر بسبب مكتوب).")
    for sev, rid, path, where, lineno, snip, desc in blocks:
        loc = f"{path}:{lineno}" if lineno else path
        print(f"  {sev:<5} {rid:<12} [{where}] {loc}"
              + (f"  | {snip}" if snip else "") + f"  — {desc}")
    if blocks:
        print("\nالحكم: BLOCK — لا تدفع حتى تُعالج هذه البنود "
              "(أو أضف استثناءً مبرَّراً في .publish-allowlist).")
    else:
        print("\nالحكم: آمن للدفع.")
    if (blocks or (warns and args.strict_warn)) and not args.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
