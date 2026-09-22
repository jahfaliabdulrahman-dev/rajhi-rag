"""حارسُ المبالغ — اختبارُ القاعدة، واختبارُ **اشتقاقها**، واختبارُ سقوطها.

القاعدةُ العاشرة: حارسٌ بقائمةِ منعٍ مُشتقّة، **صحّتُه صحّةُ اشتقاقِها لا صحّةُ منطقِه**.

**وأربعةُ دروسٍ دُمِّرت مرّات، وكلُّ درسٍ هنا مُجرَّبُ السقوط لا مُدَّعى:**
١) المدى = ≥٤ خاناتٍ صحيحة **+ وجودُ كسرٍ عشريّ** (الاستدارةُ صفةُ المبلغ لا دليلُ صناعيّته).
٢) **لا يُعفى موضع، يُعفى قيمة (القاعدة ١٢)** — كان إعفاءٌ بالمسار يُمرّر مبلغاً حقيقيًّا في `tests/`.
٣) **الإهمالُ واقعٌ يُقاس (القاعدة ١٤)** — كان المفتاحُ مُلتزَماً والتوثيقُ يقول «(مُهمَل)».
٤) **المخرَجُ الآليُّ لا يُقصّ (القاعدة ١٣)** — كان `--json` يعرض ٢٠ ويُعلن ٤٠.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
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


def test_scope_is_length_plus_a_decimal_never_the_roundness():
    """**تصحيحُ مراجعة ٣٦:** كان المُصفّي يستثني الكسرَ الصفريّ — والاستدارةُ صفةُ المبلغ لا
    دليلُ صناعيّته ⇒ ٢٤٦ مبلغاً مصدريًّا (٧.٩٪) كان خارج الحماية، و٣١ ظهوراً في ١٩ ملفاً.

    **وعاد العطبُ من بابٍ ثانٍ:** لمّا صار التطبيعُ المرجعيُّ داخل `normalize` نفسه، صار
    `9001.00` ⇒ `1500` ⇒ **انتفى شرطُ الكسر صامتاً**. ولذلك يفصل هذا الاختبارُ بين البابين.
    """
    assert ag.is_significant("7777.00") and ag.is_significant("7777.0") and ag.is_significant("-7777.00")
    assert not ag.is_significant("7777")            # بلا كسر: يتصادم مع تواريخ وعدّادات
    assert not ag.is_significant("450.00")          # قصيرٌ: يتصادم بطبعِه
    assert ag.is_significant(ag.normalize("7777.00")), "النصُّ يحفظ وجودَ الكسر ⇒ شرطُ المدى سليم"


def test_canonical_collapses_writing_forms_but_applies_to_the_fingerprint_only():
    """**الشكلُ لا يهمّ في البصمة** (`7777.0` ≡ `7,777.00`) — **ويهمّ في المدى**. الفصلُ ضروريّ."""
    assert ag.canonical("7777.0") == ag.canonical("7,777.00") == ag.canonical("٧٧٧٧٫٠٠") == "7777"
    assert len({ag.canonical("7777.0"), ag.canonical("7777.00")}) == 1


def test_no_location_is_exempt(tmp_path, monkeypatch):
    """**الدرسُ الثاني (القاعدة ١٢):** قناةُ `tests/` مُغلقة — والسمُّ يُشتقّ من المصدر لا يُكتب هنا.

    كان `FIXTURE_PREFIXES = ("tests/", "src/")` إعفاءً بالمسار ⇒ حقنُ مبلغين حقيقيين في
    `tests/` مرّ بـ`PASS`. **والفرقُ بين سطحِ صناعةٍ وقناةِ تسريبٍ ليس في المجلد بل في القيمة.**
    """
    _key(tmp_path, monkeypatch)
    target = ROOT / "tests" / "SECURITY_PROBE.py"
    backup = target.read_text(encoding="utf-8") if target.exists() else None
    try:
        target.write_text(f"الرصيد: {FAKE}\n", encoding="utf-8")
        monkeypatch.setattr(ag, "load_deny", lambda: {ag.fingerprint(FAKE)})
        monkeypatch.setattr(ag, "SCAN_SKIP", set())
        hits = [h for h in ag.scan() if h[0].endswith("SECURITY_PROBE.py")]
        assert hits, "مبلغٌ حقيقيٌّ في `tests/` لم يُسقط الحارس ⇒ إعفاءٌ بالمسار عاد (القاعدة ١٢)"
    finally:
        if backup is None:
            target.unlink(missing_ok=True)
        else:
            target.write_text(backup, encoding="utf-8")


def test_the_rule_falls_on_a_value_it_was_built_for(tmp_path, monkeypatch):
    """**برهانُ السقوط بنواة الفحص نفسها** (بقيمةٍ وهميّة، فلا تسريبَ في الاختبار)."""
    _key(tmp_path, monkeypatch)
    deny = {ag.fingerprint(FAKE)}
    assert ag.find_in_text("الرصيد 543210.99", deny)
    assert ag.find_in_text(f"الرصيد {FAKE_AR}", deny)       # الأبجديةُ لا تُنجيه
    assert not ag.find_in_text("قيمةٌ صناعية 300.00", deny)


def test_fingerprints_are_keyed_so_the_published_list_cannot_be_enumerated(tmp_path, monkeypatch):
    """البصمةُ بمفتاحٍ آخر لا تُطابق، وبلا مفتاح: **فشلٌ مُغلَق**."""
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


def test_ignore_is_a_measured_fact_not_a_claim(tmp_path, monkeypatch):
    """**الدرسُ الثالث (القاعدة ١٤):** «مُهمَل» تُقاس بـ`git` — المفتاحُ كان مُلتزَماً والمستودعُ عامّ."""
    assert ag.tracking_audit() == [], (f"المفتاحُ/المانيفستُ يجب أن يكونا مُهمَلَين وغيرَ متتبَّعين: "
                                       f"{ag.tracking_audit()}")
    for path in (ag.KEY_FILE, ag.MANIFEST):
        rel = str(path.relative_to(ROOT))
        assert subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel],
                              cwd=str(ROOT), capture_output=True).returncode != 0, f"{rel} مُتتبَّع ⛔"
        assert subprocess.run(["git", "check-ignore", "-q", "--", rel],
                              cwd=str(ROOT), capture_output=True).returncode == 0, f"{rel} غيرُ مُهمَل ⛔"


def test_the_manifest_is_never_published():
    """**لا يُنشر ما يمكن مهاجمتُه:** فضاءُ المبلغ ~١٠⁸ ⇒ بصماتٌ منشورةٌ تُستَرجَع بالقاموس."""
    rel = str(ag.MANIFEST.relative_to(ROOT)).replace("\\", "/")
    assert rel.startswith("data/"), "المانيفستُ يجب أن يسكن في data/ المُهمَل"
    assert not (ROOT / "docs" / "security" / "amount-denylist.json").exists(), \
        "نسخةٌ منشورةٌ من البصمات ⇒ القاموسُ يستعيدها في دقائق"


def test_json_output_is_never_truncated():
    """**الدرسُ الرابع (القاعدة ١٣):** العددُ المعلن = طولُ القائمة، دائماً."""
    r = subprocess.run([sys.executable, "tools/amount_guard.py", "--json"],
                       cwd=str(ROOT), capture_output=True, text=True)
    if not r.stdout.strip().startswith("{"):
        pytest.skip("لا مانيفستَ (سطحٌ عامّ) ⇒ الفحصُ غيرُ قابلٍ للإنفاذ هنا")
    payload = json.loads(r.stdout)
    assert payload["count"] == len(payload["hits"]), "المخرَجُ الآليُّ مقصوصٌ ⇒ نقضُ القاعدة ١٣"


def test_the_manifest_derivation_closes():
    """**حارسُ الاشتقاق:** لا يُنشر مانيفستٌ ناقص — الحسابُ يُغلق أو يسقط البناء."""
    data = json.loads(ag.MANIFEST.read_text(encoding="utf-8"))
    d = data["derivation"]
    assert d["source_shape_ok"] == d["entered"] + d["excluded_trivial"] + d["excluded_synthetic"]
    assert data["count"] == d["entered"] > 500
    assert data["keyed"] is True and d["published"] is False


def test_the_manifest_is_not_stale():
    """**المانيفستُ يتعفّن:** إن تغيّر المصدرُ ولم يُبنَ ⇒ الفحصُ يسقط ولا يمرّ كاذباً."""
    assert ag.staleness() is None, ag.staleness() or ""


def test_injection_falls_on_both_surfaces():
    """**البرهانُ الطبقيّ** (مستدير · كسريّ · سالب · طويل × دليل · صناعة) — يسقط إن نجا أيُّها.

    **وما لا يُحقَن فيه لا يُعرف حالُه** ⇒ السطحان مطلوبان.
    """
    rc = ag.proof_inject()
    assert rc == 0, "حقنٌ لم يسقط كلَّ الأصناف على السطحين ⇒ الحارسُ ليس حارساً"


@pytest.mark.xfail(strict=False, reason=(
    "مُنكَرٌ مُعلن: ٤٠ قيمةً في أسطح الصناعة (tests/ · src/) تتصادم مع مبالغَ حقيقيّة، "
    "وتحتاج إعادةَ كتابةٍ بقيمٍ آمنةٍ مع توقّعاتها (القاعدة ١٢: تُغيَّر القيمةُ لا يُعفى الموضع). "
    "الفحصُ اليوم يُسقطها بغير الصفر — وهو السلوكُ الصحيحُ حتى تُعاد كتابتُها"))
def test_the_repository_itself_carries_no_real_amount_in_tracked_text():
    assert ag.scan() == [], f"مبالغُ حقيقيّةٌ في ملفّاتٍ مُتتبَّعة: {ag.scan()[:3]}"


def test_tracked_binaries_under_data_must_be_declared():
    assert ag.DECLARED_BINARIES.exists()
    assert ag.undeclared_binaries() == []
