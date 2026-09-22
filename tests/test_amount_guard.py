"""حارسُ المبالغ — اختبارُ القاعدة، واختبارُ **اشتقاقها**، واختبارُ سقوطها.

القاعدةُ العاشرة: حارسٌ بقائمةِ منعٍ مُشتقّة، **صحّتُه صحّةُ اشتقاقِها لا صحّةُ منطقِه**.

**والدروسُ التي دُمِّرت هنا مرّات، وكلُّ درسٍ مُجرَّبُ السقوط لا مُدَّعى:**
١) المدى = ≥٤ خاناتٍ صحيحة **+ كسرٌ عشريّ مقروء** (الاستدارةُ صفةُ المبلغ لا دليلُ صناعيّته).
٢) **لا يُعفى موضع، يُعفى قيمة (القاعدة ١٦).**
٣) **الإهمالُ واقعٌ يُقاس (القاعدة ١٦)** — والمفتاحُ والخريطةُ والمانيفستُ ثلاثةٌ لا واحد.
٤) **المخرَجُ الآليُّ لا يُقصّ (القاعدة ١٥)** — والقيمةُ لا تُطبع أصلاً.
٥) **القيمةُ تُقرأ بالمُحلِّل الموروث (مراجعة ٣٨):** البصمةُ **للمقدار** (فالإشارةُ ليست هويّة)،
   والمدى يراه **بفاصلةٍ عتيقة** (`N,dd`) كما يراه بنقطةٍ حديثة ⇒ المقيسُ **٤٢ لا ٣٩**.
٦) **السقاطةُ بدل «أحمرَ دائماً» (مراجعة ٣٨):** بوابةٌ تسقط على دَينٍ مُعلَنٍ لا تمنع شيئاً
   ⇒ الإسقاطُ عند **الزيادة** وحدها، والدَينُ يبقى مُعلَنًا حتى تُعاد كتابةُ قِيَمه.
٧) **أربعُ أبوابٍ من مراجعة ٣٩ مُغلَقةٌ باختبار:** المصدرُ من `DATA_ROOT` (ومدخلٌ صفريّ يسقط)،
   والمدى غيرُ المحلول يسقط مُغلَقاً، والعتبةُ لا يضعها الدافع (ولا تبديلَ عند العدّ نفسِه)،
   والخطّافُ لا يحجب على أداةٍ تطويريّة غائبة (فذلك يخلق حافزَ `--no-verify` ويُسقط الأمنَ معه).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("amount_guard", ROOT / "tools" / "amount_guard.py")
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)

FAKE = "543210.99"          # قيمةٌ وهميّةٌ **خارج الكوربوس** (لا تُسرّب مبلغاً حقيقيًّا)
FAKE_AR = "٥٤٣٢١٠٫٩٩"


def _key(tmp_path, monkeypatch):
    """مفتاحٌ وهميّ للاختبار: البصمةُ لا تُجرَد بغير المفتاح، والاختبارُ لا يحتاج المفتاحَ الحقيقيّ."""
    kf = tmp_path / "k"
    kf.write_text("test-key-not-the-real-one", encoding="utf-8")
    monkeypatch.setattr(ag, "KEY_FILE", kf)
    monkeypatch.delenv(ag.KEY_ENV, raising=False)


def test_normalizes_arabic_and_persian_digits_alike(tmp_path, monkeypatch):
    _key(tmp_path, monkeypatch)
    assert ag.normalize(FAKE_AR) == FAKE
    assert ag.normalize("۱٬۲۳۴٫۵۶") == "1234.56"
    assert ag.normalize("543,210.99") == FAKE


def test_amount_shaped_requires_four_integer_digits():
    assert ag.is_amount_shaped("1234.00") and ag.is_amount_shaped(FAKE_AR)
    assert not ag.is_amount_shaped("300.00")
    assert not ag.is_amount_shaped("0.979")
    # **عطبٌ أمسكتُه قبل أن يخرج:** لو صار «الشكل» قراءةً بالمُحلِّل لصار كلُّ معرّفٍ يحمل ٤
    # أرقام مبلغاً (المُحلِّلُ يحذف غيرَ الأرقام) ⇒ المصدرُ انتفخ من ١١٬٠٢٩ إلى ٢٧٬٣٠٩.
    assert not ag.is_amount_shaped("P2026x")


def test_scope_is_length_plus_a_decimal_never_the_roundness():
    """**(تصحيحُ مراجعة ٣٦)** كان المُصفّي يستثني الكسرَ الصفريّ ⇒ ٢٤٦ مبلغاً مصدريًّا خارج الحماية.

    **و(تصحيحُ مراجعة ٣٨)** كان المدى يرى نقطةً حديثةً وحدَها ⇒ الفاصلةُ العتيقةُ `N,dd` تمرّ:
    صار الفاصلان يُقرآن بالمُحلِّل الموروث، والقيمةُ واحدة.
    """
    assert ag.is_significant("7777.00") and ag.is_significant("7777.0") and ag.is_significant("-7777.00")
    assert ag.is_significant("7777,00"), "الفاصلةُ العتيقةُ مبلغٌ في هذا الكوربوس (`300,00` = 300.00)"
    assert ag.is_significant("٧٧٧٧,٠٠")
    assert not ag.is_significant("7777")            # بلا كسر: يتصادم مع تواريخ وعدّادات
    assert not ag.is_significant("1,234")          # ثلاثُ خاناتٍ بعد الفاصلة = فاصلُ آلافٍ لا كسر
    assert not ag.is_significant("450.00")         # قصيرٌ: يتصادم بطبعِه


def test_canonical_collapses_writing_forms_and_ignores_the_sign():
    """**الشكلُ لا يهمّ في البصمة** (`7777.0` ≡ `7,777.00` ≡ `٧٧٧٧٫٠٠`) **والإشارةُ ليست هويّة**."""
    assert ag.canonical("7777.0") == ag.canonical("7,777.00") == ag.canonical("٧٧٧٧٫٠٠") == "7777.00"
    assert ag.canonical("-7777.00") == ag.canonical("7777.00"), "المقدارُ لا الإشارة (مراجعة ٣٨)"
    assert ag.canonical("7777,00") == "7777.00"


def test_no_location_is_exempt(tmp_path, monkeypatch):
    """**الدرسُ الثاني (القاعدة ١٦):** قناةُ `tests/` مُغلقة — والسمُّ يُشتقّ من المصدر لا يُكتب هنا.

    كان `FIXTURE_PREFIXES = ("tests/", "src/")` إعفاءً بالمسار ⇒ مرّ حقنُ مبلغين حقيقيين.
    **والفرقُ بين سطحِ صناعةٍ وقناةِ تسريبٍ ليس في المجلد بل في القيمة** — وهذا يقيسه على السطحين.
    """
    _key(tmp_path, monkeypatch)
    deny = {ag.fingerprint(FAKE)}
    for surface in ("tests/SECURITY_PROBE.py", "docs/SECURITY_PROBE.md"):
        p = ROOT / surface
        backup = p.read_text(encoding="utf-8") if p.exists() else None
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"الرصيد: {FAKE}\n", encoding="utf-8")
            assert ag.counts_by_file(deny, [surface]) == {surface: 1}, \
                f"مبلغٌ حقيقيٌّ في `{surface}` لم يُسقط الحارس ⇒ إعفاءٌ بالمسار عاد (القاعدة ١٦)"
        finally:
            if backup is None:
                p.unlink(missing_ok=True)
            else:
                p.write_text(backup, encoding="utf-8")


def test_the_rule_falls_on_a_value_it_was_built_for(tmp_path, monkeypatch):
    """**برهانُ السقوط بنواة الفحص نفسها** (بقيمةٍ وهميّة، فلا تسريبَ في الاختبار)."""
    _key(tmp_path, monkeypatch)
    deny = {ag.fingerprint(FAKE)}
    assert ag.find_in_text("الرصيد 543210.99", deny)
    assert ag.find_in_text(f"الرصيد {FAKE_AR}", deny)                       # الأبجديةُ لا تُنجيه
    assert ag.find_in_text("الرصيد 543210,99", deny), "الفاصلةُ العتيقة (مراجعة ٣٨)"
    assert ag.find_in_text("الرصيد -543210.99", deny), "الإشارةُ المقلوبة (مراجعة ٣٨)"
    assert not ag.find_in_text("قيمةٌ صناعية 300.00", deny)
    assert not ag.find_in_text("عدّادٌ 1234567", deny), "عددٌ صحيحٌ بلا كسر ليس مبلغاً"


def test_the_fingerprint_is_keyed_and_the_key_is_required(tmp_path, monkeypatch):
    """**الجردُ يحتاج المفتاح:** ٢٥٦ بتاً لا يُجرَد بمعرفة فضاءِ المبلغ وحده ⇒ وبلا مفتاح: فشلٌ مُغلَق."""
    _key(tmp_path, monkeypatch)
    keyed = ag.fingerprint(FAKE)
    public = hashlib.sha256(b"rajhi-rag/amount-guard/v1" + FAKE.encode()).hexdigest()[:32]
    assert keyed != public
    monkeypatch.setattr(ag, "KEY_FILE", tmp_path / "missing")
    monkeypatch.delenv(ag.KEY_ENV, raising=False)
    try:
        ag.load_key()
        raise AssertionError("بلا مفتاح يجب أن يفشل الحارسُ مُغلَقاً لا صامتاً")
    except SystemExit:
        pass


@pytest.mark.skipif(not (ag.KEY_FILE.exists() and ag.MANIFEST.exists()),
                    reason="لا مفتاحَ/مانيفست على سطحٍ عامّ (لا يُنشران بالتصميم)")
def test_ignore_is_a_measured_fact_not_a_claim():
    """**الدرسُ الثالث (القاعدة ١٦):** «مُهمَل» تُقاس بـ`git` — والمخفيُّ ثلاثةٌ لا واحداً.

    (مراجعة ٣٨: خريطةُ التطهير كانت في `SCAN_SKIP` ولا يفحصها `tracking_audit` ولا يمنعها
    حارسُ النشر ⇒ `git add -f` كان يمرّ من الثلاثة، وهي خريطةٌ تربط المُقنَّعَ بالحقيقيّ.)
    """
    assert ag.tracking_audit() == [], f"المفتاحُ/المانيفستُ/الخريطة: {ag.tracking_audit()}"
    for path in (ag.KEY_FILE, ag.MANIFEST, ag.REDACTION_MAP):
        rel = str(path.relative_to(ag.ROOT))
        assert subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel],
                              cwd=str(ROOT), capture_output=True).returncode != 0, f"{rel} مُتتبَّع ⛔"
        assert subprocess.run(["git", "check-ignore", "-q", "--", rel],
                              cwd=str(ROOT), capture_output=True).returncode == 0, f"{rel} غيرُ مُهمَل ⛔"


def test_the_manifest_is_never_published():
    """**لا يُنشر ما يمكن مهاجمتُه:** المانيفستُ وخريطةُ التطهير يسكنان `data/` المُهمَل."""
    for path in (ag.MANIFEST, ag.REDACTION_MAP):
        rel = str(path.relative_to(ag.ROOT)).replace("\\", "/")
        assert rel.startswith("data/"), f"{rel} خارج data/ المُهمَل"
    assert not (ROOT / "docs" / "security" / "amount-denylist.json").exists(), \
        "نسخةٌ منشورةٌ من البصمات ⇒ تُجرَد بمن يملك المفتاح ⇒ احتفظ بها داخل data/"


def test_json_output_is_never_truncated():
    """**الدرسُ الرابع (القاعدة ١٥):** العددُ المعلن = طولُ القائمة، دائماً — **والقيمةُ لا تُطبع**."""
    r = subprocess.run([sys.executable, "tools/amount_guard.py", "--json"],
                       cwd=str(ROOT), capture_output=True, text=True)
    if not r.stdout.strip().startswith("{"):
        pytest.skip("لا مانيفستَ (سطحٌ عامّ) ⇒ الفحصُ غيرُ قابلٍ للإنفاذ هنا")
    payload = json.loads(r.stdout)
    assert payload["count"] == len(payload["files"]), "المخرَجُ الآليُّ مقصوصٌ ⇒ نقضُ القاعدة ١٥"
    assert payload["total"] == sum(payload["files"].values())
    assert all(isinstance(v, int) for v in payload["files"].values()), \
        "المخرَجُ الآليُّ يحمل أعداداً لا قِيَماً (لا مبلغَ في مخرَجٍ يُسجَّل)"


def test_the_ratchet_blocks_an_increase_and_pardons_the_declared_debt():
    """**السقاطة (مراجعة ٣٨):** تسقط عند زيادةٍ أو ملفٍّ جديد، وتخضرّ على الدَين المُعلَن.

    (بوابةٌ تسقط على دَينٍ قائمٍ لا تمنع شيئاً ⇒ يُتجاوزها `--no-verify`، وهو ما حدث فعلًا.)
    """
    base = {"tests/a.py": {"count": 2, "commitment": "aa"}, "src/b.py": {"count": 1}}
    assert ag.ratchet_violations({"tests/a.py": {"count": 2, "commitment": "aa"}}, base, "x") == []
    assert ag.ratchet_violations({"tests/a.py": {"count": 1, "commitment": "bb"}}, base, "x") == [], \
        "نقصانٌ مسموح (ولو تبدّلت البصمة: هذا تصحيحٌ لا تبديل)"
    assert len(ag.ratchet_violations({"tests/a.py": {"count": 3, "commitment": "aa"}}, base, "x")) == 1
    assert len(ag.ratchet_violations({"tests/c.py": {"count": 1}}, base, "x")) == 1              # ملفٌّ جديد
    assert len(ag.ratchet_violations({"tests/a.py": {"count": 2, "commitment": "bb"}}, base, "x")) == 1, \
        "**تبديلُ قيمةٍ بأخرى عند العدّ نفسِه (ثغرةُ ٣٩ رقم ٣ج)** ⇒ ما لا يراه عدّادٌ يقارن الأعدادَ وحدها"


def test_without_a_manifest_the_guard_fails_closed_unless_ci_is_declared(tmp_path, monkeypatch, capsys):
    """**«يفشل مُغلَقاً» تُقاس:** بلا مانيفست ⇒ `rc=2` — ولا يُفتح إلّا بعلَمٍ صريحٍ `--ci`."""
    monkeypatch.setattr(ag, "MANIFEST", tmp_path / "nope.json")
    assert ag.load_deny() is None
    assert ag.main([]) == 2, "بلا مانيفست يجب أن يسقط مُغلَقاً (كان `rc=0` في الإصدار الثاني)"
    assert ag.main(["--ci"]) != 2, "`--ci` إعلانٌ صريح للسطح العامّ ⇒ يمضي ويُعلن ما فحصه"
    capsys.readouterr()


@pytest.mark.skipif(not ag.MANIFEST.exists(),
                    reason="المانيفستُ لا يُنشر بالتصميم ⇒ يُبنى محليًّا فقط")
def test_the_manifest_derivation_closes_and_carries_a_set_digest():
    """**حارسُ الاشتقاق:** لا يُنشر مانيفستٌ ناقص — والعددُ وحدَه لا يكشف تبديلَ قيمةٍ بأخرى."""
    data = json.loads(ag.MANIFEST.read_text(encoding="utf-8"))
    d = data["derivation"]
    assert d["source_shape_ok"] == d["entered"] + d["excluded_trivial"] + d["excluded_synthetic"]
    assert data["source_formats"] == d["entered"] > 500
    assert data["count"] == len(set(data["fingerprints"])), "العددُ المعلن = بصماتٌ فريدة"
    assert data["count"] <= data["source_formats"]
    assert data["keyed"] is True and d["published"] is False and len(data["set_digest"]) == 64


@pytest.mark.skipif(not ag.MANIFEST.exists(),
                    reason="المانيفستُ لا يُنشر بالتصميم")
def test_a_swapped_value_is_caught_even_when_the_count_is_unchanged(tmp_path, monkeypatch):
    """**تصحيحُ مراجعة ٣٨:** كان `staleness()` يقارن العددين ⇒ ٤٬٢٧٢ = ٤٬٢٧٢ يقبل تبديلَ قيمةٍ بأخرى."""
    real = json.loads(ag.MANIFEST.read_text(encoding="utf-8"))
    tampered = json.loads(json.dumps(real))
    tampered["fingerprints"][0] = "0" * 32           # نفسُ العدد · محتوى مختلف
    p = tmp_path / "m.json"
    p.write_text(json.dumps(tampered), encoding="utf-8")
    monkeypatch.setattr(ag, "MANIFEST", p)
    msg = ag.staleness()
    assert msg and "بصمةُ المجموعة" in msg, f"تبديلُ قيمةٍ مرّ بلا كشف: {msg}"


def test_the_manifest_is_not_stale():
    """**المانيفستُ يتعفّن:** إن تغيّر المصدرُ ولم يُبِن أحدٌ ⇒ الفحصُ يسقط ولا يمرّ كاذباً."""
    assert ag.staleness() is None, ag.staleness() or ""


@pytest.mark.skipif(not (ag.MANIFEST.exists() and ag.KEY_FILE.exists()),
                    reason="سطحٌ عامٌّ بلا أدلّة: الحقنُ لا سمَّ له ⇒ لا أُعلن نجاحاً ولا فشلاً")
def test_injection_falls_on_both_surfaces_in_a_throwaway_worktree():
    """**البرهانُ الطبقيُّ على سطحين** (دليل · صناعة) بستّ طبقات — ومنها طبقتا مراجعة ٣٨.

    (كان يكتب في `docs/SECURITY_PROBE.md` **داخل شجرةٍ يعمل عليها عدّةُ وكلاء** ⇒ صار في نسخةٍ
    مؤقّتةٍ تُحذف كاملة.)
    """
    assert ag.PROBE_SURFACES[0].startswith("docs/") and ag.PROBE_SURFACES[1].startswith("tests/")
    rc = ag.proof_inject()
    assert rc == 0, "حقنٌ لم يسقط كلَّ الأصناف على السطحين ⇒ الحارسُ ليس حارساً"


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "مُنكَرٌ مُعلن — الهدفُ **٤٢ ظهوراً في ١١ ملفّاً** (المقيس بعد تصحيح المطابِق، مراجعة ٣٨)، "
    "وكلُّها أسطحُ صناعة (tests/ · src/) تحتاج إعادةَ كتابةٍ بقيمٍ آمنةٍ مع توقّعاتها "
    "(القاعدة ١٤: تُغيَّر القيمةُ لا يُعفى الموضع). والسقاطةُ تحرس الطريق: لا زيادةَ حتى تُعاد."))
def test_the_repository_itself_carries_no_real_amount_in_tracked_text():
    assert ag.counts_by_file(ag.load_deny() or set()) == {}, \
        f"مبالغُ حقيقيّةٌ في ملفّاتٍ مُتتبَّعة: {ag.counts_by_file(ag.load_deny() or set())}"


def test_tracked_binaries_under_data_must_be_declared():
    assert ag.DECLARED_BINARIES.exists()
    assert ag.undeclared_binaries() == []


# ═══════════ أبوابُ مراجعة ٣٩ الأربعة: كلٌّ منها سقط فعلًا، وكلٌّ منها مُختبَرٌ الآن ═══════════


def _skip_without_evidence():
    if ag.load_deny() is None:
        pytest.skip("لا مانيفستَ محليّاً ⇒ ما لا يُنشر بالتصميم لا يُختبر هنا (يُعلن ولا يُدَّعى)")


def test_the_source_walk_is_root_invariant_and_an_empty_walk_refuses(tmp_path, monkeypatch):
    """**ثغرةُ ٣٩ رقم ١:** كان المشيُ على `ROOT` ⇒ بناءٌ من worktree أفرغ المانيفست الرئيسيّ.

    والمقياسُ هنا: (أ) المشيُ لا يتغيّر بتغيّر جذر التشغيل، (ب) مدخلٌ صفريّ يسقط ولا يكتب.
    """
    _skip_without_evidence()
    before = ag.source_amounts()
    monkeypatch.setattr(ag, "ROOT", tmp_path)
    after = ag.source_amounts()
    assert (after[1], after[2]) == (before[1], before[2]), \
        "المشيُ يجب أن يكون واحداً من أيّ جذر: المصدرُ من `DATA_ROOT` لا من `ROOT`"
    manifest = tmp_path / "m.json"
    monkeypatch.setattr(ag, "MANIFEST", manifest)
    monkeypatch.setattr(ag, "_artifacts", lambda globs=("data/**/*",): iter(()))
    with pytest.raises(SystemExit):
        ag.build([])
    assert not manifest.exists(), "صفرُ مدخلٍ ليس نتيجةً: لا يُكتب مانيفستٌ فارغ"


def test_an_unresolved_push_range_fails_closed():
    """**ثغرةُ ٣٩ رقم ٢:** `rev-list` يفشل على رأسٍ بعيدٍ غيرِ مجلوب ⇒ كان يمرّ `rc=0` بلا فحص."""
    cmd = [sys.executable, str(ROOT / "tools" / "amount_guard.py"), "--pre-push"]
    bogus = "refs/heads/x " + "1" * 40 + " refs/heads/x " + "2" * 40 + "\n"
    r = subprocess.run(cmd, input=bogus, capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 2 and "BLOCK" in r.stdout, "مدىً غيرُ محلولٍ ليس مدىً نظيفاً"
    # stdin فارغٌ (قِيس حيًّا في مسار دفعٍ حقيقيّ) ⇒ يُشتقّ المدى من الحالة **بإعلان**
    r2 = subprocess.run(cmd, input="", capture_output=True, text=True, cwd=ROOT)
    assert r2.returncode in (0, 1, 2), "لا انفجارَ على stdin فارغ"
    assert "اشتُقّ المدى" in r2.stdout or "BLOCK" in r2.stdout, \
        "البديلُ يُعلن ولا يمرّ صامتاً"


def test_the_baseline_cannot_be_raised_by_its_own_debtor(tmp_path, monkeypatch):
    """**ثغرةُ ٣٩ رقم ٣أ/٣ب:** كان الدافعُ يرفع عتبتَه فيمرّ ⇒ الآن الكتابةُ الزائدة تُرفَض."""
    _skip_without_evidence()
    seeded = tmp_path / "b.json"
    shutil.copy2(ag.BASELINE, seeded)          # نقطةُ انطلاقٍ حقيقيّة (لا ملفٌّ فارغٌ يُقارَن به)
    monkeypatch.setattr(ag, "BASELINE", seeded)
    deny = ag.load_deny() or set()
    assert ag.write_baseline(deny) == 0
    written = (tmp_path / "b.json").read_text(encoding="utf-8")
    monkeypatch.setattr(ag, "counts_with_commitment",
                        lambda d, files=None: {"tests/a.py": {"count": 99, "commitment": "zz"}})
    assert ag.write_baseline(deny) == 1, "زيادةٌ على خطّ الأساس ⇒ تُرفَض (القاعدة ١٤: لا يُعفى موضع)"
    assert (tmp_path / "b.json").read_text(encoding="utf-8") == written, "والملفُّ لم يُمَسّ"


def test_the_hook_never_blocks_a_push_on_a_missing_dev_tool():
    """**ثغرةُ ٣٩ رقم ٤:** حجبُ الدفع لغِياب pyflakes يخلق حافزَ `--no-verify` ⇒ ويسقط معه الأمن."""
    hook = (ROOT / ".githooks" / "pre-push").read_text(encoding="utf-8")
    i_pub = hook.index("publish_guard")
    i_amt = hook.index("amount_guard")
    i_static = hook.index("static_gate.py")
    assert i_pub < i_static and i_amt < i_static, "حرّاسُ الأمن تُشغَّل قبل أداة التطوير"
    assert "import pyflakes" in hook and "تخطّى" in hook, "غيابُ pyflakes يُعلَن ولا يحجب"
    code = "\n".join(l for l in hook.splitlines() if not l.lstrip().startswith("#"))
    assert "--no-verify" not in code, "ولا يُشير الخطّافُ إلى تجاوزه في كوده (الذكرُ في تعليقٍ تحذيريّ مشروع)"


def test_the_ci_baseline_audit_needs_no_key_and_no_evidence():
    """**ثغرةُ ٣٩ رقم ٣ (سطحُ CI):** القاعدةُ التي لا تحتاج سرّاً ⇒ تُنفَّذ حيث لا مفتاحَ ولا أدلّة."""
    if subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=ROOT,
                      capture_output=True).returncode != 0:
        pytest.skip("لا `origin/main` في هذه النسخة ⇒ لا أساسَ يُقارَن به")
    env = {k: v for k, v in os.environ.items() if k != "AMOUNT_GUARD_KEY"}
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "amount_guard.py"),
                        "--baseline-audit", "origin/main"],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    assert r.returncode == 0 and "بلا مفتاح" in r.stdout, r.stdout + r.stderr
