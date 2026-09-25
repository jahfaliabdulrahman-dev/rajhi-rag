"""**ماسحُ الأسرار: يرى أصنافَ هذا المشروع، ولا يطبع قيمةً، ويفشل مُغلَقًا.**

وُلد من مراجعة ٥٣ (مدقّقٌ مستقلّ بمفاتيحَ مصطنعة): النمطُ الواحد في `pre-commit` كان يمرّر
`sk-or-v1-…` و`sk-ant-…` (صنفُ الرمز الذي تسرّب فعلًا) و`sk-proj-…` و`github_pat_…` — لأنّه توقّف عند
أوّل شَرطة. ⇒ الفحصُ انتقل إلى أداةٍ ذاتِ نمطٍ لكلّ صنف، وهذه ضوابطُها.

⚠ **ولا يُكتب سِرٌّ في هذا الملفّ حرفيًّا**: القيمُ تُبنى بالضَمّ وقتَ التشغيل ⇒ فلا الخطّافُ ولا أيُّ
ماسحٍ يرى سِرًّا حقيقيًّا في هذه الضوابط. (والمقاطعُ وحدها **يجب ألّا تُطابَق** — وهذا ضابطٌ بنفسه.)
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("secret_scan", ROOT / "tools" / "secret_scan.py")
    assert spec is not None and spec.loader is not None, "تعذّر تحميلُ الماسح ⇒ لا قياس"
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _pair_at(text: str, pattern: str) -> tuple[int, int] | None:
    """أوّلُ زوجٍ رقميّ يطابقه النمطُ في النصّ (والأرقامُ العربيةُ تُوحَّد) — أو `None` (والغيابُ يُكشَف)."""
    m = re.search(pattern, text.translate(_AR_DIGITS))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _fakes() -> dict[str, str]:
    """قيمٌ مصطنعةٌ لكلّ صنف (تُبنى ولا تُكتب) — الحشوُ تكرارُ حرفٍ واحد فلا يشبه شيئًا حقيقيًّا."""
    return {
        "anthropic": "sk-ant-" + "api03-" + "x" * 40,
        "openrouter": "sk-or-v1-" + "0" * 40,
        "openai_project": "sk-proj-" + "y" * 40,
        "openai_legacy": "sk-" + "z" * 40,
        "github_pat": "github_pat_" + "a" * 30,
        "github_token": "ghp_" + "b" * 40,
        "aws_access_key": "AKIA" + "C" * 16,
        "google_api_key": "AIza" + "d" * 35,
        "slack_token": "xoxb-" + "e" * 20,
        "private_key_block": "-----BEGIN RSA " + "PRIVATE KEY-----",
        "jwt": "eyJ" + "f" * 20 + "." + "eyJ" + "g" * 20 + "." + "h" * 20,
    }


def test_every_secret_class_is_caught():
    """**الضابطُ الأساسي**: كلُّ صنفٍ على حدة، والماسحُ يسمّي صنفَه (بلا قيمة)."""
    m = _load()
    missed = []
    for name, value in _fakes().items():
        hits = m.scan_lines([(1, f"KEY={value}")])
        if name not in [h[1] for h in hits]:
            missed.append(name)
    assert not missed, f"أصنافٌ تمرّ صامتة: {missed} (وهي بعينها ما أمسكه المدقّق في الجولة السابقة)"


def test_a_named_assignment_with_an_opaque_value_is_caught():
    """**الحدُّ المُعلَن يُغلق ما يمكن إغلاقه**: سِرٌّ مجهولُ الشكل لكنه مُسنَدٌ باسمٍ صريح."""
    m = _load()
    hits = m.scan_lines([(7, 'api_key = "' + "q" * 30 + '"')])
    assert hits and hits[0] == (7, "named_assignment"), hits


def test_the_building_blocks_alone_are_not_secrets():
    """**ضابطٌ سالب**: مقاطعُ الأسماء وحدها (`sk-ant-` · `AKIA` · `github_pat_`) ليست أسرارًا.

    (وهو ما يجعل كتابةَ هذه الضوابط نفسِها آمنة: لا سِرَّ حرفيًّا في المستودع.)
    """
    m = _load()
    for frag in ("sk-ant-", "sk-or-v1-", "sk-proj-", "github_pat_", "AKIA", "xoxb-"):
        assert m.scan_lines([(1, f"اسمُ الصنف: {frag}")]) == [], f"مقطعٌ يُطابَق خطأً: {frag}"


def test_a_clean_text_has_no_hits():
    m = _load()
    clean = ["# تعليقٌ عاديّ", "def f(x):", "    return x + 1", "TOKEN_ENV_NAME = 'OPENROUTER_API_KEY'",
             'notes = "ضع المفتاح في .env لا في الكود"', "sha = 'a' * 64"]
    assert m.scan_lines(list(enumerate(clean, 1))) == []


def test_the_report_never_prints_the_value(tmp_path, capsys):
    """**القاعدة ١٣**: ما يُقاس لا يُسرّب — يُطبَع رقمُ السطر واسمُ الصنف فقط."""
    m = _load()
    value = _fakes()["anthropic"]
    p = tmp_path / "leak.txt"
    p.write_text(f"ANTHROPIC_API_KEY={value}\n", encoding="utf-8")
    rc = m.main(["--text", str(p)])
    out = capsys.readouterr().out
    assert rc == 1, f"سِرٌّ في ملفّ ⇒ 1 (صار {rc})"
    assert value not in out, "طُبعت القيمة! (القاعدة ١٣)"
    assert "anthropic" in out, "لم يُسمَّ الصنف"


def test_a_missing_file_fails_closed(tmp_path, capsys):
    """**فشلٌ مُغلَق**: تعذّرُ الفحص لا يُقرأ نظافةً."""
    m = _load()
    rc = m.main(["--text", str(tmp_path / "لا-يوجد.txt")])
    assert rc == 2, f"تعذّر الفحص ⇒ 2 (صار {rc})"
    assert "مُغلَق" in capsys.readouterr().out


# ── P-4 · «الرابطُ المُوسَم»: معرّفٌ لا وجودَ له في هذا المستودع (تبنّاه المدقّق في مراجعة ٥٤) ──

#: **دَينٌ مُعلَنٌ ومُثبَتُ التركيب**: عددُ الأسطر على الكوربوس المُتتبَّع التي تحمل معرّفاً لا وجودَ له في
#: رسم المستودع. **والتركيبُ مُقاسٌ لا موصوف — وأُعيد قياسُه بعد R57-3:** **٤٧ سطراً كلُّها بكلمة `commit`**
#: (ترويساتُ رسائلَ قديمة: `commit: <hex>` تشير إلى التزاماتٍ **ما قبل التنقية**) ⇒ فهو دَينُ الصنفِ الذي
#: يطارده P-4 لا ضجيجَ بصماتِ ملفّ (تلك **لا تعبر البوّابةَ أصلًا** بعد R56-1ب).
#: **وتصحيحٌ مؤرَّخ (مراجعة ٥٧ · R57-3):** كان مكتوباً هنا «٤٧ بـ`commit` وواحدٌ بكلمة `sha`» — والقياسُ
#: كذّبه في شقّه الثاني: السطرُ الثامنُ والأربعون أجازته `rev` في **`git rev-parse`** (أمرٌ لا معرّف) ومعرّفُه
#: بصمةُ ملفٍّ، فسقط بالحدّ الجديد لـ`rev` وصار العددُ **٤٧ لا ٤٨**. وهذا «كشفٌ فقدناه» كان الراتشتُ لا يراه
#: (القيمةُ لم تتحرّك لأنّ الكوربوس لا يحوي سطراً بكلمة `sha` وحدها) ⇒ وُلد منه ضابطٌ موجبٌ صريح أدناه.
#: **والسقفُ راتشتٌ في الاتجاهين** (`==` لا `<=`): الصعودُ يقول «انكشافٌ جديد» والنزولُ يقول «كشفٌ مفقود»
#: — وكلاهما يستحقّ توقّفاً، لا أن يُبتلع صامتاً. (تاريخُه: ٨٥ ⇒ ٦٣ ⇒ ٦٤ ⇒ ٥٠ ⇒ ٤٨ ⇒ **٤٧**.)
FOREIGN_ID_DEBT_ON_CORPUS = 47
#: **وصيغةُ الكشيدة (R57-3) تُقاس هي أيضاً — أسطراً وملفّات** (S-3 · قاسه مقعد المعايير): كان في §٢٦ وفي
#: ترويسة الأداة «٢٧ سطراً في **١٦** ملفّاً» وهو **مكتوبٌ بيدٍ** وقياسُه **١١** ⇒ رقمٌ يُكذّبه مقياسُه في
#: وثيقةٍ معياريّة. والآن يُقاس في الاتجاهين: الصعودُ = صيغةٌ/ملفٌّ جديد، والنزولُ = **كشفٌ فقدناه**.
#:
#: **R58-1 (مراجعة ٥٨ · الحاجب) — المقامُ كان خاطئاً والمقياسان مختلفين:**
#:   ‹١› **المقام:** العدّادُ كان يقرأ **كتلَ المراسلة** (`handoff/`) ⇒ نصُّ المدقّق يصير مُدخَلاً إلى راتشتٍ
#:       يملكه المنفّذ، فلا يستطيع إنزالُ مراجعةٍ تقتبس الصيغة (صنفُ R57-1 عائداً). **وأُعيد إنتاجه قبل
#:       الإصلاح:** بمراجعة ٥٧ في المتتبَّع صار العدُّ **٣١ سطراً في ١٢ ملفّاً** ⇒ `1 failed`.
#:       **وصناديقُ المراسلة ليست كوربوسَ المنفّذ** ⇒ تُستثنى، والمُستثنى **يُطبَع** لا يُخفى.
#:   ‹٢› **القاعدة:** الماسحُ `(?i)` والعدّادُ كان حسّاساً للحالة ⇒ **مقياسان لمعنى واحد**. والعدّادُ الآن
#:       على قاعدة الماسح نفسِها.
#:   ‹٣› **قياسٌ مؤرَّخ (2026-09-25 · `HEAD` · بلا `handoff/`):** **١١ سطراً في ٤ ملفّات** — وهو
#:       **المقامُ المُعلَن** الذي يُقابَل بالمقياس الحيّ (والشجرةُ كلُّها **لا تُقابَل**: انظر R59-1).
#:   ‹٣ب› **وتصحيحٌ مؤرَّخ (R59-3 · مراجعة ٥٩):** كان هنا «27·16 على الشجرة كلِّها ⇒ **لا يُعاد إنتاجه
#:       بأيّ قاعدةٍ ولا مقام**» — **والأمرُ يُعيده**: قاعدةُ الماسح نفسُها (الصيغةُ + الامتداداتُ الأربعة)
#:       على ملفّات الشجرة `e903b12` ⇒ **`27 16`**. والقاعدةُ (§٢٣) أن يُكتب كلُّ رقمٍ **مع شجرته**،
#:       لا أن يُنفى رقمُ شجرةٍ أخرى؛ والرقمان (٢٧·١١ و٣٦·١٨) صحيحان لشجرةٍ **لاحقة** ومؤرَّخان في §٢٦.
#:   ‹٤› **والاستثناءُ ليس عَمىً:** صيغةٌ **خارج** الصندوق تُحسَب — ضابطٌ اصطناعيٌّ أدناه يقيس الاتجاهين.
TATWEEL_FORM_EXCLUDED_PREFIX = "handoff/"
#: **وقاعدةُ الحالة تُشتقّ من الماسح لا تُكتب ثانياً (P3-9 · مقعدُ البنية):** كان `False` ثابتاً معلَّلاً
#: بأنّه «قاعدةُ الماسح `(?i)`» — وهو **قولٌ لا قراءة**؛ فصار يُقرأ من `ID_CONTEXT.flags` (مصدرٍ واحد)،
#: ويُقاس سلوكُه على الصيغتين في ضابطٍ أدناه (فلا يكفي الاشتقاقُ بلا أثرٍ مرئيّ).
TATWEEL_FORM_CASE_SENSITIVE = not bool(_load().ID_CONTEXT.flags & re.IGNORECASE)
TATWEEL_FORM_LINES = 11
TATWEEL_FORM_FILES = 4
#: **والعدّادُ الثاني (P-4 · `scan_foreign_ids`) كان يقرأ الكوربوس نفسه بلا الاستثناء نفسِه (F1 · مراجعة
#: ٥٩):** قياسُ المقعد: **47 إيجاباً كلُّها داخل `handoff/` · وصفرٌ خارجه** ⇒ فالبوّابةُ كانت تراتش على
#: **صندوق المراسلة** لا على كوربوس المنفّذ (صنفُ R57-1 بعينه: مراجعةٌ تقتبس `commit:` تُحمرّ المنفّذ).
#: والآن: المقامُ = الشجرةُ المتتبَّعة **بلا `handoff/`**، والسقفُ = المقيسُ فيه، والمُستثنى **يُطبَع**.
FOREIGN_ID_EXCLUDED_PREFIX = "handoff/"
FOREIGN_ID_DEBT_ON_CORPUS = 0
FOREIGN_ID_DEBT_INSIDE_MAILBOX = 47        # دَينٌ تاريخيٌّ مُعلَن — **لا يُراتَش** (لا يُعاقَب المدقّقُ)


def _tatweel_form_counts(files, root=ROOT, excluded_prefix=TATWEEL_FORM_EXCLUDED_PREFIX):
    """يعدُّ صيغةَ الكشيدة على **ملفّاتٍ معطاة** ويُعيد (الأسطر, الملفّات, المقيس, المُستثنى).

    مُستخرَجٌ في دالّةٍ **ليقيسه ضابطٌ بمُدخَلٍ اصطناعيٍّ**: المقامُ نفسُه يُقاس، لا الشجرةُ وحدها.
    (وبلا استثناءٍ صامت: عددُ المُستثنى يعود مع النتيجة فيُطبَع في رسالة السقوط.)
    """
    rx = re.compile("\u0640sha", 0 if TATWEEL_FORM_CASE_SENSITIVE else re.IGNORECASE)
    lines = hit_files = counted = excluded = 0
    for f in files:
        if excluded_prefix and f.startswith(excluded_prefix):
            excluded += 1
            continue
        counted += 1
        try:
            body = (root / f).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        hits = sum(1 for ln in body if rx.search(ln))
        lines += hits
        hit_files += 1 if hits else 0
    return lines, hit_files, counted, excluded


def _foreign_id_counts(files, root=ROOT, excluded_prefix=FOREIGN_ID_EXCLUDED_PREFIX):
    """يعدُّ إيجابيّات إشارةِ الخارِج على **ملفّاتٍ معطاة** ⇒ (المقيس, المُستثنى, عددُ الملفّات المقيسة).

    مُستخرَجٌ في دالّةٍ **ليقيسه ضابطٌ بمُدخَلٍ اصطناعيٍّ** (F1): المقامُ نفسُه يُقاس لا الشجرةُ وحدها.
    """
    m = _load()
    counted = excluded = files_counted = 0
    for f in files:
        try:
            body = (root / f).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        hits = sum(1 for i, ln in enumerate(body, 1) if m.scan_foreign_ids([(i, ln)]))
        if excluded_prefix and f.startswith(excluded_prefix):
            excluded += hits
        else:
            files_counted += 1
            counted += hits
    return counted, excluded, files_counted


def test_the_corpus_positive_rate_is_declared_and_capped():
    """**الصدقُ في المعدّل**: أداةٌ تُعلن نظافتَها على الكوربوس بينما تُنتج عشراتِ الإيجابيّات = ادّعاء.

    ولا تُصلَح آليّاً (تُراجَع بشرٍ): فالقياسُ هنا **سقفٌ مُعلَن** يمنع النموّ — أي أنّ أيَّ توسيعٍ للسياق
    أو صيغةٍ جديدة تُضاعف المعدّل **يُكشَف فوراً** بدل أن يُبتلع. **والمقامُ بلا `handoff/` (F1 · R58-1):**
    صناديقُ المراسلة ليست كوربوسَ المنفّذ، والمُستثنى **يُطبَع** لا يُخفى.
    """
    files = subprocess.run(["git", "ls-files", "*.md", "*.py", "*.json", "*.txt"],
                           cwd=str(ROOT), capture_output=True, text=True).stdout.split()
    assert files, "لا ملفّاتٍ مُتتبَّعة ⇒ فشلٌ مُغلَق (لا أُعلن سقفاً بلا مقام)"
    n, excluded, counted_files = _foreign_id_counts(files)
    assert n == FOREIGN_ID_DEBT_ON_CORPUS, (
        f"معدّلُ الإيجابيّات **خارج صناديق المراسلة** {n} ≠ المُعلَن {FOREIGN_ID_DEBT_ON_CORPUS} ⇒ "
        f"إن ارتفع: صيغةٌ تُوسّع الانكشافَ أو ملفٌّ جديد؛ وإن نزل: **كشفٌ فقدناه** (أخطرُ من الأول). "
        f"(والمُستثنى داخل `{FOREIGN_ID_EXCLUDED_PREFIX}`: {excluded} سطراً — مُعلَنٌ للتاريخ، "
        f"ولا يُراتَش: لا يُعاقَب مدقّقٌ على اقتباسِ التزام. المقيسُ: {counted_files} ملفّاً)")
    assert excluded >= FOREIGN_ID_DEBT_INSIDE_MAILBOX, (
        f"المُستثنى داخل الصندوق {excluded} < المُعلَن {FOREIGN_ID_DEBT_INSIDE_MAILBOX} ⇒ الكوربوسُ "
        f"تغيّر أو المقامُ يُقرأ خطأً (النقصانُ يُعلَن ولا يُبتلع)")

def test_a_foreign_commit_id_is_flagged():
    """٤٠ خانةً سِتّ عشريّة لا وجودَ لها + سياقُ إحالةٍ ⇒ إشارةٌ إلى خارجه.

    **والصيغُ التسعُ هنا مقيسةٌ لا مُتخيَّلة**: نسخةٌ ضيّقت السياقَ إلى كلمة `commit` وحدها كانت **تنجو**
    من `sha=<id>` و`commit hash <id>` (قاسها مقعدُ المعايير) ⇒ فالدقّةُ لا تُشترى بالقدرة.
    """
    m = _load()
    foreign = "f" * 39 + "a"
    for line in (f"commit = {foreign} هو مصدر البيانات",
                 f"الالتزام {foreign} مدموجٌ سابقاً",
                 f"sha={foreign} هو مصدر البيانات",
                 f"the commit hash {foreign} في السجلّ",
                 f"revision hash {foreign} مدموج"):
        hits = m.scan_foreign_ids([(3, line)], exists=lambda t: False)
        assert hits == [(3, "foreign_commit_id")], (line, hits)


def test_a_file_hash_stamp_is_not_a_commit_id():
    """**R55-3 (الدليلُ الحيّ)**: بصمةُ حزمة الأسئلة (`spec_sha`) و`sha256` هاشُ **ملفٍّ** لا كائنَ git.

    قبل الإصلاح: كلمةُ `sha` وحدها في السياق كانت تجعلهما «معرّفَ التزامٍ غريباً» ⇒ **الخطّافُ أوقف التزامَ
    مراجعة المدقّق** على سطرين يقتبسان البصمة، بلا أيّ معرّفِ التزام. وقياسُ الاثنين معاً = الحدّ الفاصل.
    """
    m = _load()
    stamp = "4facf540abd4"                      # بصمةُ ملفّ الأسئلة (هاشُ محتوى، لا كائنَ git)
    wide = "b" * 40
    for line in (f"`spec_sha` = {stamp} محسوبةٌ من ملفّ الأسئلة",
                 f"sha256={wide} للنسخة المُنزَّلة",
                 f"content_sha: {wide} في المانيفست",
                 f"checksum={wide} للملفّ"):
        hits = m.scan_foreign_ids([(7, line)], exists=lambda t: False)
        assert hits == [], (line, hits)
    # **وحدُّ القاعدة**: `sha=<id>` بلا اسمِ حقلٍ صريح ⇒ **يُكتشَف** (لا استثناءَ بكلمةٍ عامّة، ولا نافذةَ
    # مسافة: البوّابةُ تشترط `sha` **كلمةً** ⇒ اسمُ حقل مثل `spec_sha` لا يعبرها أصلًا).
    hits = m.scan_foreign_ids([(8, f"sha={wide} مدموجٌ سابقاً")], exists=lambda t: False)
    assert hits == [(8, "foreign_commit_id")], ("الاستثناءُ صار أوسعَ من العلّة", hits)


def test_the_four_measured_forms_of_the_pack_stamp_are_not_blocked():
    """**R56-1 — الصيغُ الأربع المقيسة** (مراجعة المدقّق ٥٦) + **السطرُ الحقيقيّ الطويل** (نقدُ مقعد Spec).

    الأربعُ **مقتبسةٌ من أسطرٍ حقيقيّةٍ في هذا المستودع** (قِيست بـ`git grep` على البصمات)، وجامعُها أنّ
    كلمةَ الهاش تأتي **داخل** اسمِ حقل أو تفصلها عنه رموزٌ لا مسافة: صفُّ جدول · قوسان مربّعان · نثرٌ عربيّ.

    ⚠ **والحالةُ التي أسقطت إصلاحَ «النافذة»:** السطرُ الخامسُ **منسوخٌ حرفيًّا** من
    `handoff/sulaiman/20260922-013500-item4-plan-v22-…md:21` — فيه **٩٥ خانةً** بين `sha256` والبصمة، فكان
    إصلاحُ «كلمةِ هاشٍ في ±٦٠ خانةً» **يُبقيه محجوباً** (قاسه المقعدان). والبوّابةُ الجديدة
    تحلّه **بالصيغة لا بالمسافة** ⇒ فلا حدَّ لطولِ السطر.
    """
    m = _load()
    for line in ('  "aggregate_sha16": "100e10a506f08557",',                       # صيغةُ JSON
                 "sha256(slice_629p.pdf)[:16]    = 3e2d360a665c88aa   ← الكوربوس",  # نثرٌ إنجليزيّ مختصر
                 "| الأدلّة | (`eval-runs/20260924-4facf540abd4/`) · **بصماتٌ 16/16** | `shasum -a 256 -c SHA256SUMS` |",
                 'assert st.is_publishable({"spec_sha": "4facf540abd4"}, "4facf540abd4")',
                 # ★ منسوخٌ حرفيًّا من سطرٍ حقيقيّ في المستودع (٢٣٢ خانة) — شاهدُ الانحدار القديم:
                 "| **الهوية** | `sha256(file)[:16]` للمستندين | الالتقاط = **`data/local_sample/digital/app_statement.pdf`**"
                 " ⇒ `093e1b733689193f` · والكوربوس = `slice_629p/slice_629p.pdf` ⇒ **`3e2d360a665c88aa`**"
                 " ⇒ **مستندان مختلفان بهَشمة الملف** |"):
        hits = m.scan_foreign_ids([(9, line)], exists=lambda t: False)
        assert hits == [], (line, hits)


def test_the_arabic_tatweel_form_of_the_word_sha_is_seen():
    """**R57-3 (أ) — العمى الذي كان `\\b` يفتحه عند الكلمة لا عند المعرّف**: «الـsha <معرّف>» هي **لغةُ هذا
    المستودع نفسِه** (**١١ سطراً في ٤ ملفّات** خارجَ صناديق المراسلة — انظر `test_the_tatweel_form_coverage_is_measured_not_described`)،
    والكشيدةُ (`\\u0640`) والحرفُ العربيّ
    حرفا كلمةٍ عند `\\b` ⇒ كانت **لا تُكشَف** بعد إصلاح R56-1 (وكانت تُكشَف قبله). ولا يمسكها الراتشتُ
    لأنّ الكوربوس لا يحوي هذه الصيغة ⇒ فضياعُ الكشف كان يمرّ صامتاً. والضابطُ موجبٌ صريح.
    """
    m = _load()
    foreign = "f" * 39 + "b"
    for line in (f"الـsha {foreign} هو مصدر البيانات",
                 f"بالـsha {foreign} مدموجٌ سابقاً",
                 f"rev {foreign} مدموج"):
        assert m.scan_foreign_ids([(4, line)], exists=lambda t: False) == [(4, "foreign_commit_id")], line


def test_the_tatweel_form_coverage_is_measured_not_described():
    """**S-3 (قاسه مقعد المعايير)**: «٢٧ سطراً في **١٦** ملفّاً» كان رقماً مكتوباً بيدٍ في §٢٦ وترويسة
    الأداة، وقياسُه **١١** ملفّاً ⇒ وثيقةٌ معياريّةٌ يحمل رقمُها ما يناقض مِقياسَه (صنفُ §٢٨ P-10). وصُحِّح
    الرقمُ **وقيس**: الأسطرُ والملفّاتُ تُقرأ من الشجرة المُتتبَّعة وتُقابَل بثابتين — راتشتٌ في الاتجاهين.
    (ولا يُكتب الحدُّ هنا بكشيدةٍ حرفيّةٍ عن قصد: كُتُبَ هجاؤُه `\\u0640` لئلّا يزيد الضابطُ نفسُه الرقمَ الذي يقيس.)
    """
    m = _load()          # لا شيءَ من الفاحص يُستعمل هنا: الشاهدُ هو **الصيغةُ كما تكتبها الوثائق**.
    files = subprocess.run(["git", "ls-files"], cwd=str(ROOT), capture_output=True, text=True).stdout.split()
    assert files, "لا ملفّاتٍ مُتتبَّعة ⇒ فشلٌ مُغلَق"
    lines, hit_files, counted, excluded = _tatweel_form_counts(files)
    assert excluded > 0, (
        f"الاستثناءُ بلا مقام: لا ملفَّ تحت `{TATWEEL_FORM_EXCLUDED_PREFIX}` في الشجرة المُتتبَّعة ⇒ "
        f"الاستثناءُ صار أعمى — وهذا **فشلٌ مُغلَق** لا اجتياز")
    assert (lines, hit_files) == (TATWEEL_FORM_LINES, TATWEEL_FORM_FILES), (
        f"صيغةُ الكشيدة: {lines} سطراً في {hit_files} ملفّاً ≠ المُعلَن "
        f"({TATWEEL_FORM_LINES} سطراً · {TATWEEL_FORM_FILES} ملفّاً) · **المقام:** {counted} ملفّاً "
        f"مُتتبَّعاً بلا `{TATWEEL_FORM_EXCLUDED_PREFIX}` (مُستثنى {excluded}) · **القاعدة:** "
        f"{'حسّاسةٌ للحالة' if TATWEEL_FORM_CASE_SENSITIVE else 'قاعدةُ الماسح بلا حسّاس'} ⇒ إن ارتفع: "
        f"صيغةٌ أو ملفٌّ جديد (حدِّث الثابتَ والوثيقةَ معاً)؛ وإن نزل: **كشفٌ فقدناه**")
    assert m  # الفاحصُ مُحمَّلٌ (لا يُقاس الرقمُ على أداةٍ لم تُقرأ)


def test_the_tatweel_counter_cannot_read_the_mailbox_and_still_sees_the_product(tmp_path):
    """**R58-1 — المقامُ يُقاس بضابطٍ اصطناعيٍّ في الاتجاهين:**

    ‹١› صيغةٌ داخل صندوق المراسلة **لا تُحرّك الرقم** (نصُّ المدقّق ليس مُدخَلاً إلى راتشتٍ يملكه المنفّذ).
    ‹٢› صيغةٌ **في نثر المنتج** تُحسَب (الاستثناءُ ليس عَمىً — لو كان، لباع الرقمُ قدرتَه بلا إعلان).
    """
    form = "\u0640" + "sha"          # تُبنى ولا تُكتب: لا كشيدةَ حرفيّةً في هذا الملفّ (وإلّا زاد الرقمُ نفسُه)
    (tmp_path / "handoff").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "handoff" / "review.md").write_text(f"اقتباسٌ من {form} في صندوق المدقّق\n", encoding="utf-8")
    (tmp_path / "docs" / "guide.md").write_text(f"وفي نثر المنتج {form} أيضاً\n", encoding="utf-8")
    (tmp_path / "docs" / "clean.md").write_text("بلا صيغةٍ هنا\n", encoding="utf-8")
    names = ["handoff/review.md", "docs/guide.md", "docs/clean.md"]
    assert _tatweel_form_counts(names, root=tmp_path) == (1, 1, 2, 1), (
        "أحدُ ثلاثة: المقامُ غير مُعلَن · أو الصندوقُ حرّك الرقمَ · أو نثرُ المنتج لم يُحسَب")
    # **والفارقُ هو الاستثناءُ نفسُه** (لا صدفة): بإلغائه يصير الرقمُ اثنين ⇒ الضابطُ يقيس ما يقول.
    assert _tatweel_form_counts(names, root=tmp_path, excluded_prefix="") == (2, 2, 3, 0), (
        "الاستثناءُ لم يكن هو الفارق ⇒ الضابطُ لا يقيس ما يقول")


def test_the_verb_rev_parse_is_not_a_commit_reference():
    """**R57-3 (ب) — السطرُ الذي كُتب دَيناً وهو ليس منه**: سطرٌ أجازته `rev` في **`git rev-parse`** (أمرٌ لا
    معرّف) ومعرّفُه بصمةُ ملفّ ⇒ كان يُحسب «معرّفَ التزامٍ غريباً» فيدخل الـ٤٨. والحدُّ الجديد يُضيِّق
    `rev` بـ`-` ⇒ `rev-parse` لا تُجيز السطرَ، ويبقى `rev <hex>` مُكتشَفاً (الضابطُ الموجب أعلاه).

    (وهذا هو الاتّجاهُ الثاني المُعلَن في الراتشت: نزولُ العدد يقول «كشفٌ فقدناه» — وهنا كان **إيجاباً
    كاذباً** كُتب دَيناً، فيُنقل العددُ إلى ٤٧ **بقرارٍ مُعلَنٍ في الالتزام نفسه** لا بصمت.)
    """
    m = _load()
    fingerprint = "100e10a506f08557"                    # بصمةُ ملفّ (هاشُ محتوى، لا كائنَ git)
    for line in (f"`git rev-parse HEAD` يُقرأ عند الطلب · هويّةُ الحزمة {fingerprint}",
                 f"rev-parse --short origin/main  # {fingerprint}"):
        assert m.scan_foreign_ids([(12, line)], exists=lambda t: False) == [], line


def test_an_id_stuck_to_an_arabic_letter_is_still_seen():
    """**عمى اليونيكود في حدّ الكلمة** (قاسه مقعدُ المعايير): `\b` يعتبر الحرفَ العربيّ حرفَ كلمة، فمعرّفٌ
    **مُلاصقٌ** لحرفٍ عربيّ (بلا فراغ) كان **لا يُرى أصلًا** — وليس إيجاباً كاذباً بل **كشفٌ مفقود**، وهو
    أخطرُ في كاشفِ P-4. والحدُّ الآن نظرتا حرفٍ سِتّ عشريّ (`(?<![0-9a-fA-F])…(?![0-9a-fA-F])`) لا حدودُ كلمة.
    """
    m = _load()
    foreign = "f" * 39 + "e"
    assert m.scan_foreign_ids([(1, f"commit = {foreign}مدموج")], exists=lambda t: False) == [
        (1, "foreign_commit_id")], "معرّفٌ ملاصقٌ لحرفٍ عربيّ مرّ صامتاً"


def test_an_id_that_exists_in_the_repo_is_not_flagged():
    m = _load()
    real = "a" * 40
    assert m.scan_foreign_ids([(1, f"commit {real} مدموج")], exists=lambda t: True) == []


def test_a_long_number_is_not_a_commit_id():
    """**ضابطٌ سالب**: سلاسلُ الأرقام الطويلة (كسلسلة العائم الشهيرة) وأشباهُها ليست لا معرّفات (لا حرفَ سِتّ عشريّاً)."""
    m = _load()
    digits = "3" * 17          # تُبنى ولا تُكتب (القاعدة ١٢: تغييرُ القيمة لا إعفاءُ الموضع)
    for line in (f"القيمة {digits} مكتوبة", f"sha={digits} بلا حرف"):
        assert m.scan_foreign_ids([(1, line)], exists=lambda t: False) == [], line


def test_without_context_a_hex_token_is_not_flagged():
    """حدٌّ مُعلَن: يُشترَط سياقُ المعرّف — أقلُّ إيجابٍ كاذبٍ في نثرٍ عربيّ عاديّ."""
    m = _load()
    token = "b" * 40
    assert m.scan_foreign_ids([(1, f"عبارةٌ عابرةٌ فيها {token} بلا سياقٍ")], exists=lambda t: False) == []


def test_the_documented_foreign_ids_mode_exists_and_narrows(tmp_path, capsys):
    """**صنفٌ كشفه القياس لا المراجعة**: `--foreign-ids` كان مذكوراً في `docs/GATES.md` و`docs/ROADMAP.md`
    (وفي تلقينةٍ للمدقّق) **قبل أن يوجد** — مرّ عليه أمرٌ حقيقيٌّ فأعطى `unrecognized arguments`.

    والإصلاحُ **بناءٌ لا تحريرُ نصّ**: المدخلُ صار موجوداً، وهذا الضابطُ يقيس أنّه **يُضيَّق ولا يُخفي**:
    في الوضع العاديّ يُبلَّغ عن السِرِّ، وفي وضع P-4 **لا يُبلَّغ** عنه (وإلّا كان علماً يُطفئ طبقةً بصمت).
    """
    m = _load()
    m._is_shallow = lambda: False
    p = tmp_path / "mixed.txt"
    foreign = "f" * 39 + "d"
    p.write_text(f"ANTHROPIC_API_KEY={_fakes()['anthropic']}\ncommit = {foreign} مدموج\n", encoding="utf-8")
    assert m.main(["--text", str(p)]) == 1
    full = capsys.readouterr().out
    assert "anthropic" in full and "المعرّفات" in full, full
    assert m.main(["--text", str(p), "--foreign-ids"]) == 1
    only_ids = capsys.readouterr().out
    assert "المعرّفات" in only_ids and "anthropic" not in only_ids, (
        f"وضعُ P-4 لم يُضيِّق (ظهر صنفُ سِرٍّ): {only_ids}")


def test_the_foreign_id_report_never_prints_the_id(tmp_path, capsys):
    """**حدُّ المدقّق**: يُطبع الملفُّ والسطرُ فقط — لأنّ سجلّاتِ CI في مستودعٍ عامٍّ عامّةٌ أيضاً."""
    m = _load()
    foreign = "c" * 40
    p = tmp_path / "leak.md"
    p.write_text(f"التزام sha={foreign}\n", encoding="utf-8")
    m._is_shallow = lambda: False                      # نفحص المنطقَ لا البيئة
    rc = m.main(["--text", str(p)])
    out = capsys.readouterr().out
    assert rc == 1, f"معرّفٌ غريب ⇒ 1 (صار {rc})"
    assert foreign not in out, "طُبع المعرّف! (حدُّ المدقّق: السطرُ فقط)"
    assert "foreign_commit_id" in out


def test_the_tatweel_counter_uses_the_scanner_case_rule():
    """**P3-9 (مقعدُ البنية):** «قاعدةُ الماسح `(?i)`» كانت **قولاً** في ثابتٍ مكتوب ⇒ لا ثابتان لمعنى واحد.

    فالقاعدةُ الآن مُشتقّةٌ من `ID_CONTEXT.flags`، ويُقاس **أثرُها**: الحرفان الكبيرُ والصغير يسلكان سبيلاً
    واحداً في العدّاد، وهي سبيلُ الماسح نفسِه.
    """
    m = _load()
    scanner_i = bool(m.ID_CONTEXT.flags & re.IGNORECASE)
    rx = re.compile("\u0640sha", 0 if TATWEEL_FORM_CASE_SENSITIVE else re.IGNORECASE)
    assert bool(rx.flags & re.IGNORECASE) == scanner_i, "قاعدةُ العدّاد تخالف قاعدةَ الماسح (ثابتان لمعنى)"
    assert bool(rx.search("الـ\u0640SHA")) == bool(rx.search("الـ\u0640sha")) == scanner_i, (
        "أثرُ القاعدة غيرُ مرئيّ على حالة الحروف ⇒ الاشتقاقُ ادّعاءٌ لا قياس")


def _undated_snapshot_pairs(text: str) -> list[str]:
    """يُعيد كلَّ زوجٍ **يشمل الشجرةَ كلَّها** (`N·M`) في فقرةٍ بلا وسمِ «مؤرَّخ» وبلا تاريخ ⇒ عطبٌ مُسمًّى.

    **القاعدة (§٢٣ · وحكمُ مراجعة ٥٩):** كلُّ رقمٍ مع شجرته. وقياسُ الصناديق يتغيّر مع كلّ مراجعةٍ تهبط
    (فيه رقمٌ يُقتبس) ⇒ يُقرأ **تاريخًا مؤرَّخًا** لا حكمًا: يلزمه وسمُ التأريخ **وتاريخٌ** في الفقرة نفسِها،
    وإلّا فهو رقمٌ حيٌّ بلا مقياسٍ يحرسه — وهو الصنفُ الذي كسر الـCI ثلاثَ مرّات.
    """
    bad: list[str] = []
    for para in text.split("\n\n"):
        if "مؤرَّخ" in para and re.search(r"\d{4}-\d{2}-\d{2}", para):
            continue
        bad += [m.group(0) for m in re.finditer(r"\d+·\d+\s*(?:حسّاساً|بلا حسّاس)", para)]
    return bad


def test_the_three_prose_sites_are_compared_to_the_measurement():
    """**الرقمُ يُقاس في مواضعه الثلاثة لا في موضعٍ واحد (P2-4 · مقعدُ المواصفة):** «١١ سطراً في ٤ ملفّات»
    مكتوبٌ في **§٥ من البروتوكول** و**ترويسة الماسح** — ويُقابَلان بالمقياس على **المقام المُعلَن**:
    «الشجرةُ المتتبَّعة **بلا `handoff/`**».

    **والرقمان 27·11 و36·18 (الشجرةُ كلُّها) صارا تاريخًا مؤرَّخًا لا يُقابَلان (R59-1 · حاجبُ مراجعة ٥٩):**
    المقارنةُ كانت تشمل `handoff/claude/` ⇒ **نصُّ المدقّق مُدخَلٌ إلى راتشتٍ يملكه المنفّذ**: قِيس أنّ
    مراجعةً واحدةً تقتبس الصيغة (و٥٧ تقتبسها في ٤ أسطر) تُحمرّ الـCI — وهو الصنفُ نفسُه ثلاثَ مرّات.
    فالضابطُ الآن يُلزم: المقارَنُ = المقامُ المُعلَن وحدَه، وتلك الأرقامُ **بوسمِ تأريخٍ وتاريخٍ**.
    (و«٣١ سطراً في ١٢ ملفّاً» في §٢٦ **إعادةُ إنتاجٍ مؤرَّخة** لإسقاطٍ حصل قبل الإصلاح — تُقرأ كتاريخٍ
    لا كقياسِ اليوم، فلا تُقابَل بمقياسٍ لا يعود.)
    """
    files = subprocess.run(["git", "ls-files", "*.md", "*.py", "*.json", "*.txt"],
                           cwd=str(ROOT), capture_output=True, text=True).stdout.split()
    lines_ex, files_ex, _, excluded_files = _tatweel_form_counts(files)
    assert (lines_ex, files_ex) == (TATWEEL_FORM_LINES, TATWEEL_FORM_FILES), "الثابتان ≠ المقيس (المقامُ بلا handoff/)"
    assert excluded_files > 0, "المُستثنى صفرٌ ⇒ المقامُ لم يُقَس على ما يقول (ولا استثناءَ صامت)"
    pat = r"(\d+)\s*سطراً في\s*(\d+)\s*ملفّ"
    for doc in ("docs/handoff-protocol.md", "tools/secret_scan.py"):
        text = (ROOT / doc).read_text(encoding="utf-8")
        assert _pair_at(text, pat) == (TATWEEL_FORM_LINES, TATWEEL_FORM_FILES), (
            f"{doc}: «… سطراً في … ملفّات» المنطوق يخالف المقيس "
            f"{(TATWEEL_FORM_LINES, TATWEEL_FORM_FILES)} ⇒ نصٌّ مُتقادم")
    # **وما يشمل الصناديق لا يُقابَل — بل يُلزَم تاريخًا** (R59-1): وحكمُه دالّةٌ تُقاس في الاتجاهين.
    proto = (ROOT / "docs" / "handoff-protocol.md").read_text(encoding="utf-8")
    assert _undated_snapshot_pairs(proto) == [], (
        f"أرقامٌ تشمل صناديق المراسلة بلا وسمِ تأريخٍ وتاريخ: {_undated_snapshot_pairs(proto)} ⇒ "
        "يُكتب كلُّ رقمٍ مع شجرته (R59-1)، ولا يُدخَل نصُّ المدقّق في راتشتٍ يملكه المنفّذ")
    assert _pair_at(proto, r"(\d+)·(\d+)\s*حسّاساً") is not None and \
        _pair_at(proto, r"(\d+)·(\d+)\s*بلا حسّاس") is not None, \
        "القياسُ المؤرَّخ يُذكَر بتاريخه (§٢٣: رقمٌ بلا شجرته = رقمٌ بلا مصدر)"
    # **والدالّةُ تقيس ما تقول (لا تمرّ فراغًا):** زوجٌ بلا تاريخٍ ولا وسم ⇒ يُكشَف · ومعهما ⇒ يمرّ.
    assert _undated_snapshot_pairs("كلُّ الشجرة 27·11 حسّاساً و36·18 بلا حسّاس.") == \
        ["27·11 حسّاساً", "36·18 بلا حسّاس"], "الضابطُ لا يكشف الرقمَ الحيّ ⇒ شهادةٌ بلا عضّ"
    assert _undated_snapshot_pairs(
        "**قياسٌ مؤرَّخ** (2026-09-25 · بلا `handoff/`): 27·11 حسّاساً و36·18 بلا حسّاس.") == [], \
        "الزوجُ المؤرَّخُ بتاريخه وسمِه يجب أن يمرّ — وإلّا فالضابطُ يمنع التوثيق"

