"""Public numbers must be derived from the run, not remembered (audit P2-5).

Four drifts were caught by a human reading two files at once; this test is the
mechanism that replaces that. It skips where the evidence does not exist (CI
has no statement cache), which is stated plainly rather than hidden.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def test_public_documents_match_the_measured_report():
    import render_claims as rc

    if not rc.REPORT.exists():
        # CI has no statement cache. Instead of skipping — a gate that guards
        # nothing — it reads the DERIVED snapshot committed with the repo:
        # written by tools/render_claims.py from the measured report, so the
        # numbers stay a product of the run and not of anyone's memory.
        snapshot = ROOT / "docs" / "claims.json"
        if not snapshot.exists():
            pytest.skip("لا تقرير ولا لقطة مشتقّة — لا شيء يُحرَس")
        derived = json.loads(snapshot.read_text(encoding="utf-8"))
        assert rc.check(derived) == [], "الوثيقة تخالف لقطتها المشتقّة"
        return
    derived = rc.derive()
    assert derived is not None
    drifts = rc.check(derived)
    assert drifts == [], f"انزياح بين الوثيقة ومصدرها: {drifts}"


def test_a_stale_snapshot_cannot_hide_behind_a_stale_document(tmp_path, monkeypatch):
    """**الثقبُ الذي أمسكته المراجعة ٦٦ (R66-1): بلا تقريرٍ مقيس، كانت الوثيقةُ تُقابَل باللقطة وحدَها.**

    فلقطةٌ `tests=865` ووثيقةٌ تقول «حالياً 865» **توافقان بعضَهما** بينما العدُّ الحيُّ `868` ⇒ الحكمُ
    أخضرُ في الـCI ولا أحدَ يرى الانزياح (قِيس: `render_claims.py --check` ⇒ «الوثائقُ توافق لقطتها
    الملتزمة» والعدُّ الحيُّ `868`). و`_test_count()` **لا يحتاج** كاشَ التصريح ⇒ فصار العددُ يُقاس حيًّا
    في هذا المسار أيضًا؛ وهذا الضابطُ يقيس **العلّةَ نفسَها**: يُثبّت لقطةً متقادمة، ويُطالب بالخروج `1`.
    (والوثيقةُ تُطابَق بـ`check` مُبدَّلةٍ هنا لتُحاكي «وثيقةٌ موافقةٌ للقطة» — وهو حالُ العطب بعينه.)
    """
    import json
    import render_claims as rc

    snap = tmp_path / "claims.json"
    snap.write_text(json.dumps({"tests": 0}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(rc, "SNAPSHOT", snap)
    monkeypatch.setattr(rc, "REPORT", tmp_path / "no-report-here.json")
    monkeypatch.setattr(rc, "check", lambda _d: [])          # الوثيقةُ توافق اللقطةَ المتقادمة (العطب)
    monkeypatch.setattr(sys, "argv", ["render_claims.py", "--check"])
    with pytest.raises(SystemExit) as e:
        rc.main()
    assert e.value.code == 1, "لقطةٌ متقادمةٌ مرّت: العددُ لم يُقَس حيًّا في مسار اللقطة"


def test_claims_lists_every_metric_it_promises():
    import render_claims as rc

    fake = {"pages": 629, "rows": 5793, "clean": 5770, "clean_pct": "99.6%",
            "ok": 621, "mismatch": 0, "gap": 2, "absent": 4, "unchecked": 2,
            "documented_ratio": "621/629", "clean_ratio": "5770/5793",
            "recoveries": 23, "rereads": 15, "arbitrations": 3,
            "median_page_s": 22.18, "tests": 113, "gate3_price_cap_pages": 133}
    pairs = rc.claims(fake)
    assert len(pairs) >= 8
    assert any(n == "621/629" for _f, n, _l in pairs)
    assert any("مرساة" in n for _f, n, _l in pairs)
    # **وسقفُ القرار له مقابلةٌ في الوثائق** (review-60): يُشتقّ من كائن القرار ويُقابَل في موضعين.
    caps = [(f, n) for f, n, _l in pairs if "سقفُ ثمنِ الإفراج" in n]
    assert len(caps) == 2 and all("133" in n for _f, n in caps), caps


def test_the_withdrawn_gate3_license_is_not_restated_in_public_docs():
    """**مفتاحُ الرخصة المسحوبة لا يعود** (review-60 · R60-1): كان القرارُ يُرخي **التقاطعَ نفسَه**
    بمفتاح `accepted_pages` ⇒ رخصةُ إدخال صفحةٍ من الحزمة إلى بيانات التدريب والحكمُ `PASS`.
    فالمصدرُ الواحدُ (`GATE3_DECISION`) يحرس مفتاحَه في اختبار الأداة، **والوثائقُ المعلَنةُ** تحرس
    ألّا تُعيد الرخصةَ بآليّتها (وقد شرحناها مؤرَّخةً في `docs/EVAL_PACK.md` — الشرحُ ليس إعادةَ تفعيل).
    """
    for rel in ("docs/GATES.md", "README.md", "PLAN.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "accepted_pages" not in text, \
            f"{rel}: مفتاحُ الرخصة المسحوبة رجع ⇒ البوابةُ (٣) تُرخى بقرارٍ من جديد (R60-1)"
    # **و`docs/EVAL_PACK.md` خارجَ القائمة عن قصد**: هو الموضعُ الوحيد الذي **يشرح** الرخصةَ المسحوبة
    # بتاريخها (والمذيَّلُ «التصحيحُ الحاكم») ⇒ فيه اسمُ المفتاح اقتباسًا لا تعليمًا. والحكمُ عليه محروسٌ
    # من جهة الشيفرة (`tests/test_eval_pack.py`: المفتاحُ ممنوعٌ في `GATE3_DECISION` نفسِه).
