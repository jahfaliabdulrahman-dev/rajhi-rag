"""حارسُ المبالغ — اختبارُ القاعدة، واختبارُ **اشتقاقها**، واختبارُ سقوطها.

القاعدةُ العاشرة: حارسٌ بقائمةِ منعٍ مُشتقّة، **صحّتُه صحّةُ اشتقاقِها لا صحّةُ منطقِه**.
وقد سقط هذا الحارسُ مرّةً لأنّه قرأ مفتاحاً غير موجود (`rows` بدل `raw_rows`) فدار صفرَ مرّة
وبقي ٤,١٠٠ مبلغاً مصدريًّا خارجَه ⇒ صارت هذه الاختبارات تحرس **الاشتقاقَ** لا المنطقَ وحدَه.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("amount_guard", ROOT / "tools" / "amount_guard.py")
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)


def _key(tmp_path, monkeypatch):
    """مفتاحٌ وهميّ للاختبار: البصمةُ لا تُجرَد بغير المفتاح، والاختبارُ لا يحتاج المفتاحَ الحقيقيّ."""
    kf = tmp_path / "k"
    kf.write_text("test-key-not-the-real-one", encoding="utf-8")
    monkeypatch.setattr(ag, "KEY_FILE", kf)
    monkeypatch.delenv(ag.KEY_ENV, raising=False)


def test_normalizes_arabic_and_persian_digits_alike(tmp_path, monkeypatch):
    _key(tmp_path, monkeypatch)
    assert ag.normalize("٥٤٣٢١٠٫٩٩") == "543210.99"
    assert ag.normalize("۱٬۲۳۴٫۵۶") == "1234.56"
    assert ag.normalize("543,210.99") == "543210.99"


def test_amount_shaped_requires_four_integer_digits():
    assert ag.is_amount_shaped("1234.00") and ag.is_amount_shaped("٥٤٣٢١٠٫٩٩")
    assert not ag.is_amount_shaped("300.00")
    assert not ag.is_amount_shaped("0.979")


def test_scope_is_length_plus_a_decimal_never_the_roundness():
    """**تصحيحُ مراجعة ٣٦:** كان المُصفّي يستثني الكسرَ الصفريّ — والاستدارةُ صفةُ المبلغ لا
    دليلُ صناعيّته ⇒ ٢٤٦ مبلغاً مصدريًّا (٧.٩٪) كان خارج الحماية، و٣١ ظهوراً في ١٩ ملفاً.
    والنطاقُ الآن: ≥٤ خاناتٍ صحيحة **مع كسرٍ عشريّ** (وجودُ الكسر شرطٌ، وقيمتُه لا تهمّ).
    """
    assert ag.is_significant("248850.42") and ag.is_significant("1500.00") and ag.is_significant("-2671.00")
    assert not ag.is_significant("1000")          # بلا كسر: يتصادم مع تواريخ وعدّادات
    assert not ag.is_significant("450.00")        # قصيرٌ: يتصادم بطبعِه


def test_fixture_surfaces_are_warned_not_blocked():
    """الاستثناءُ **بسبب السطح لا بسبب الشكل**: الاختباراتُ أسطحُ صناعةٍ تُخترع فيها القيم."""
    assert ag.is_fixture_surface("tests/test_x.py") and ag.is_fixture_surface("src/statement_qa/x.py")
    assert not ag.is_fixture_surface("handoff/sulaiman/x.md") and not ag.is_fixture_surface("docs/x.md")


def test_the_rule_falls_on_a_value_it_was_built_for(tmp_path, monkeypatch):
    """**برهانُ السقوط بنواة الفحص نفسها** (بقيمةٍ وهميّة، فلا تسريبَ في الاختبار)."""
    _key(tmp_path, monkeypatch)
    deny = {ag.fingerprint("543210.99")}
    assert ag.find_in_text("الرصيد 543210.99", deny)
    assert ag.find_in_text("الرصيد ٥٤٣٢١٠٫٩٩", deny)      # الأبجديةُ لا تُنجيه
    assert not ag.find_in_text("قيمةٌ صناعية 300.00", deny)


def test_fingerprints_are_keyed_so_the_published_list_cannot_be_enumerated(tmp_path, monkeypatch):
    """البصمةُ المنشورة لا تُجرَد: بمفتاحٍ آخر لا تُطابق. (وبلا مفتاح: فشلٌ مُغلَق)"""
    import hashlib
    _key(tmp_path, monkeypatch)
    keyed = ag.fingerprint("543210.99")
    public = hashlib.sha256(b"rajhi-rag/amount-guard/v1" + b"543210.99").hexdigest()[:32]
    assert keyed != public
    monkeypatch.setattr(ag, "KEY_FILE", tmp_path / "missing")
    monkeypatch.delenv(ag.KEY_ENV, raising=False)
    try:
        ag.load_key()
        raise AssertionError("بلا مفتاح يجب أن يفشل الحارسُ مُغلَقاً لا صامتاً")
    except SystemExit:
        pass


def test_the_manifest_derivation_closes():
    """**حارسُ الاشتقاق:** لا يُنشر مانيفستٌ ناقص — الحسابُ يُغلق أو يسقط البناء."""
    data = json.loads(ag.MANIFEST.read_text(encoding="utf-8"))
    d = data["derivation"]
    assert d["source_shape_ok"] == d["entered"] + d["excluded_trivial"] + d["excluded_synthetic"]
    assert data["count"] == d["entered"] > 500
    assert data["keyed"] is True


def test_injection_returns_nonzero_when_blind():
    """أداةُ برهانٍ تُعلن الفشلَ وتخرج بنجاحٍ ليست بوابة ⇒ العمى يُخرج بغير الصفر."""
    rc = ag.proof_inject()
    has_corpus = bool(list((ROOT / "data" / "local_sample").glob("*/results/pg-*.json")))
    if has_corpus:
        assert rc == 0, "مع مصدرٍ محليّ يجب أن يسقط الحارسُ على سُمٍّ من قلب المصدر"
    else:
        assert rc == 5, "بلا مصدر: لا أُعلن نجاحاً — أخرج بغير الصفر"


def test_the_repository_itself_carries_no_real_amount_in_tracked_text():
    assert ag.scan() == [], f"مبالغُ حقيقيةٌ في ملفّاتٍ مُتتبَّعة: {ag.scan()[:3]}"


def test_tracked_binaries_under_data_must_be_declared():
    assert ag.DECLARED_BINARIES.exists()
    assert ag.undeclared_binaries() == []
