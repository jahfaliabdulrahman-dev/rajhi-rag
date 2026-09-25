"""**ماسحُ الأسرار: يرى أصنافَ هذا المشروع، ولا يطبع قيمةً، ويفشل مُغلَقًا.**

وُلد من مراجعة ٥٣ (مدقّقٌ مستقلّ بمفاتيحَ مصطنعة): النمطُ الواحد في `pre-commit` كان يمرّر
`sk-or-v1-…` و`sk-ant-…` (صنفُ الرمز الذي تسرّب فعلًا) و`sk-proj-…` و`github_pat_…` — لأنّه توقّف عند
أوّل شَرطة. ⇒ الفحصُ انتقل إلى أداةٍ ذاتِ نمطٍ لكلّ صنف، وهذه ضوابطُها.

⚠ **ولا يُكتب سِرٌّ في هذا الملفّ حرفيًّا**: القيمُ تُبنى بالضَمّ وقتَ التشغيل ⇒ فلا الخطّافُ ولا أيُّ
ماسحٍ يرى سِرًّا حقيقيًّا في هذه الضوابط. (والمقاطعُ وحدها **يجب ألّا تُطابَق** — وهذا ضابطٌ بنفسه.)
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("secret_scan", ROOT / "tools" / "secret_scan.py")
    assert spec is not None and spec.loader is not None, "تعذّر تحميلُ الماسح ⇒ لا قياس"
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


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

#: **دَينٌ مُعلَنٌ ومؤرَّخ**: عددُ الأسطر على الكوربوس المُتتبَّع التي تُشبه إحالةً خارجية ولا وجودَ لها في
#: رسم المستودع (أكثرُها بصماتُ محتوى ومراجعُ من جولاتٍ سابقة). القياسُ عند اعتماد هذا السقف: **٦٣ من ٣٥١ ملفّاً**
#: (والكودُ الأسبق: ٨٥). **والسقفُ راتشت**: صعودُه يحتاج قراراً مُعلناً، لا يُبتلع بتوسيعٍ صامت.
#: **ورُفع إلى ٦٤ ثم رُجع إلى ٥٠ يومَ 2026-09-25 — والثاني قرارٌ مُعلَن أيضاً**: بعد R56-1 (نافذةُ كلمةِ
#: الهاش) نزل المعدّلُ ٦٤ ⇒ **٥٠**، فأُعيد السقفُ إلى المقيس (راتشتٌ يعمل في الاتّجاهين: يمنع النموّ ولا
#: يترك هامشاً وهميّاً). والباقي **دَينٌ حقيقيٌّ لا ضجيج**: أسطرُ ترويساتِ رسائل قديمة (`commit: <40hex>`)
#: تُشير إلى التزاماتٍ **ليست في هذا المستودع** (ما قبل التنقية) — وهو بعينه الصنفُ الذي يطارده P-4.
FOREIGN_ID_DEBT_ON_CORPUS = 50


def test_the_corpus_positive_rate_is_declared_and_capped():
    """**الصدقُ في المعدّل**: أداةٌ تُعلن نظافتَها على الكوربوس بينما تُنتج عشراتِ الإيجابيّات = ادّعاء.

    ولا تُصلَح آليّاً (تُراجَع بشرٍ): فالقياسُ هنا **سقفٌ مُعلَن** يمنع النموّ — أي أنّ أيَّ توسيعٍ للسياق
    أو صيغةٍ جديدة تُضاعف المعدّل **يُكشَف فوراً** بدل أن يُبتلع.
    """
    m = _load()
    files = subprocess.run(["git", "ls-files", "*.md", "*.py", "*.json", "*.txt"],
                           cwd=str(ROOT), capture_output=True, text=True).stdout.split()
    assert files, "لا ملفّاتٍ مُتتبَّعة ⇒ فشلٌ مُغلَق (لا أُعلن سقفاً بلا مقام)"
    n = 0
    for f in files:
        try:
            lines = (ROOT / f).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        n += sum(1 for i, ln in enumerate(lines, 1) if m.scan_foreign_ids([(i, ln)]))
    assert n <= FOREIGN_ID_DEBT_ON_CORPUS, (
        f"معدّلُ الإيجابيّات ارتفع إلى {n} (السقفُ المُعلَن {FOREIGN_ID_DEBT_ON_CORPUS}) ⇒ صيغةٌ تُوسّع "
        f"الانكشافَ أو ملفٌّ جديد؛ قِسْه ثم ارفع السقفَ **بقرارٍ مُعلَن** أو أصلِح الصيغة")

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
    # **وحدُّ الاستثناء**: `sha=<id>` بلا اسمِ حقلٍ صريح ⇒ **يُكتشَف** (لا استثناءَ بكلمةٍ عامّة).
    # (وكان هذا السطر يستعمل «بصمةُ المحتوى» **زينةً**؛ وصارت «بصمة» جزءاً من معجم الاستثناء في R56-1
    #  ⇒ نُقل الضابطُ إلى سطرٍ بلا أيّ كلمةِ هاشٍ — **تغييرُ الحالة لا إضعافُ القاعدة**، والحدُّ الجديد
    #  مُثبَّتٌ في `test_the_declared_limit_of_the_hash_window`.)
    hits = m.scan_foreign_ids([(8, f"sha={wide} مدموجٌ سابقاً")], exists=lambda t: False)
    assert hits == [(8, "foreign_commit_id")], ("الاستثناءُ صار أوسعَ من العلّة", hits)


def test_the_four_measured_forms_of_the_pack_stamp_are_not_blocked():
    """**R56-1 — الصيغُ الأربع المقيسة** (مراجعة المدقّق ٥٦): كانت كلُّها تُحجب وهي بصماتُ محتوى.

    الأربعُ **مقتبسةٌ من أسطرٍ حقيقيّةٍ في هذا المستودع** (قِيست بـ`git grep` على البصمات)، وجامعُها أنّ
    كلمةَ الهاش تأتي **بعد** المعرّف أو تفصلها عنه رموزٌ: صفُّ جدول · قوسان مربّعان · نثرٌ عربيّ · مسارُ أرشيف.
    """
    m = _load()
    for line in ('  "aggregate_sha16": "100e10a506f08557",',                       # صيغةُ JSON
                 "sha256(slice_629p.pdf)[:16]    = 3e2d360a665c88aa   ← الكوربوس",  # نثرٌ إنجليزيّ
                 "| الأدلّة | (`eval-runs/20260924-4facf540abd4/`) · **بصماتٌ 16/16** | `shasum -a 256 -c SHA256SUMS` |",
                 'assert st.is_publishable({"spec_sha": "4facf540abd4"}, "4facf540abd4")'):
        hits = m.scan_foreign_ids([(9, line)], exists=lambda t: False)
        assert hits == [], (line, hits)


def test_the_two_reference_forms_stay_flagged():
    """**الاتّجاهُ المُعاكس** (درسُ R55-3/R55-4): `sha=<id>` و`commit hash <id>` بلا اسمِ حقلٍ صريح.

    لو أصبحت `sha` المجرّدة أو `hash` جزءاً من معجم الاستثناء لعادت العلّةُ القديمة: إحالةٌ صريحة تمرّ.
    """
    m = _load()
    foreign = "d" * 39 + "b"
    for line in (f"sha={foreign} هو مصدر البيانات",
                 f"the commit hash {foreign} في السجلّ",
                 f"commit = {foreign} هو مصدر البيانات"):
        hits = m.scan_foreign_ids([(4, line)], exists=lambda t: False)
        assert hits == [(4, "foreign_commit_id")], (line, hits)


def test_the_declared_limit_of_the_hash_window():
    """**حدٌّ مُعلَن ومُقاس — لا يُدّعى أنّه غيرُ موجود:** معرّفُ التزامٍ حقيقيٌّ يوصَف بكلمةِ هاشٍ في النافذة.

    «بصمةُ الالتزام <id>» يُغفَل لأنّ «بصمة» كلمةُ هاشٍ. وهذه مُقايَضةٌ مقصودةٌ ومُعلَنة: الطبقةُ الأخرى
    (`publish_guard` والمراجعةُ البشريّة) تمسك ما تُغفله هذه النافذة — و**الحجبُ الصامتُ للنثر المشروع
    كان أسوأَ فعلًا** (الدليل: سقفُ الكوربوس رُفع مرّتين في يومٍ واحد قبل هذا الإصلاح).
    """
    m = _load()
    foreign = "e" * 39 + "c"
    assert m.scan_foreign_ids([(5, f"بصمة الالتزام {foreign}")], exists=lambda t: False) == []
    # ولا يتّسع الحدُّ أكثر: النافذةُ محدودةٌ ⇒ إشارةٌ بعيدةٌ عن كلمةِ الهاش تبقى مُكتشَفة
    far = f"commit = {foreign} " + "ح" * (m.HASH_WINDOW * 2) + " بصمة"
    assert m.scan_foreign_ids([(6, far)], exists=lambda t: False) == [(6, "foreign_commit_id")]


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

