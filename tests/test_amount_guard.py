"""حارسُ المبالغ — اختبارُ القاعدة **واختبارُ سقوطها**.

القاعدةُ التي لا تسقط عند حقن العطب الذي وُضعت له ليست قاعدة (القاعدةُ التاسعة).
وهذه القاعدةُ وُضعت لأن حارساً قائماً مرّ وأمامه ١٢٦ ظهوراً لمبالغَ حقيقية.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("amount_guard", ROOT / "tools" / "amount_guard.py")
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)


def test_normalizes_arabic_and_persian_digits_alike():
    assert ag.normalize("٥٤٣٢١٠٫٩٩") == "543210.99"
    assert ag.normalize("۱٬۲۳۴٫۵۶") == "1234.56"
    assert ag.normalize("543,210.99") == "543210.99"


def test_amount_shaped_requires_four_integer_digits():
    assert ag.is_amount_shaped("1234.00") and ag.is_amount_shaped("٥٤٣٢١٠٫٩٩")
    assert not ag.is_amount_shaped("300.00")          # قيمٌ ذهبية صناعية
    assert not ag.is_amount_shaped("0.979")


def test_the_rule_falls_on_a_real_amount_it_was_built_for(tmp_path, monkeypatch):
    """**برهانُ السقوط:** مبلغٌ حقيقيّ ⇒ الحارسُ يسقط، بنفس النواة التي يفحص بها الشجرة."""
    monkeypatch.setattr(ag, "MANIFEST", tmp_path / "deny.json")
    assert ag.build(["543210.99"]) == 0
    deny = ag.load_deny()
    assert ag.find_in_text("الرصيد الصحيح 543210.99 في التذييل", deny)
    assert ag.find_in_text("الرصيد بالعربية ٥٤٣٢١٠٫٩٩", deny)      # الأبجدية لا تُنجيه
    assert not ag.find_in_text("الرصيد صناعيٌّ 300.00", deny)       # ولا إيجابيّةَ كاذبة


def test_the_committed_manifest_is_present_and_substantial():
    assert ag.MANIFEST.exists(), "المانيفستُ الغائب يعني حارساً لا يعرف ما يحرس"
    import json
    data = json.loads(ag.MANIFEST.read_text(encoding="utf-8"))
    assert data["count"] >= 500 and len(data["fingerprints"]) == data["count"]


def test_the_repository_itself_carries_no_real_amount_in_tracked_text():
    hits = ag.scan()
    assert hits == [], f"مبالغُ حقيقيةٌ في ملفّاتٍ مُتتبَّعة: {hits[:5]}"


def test_tracked_binaries_under_data_must_be_declared():
    """الصنفُ الذي لا يراه الحارسُ النصّيّ: مسحٌ ضوئيٌّ مدفوع. الإعلانُ يجعل التتبّعَ قراراً معلناً."""
    assert ag.DECLARED_BINARIES.exists(), "ملفُّ الإعلان غائب ⇒ لا يعرف أحدٌ لماذا هذا الثنائيُّ مدفوع"
    assert ag.undeclared_binaries() == [], "ثنائيٌّ مدفوعٌ بلا إعلانٍ بسبب"


def test_the_declared_binary_is_the_synthetic_sample_only():
    import subprocess as sp
    tracked = sp.run(["git", "ls-files"], cwd=str(ag.PROJ), capture_output=True, text=True).stdout.split()
    bins = [f for f in tracked if f.startswith(("data/", "digital/"))
            and f.rsplit(".", 1)[-1].lower() in {"pdf", "png", "jpg", "jpeg", "tif", "tiff"}]
    assert bins == ["data/sample/statement_sample.pdf"], f"ثنائياتٌ مدفوعةٌ غيرُ متوقَّعة: {bins}"
