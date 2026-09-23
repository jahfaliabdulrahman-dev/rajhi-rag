"""سَمُّ الاستثناء — الحارسُ الذي لا يسقط لم يُثبت أنه حارس.

ما يُقاس:
  ١) **الحمايةُ بنيويّةٌ لا اختيارية** (مراجعة ٤٤): حزمةٌ على القرص تُستثنى بلا سؤال، وإلغاؤها يحتاج
     علَماً صريحاً — فأمرُ الالتقاط الموثَّق **لا يُلوّث صامتاً** (وكان يفعل: الشهادةُ المسجَّلة
     `captured: 416` بلا علَم ⇒ إعادةُ تشغيلٍ تُعيد ١٣٣ صفحةً إلى التدريب).
  ٢) **الفشلُ المُغلَق في خمسة أصناف:** قائمةٌ غائبة · لا تُقرأ · فارغة · **قراءةٌ ناقصة** · شكلٌ غيرُ معروف.
  ٣) **الهويّة:** المفتاحُ `(doc_id, page)` — حزمةُ مستندٍ آخر لا تُحجز صفحاتِ مستندنا.
  ٤) **الثابتُ الجوهريّ:** لا صفحةَ التقاطٍ من صفحات الحزمة (يُقاس على القرص الحقيقيّ).
  ٥) **ضبطٌ موجب** (لو زُرعت صفحةُ حزمةٍ لسقط الثابت) — وفي نسخةٍ نظيفةٍ **تخطٍّ مُعلَن** لا سقوط
     (و`SystemExit` في اختبار = `failed` لا `skipped` — مُثبتٌ بتشغيل).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.capture_training import (  # noqa: E402
    DEFAULT_PACK,
    pack_facts,
    pack_pages,
    resolve_exclusion,
)

PACK = ROOT / "data/eval_pack/pack.json"
TRAIN = ROOT / "data/training"


def _pack_file() -> dict:
    """حارسُ الوجود **قبل** أيّ قراءة: في نسخةٍ نظيفةٍ نُخطّي (وهذا مقصود) ولا نسقط."""
    if not PACK.exists():
        pytest.skip("لا حزمةَ على هذا القرص (الحزمةُ والالتقاطُ خارج git — التخطّي مقصود)")
    return json.loads(PACK.read_text(encoding="utf-8"))


def _pack_doc_id() -> str:
    """هويةُ الحزمة — والقياسُ أوّلًا: `identity` في هذه الحزمة **نصٌّ** لا قاموس."""
    d = _pack_file()
    ident = d.get("identity")
    got = d.get("doc_id") or (ident.get("doc_id") if isinstance(ident, dict) else ident)
    if not got:
        pytest.skip("الحزمةُ بلا هويّةٍ (doc_id) — لا مقارنةَ بلا مفتاح")
    return str(got)


def _captured_pages(doc_id: str, where: Path | None = None) -> set[int]:
    """صفحاتُ الالتقاط الفعليّة **لمستندٍ بعينه** — والمفتاحُ (doc_id, page) لا page."""
    root = where if where is not None else TRAIN
    doc = root / doc_id
    if not doc.is_dir():
        pytest.skip(f"لا التقاطَ للمستند {doc_id} على هذا القرص")
    out = {int(d.name.split("-")[-1]) for d in doc.glob("pg-*")
           if d.name.split("-")[-1].isdigit()}
    if not out:
        pytest.skip("مجلدُ الالتقاط فارغٌ (لم تُلتقط صفحةٌ)")
    return out


def _pack_file_on_disk(tmp_path: Path, *, census=(1, 2, 3), ranges=((4, 5),), declared=5,
                       identity: str = "3e2d360a665c88aa") -> Path:
    f = tmp_path / "pack.json"
    f.write_text(json.dumps({
        "identity": identity,
        "size_gate": {"value": declared, "expected": declared, "pass": True},
        "census": {"pages": [{"page": p} for p in census], "fingerprint": "fp"},
        "ranges": [{"pages": list(r)} for r in ranges],
    }), encoding="utf-8")
    return f


# ── ١) سياسةُ الاستثناء: بنيويّةٌ لا اختيارية ────────────────────────────────

def test_default_pack_is_protective_without_any_flag(tmp_path: Path):
    """**قلبُ الفرق (مراجعة ٤٤):** حزمةٌ على القرص ⇒ تُستثنى بلا سؤال — لا صمتٌ يُلوّث."""
    exists = _pack_file_on_disk(tmp_path)
    assert resolve_exclusion(None, False, exists) == exists


def test_explicit_path_wins():
    explicit = Path("/tmp/somewhere/pack.json")
    assert resolve_exclusion(explicit, False, DEFAULT_PACK) == explicit


def test_opt_out_requires_an_explicit_flag(tmp_path: Path):
    exists = _pack_file_on_disk(tmp_path)
    assert resolve_exclusion(None, True, exists) is None, "الإلغاءُ لا يقع بلا علَمٍ صريح"
    assert resolve_exclusion(Path("/tmp/x.json"), True, exists) is not None, "المسارُ الصريحُ أسبقُ من الإلغاء"


def test_no_pack_on_disk_means_no_exclusion(tmp_path: Path):
    assert resolve_exclusion(None, False, tmp_path / "absent.json") is None


# ── ٢) الفشلُ المُغلَق: خمسةُ أصناف ─────────────────────────────────────────

def test_no_pack_given_means_no_exclusion():
    """الدالّةُ النقيّة: «لا حزمةَ معلَنة» ⇒ لا استثناء (والسياسةُ في `resolve_exclusion`)."""
    assert pack_pages(None) == set()


def test_missing_file_fails_closed(tmp_path: Path):
    with pytest.raises(SystemExit) as e:
        pack_pages(tmp_path / "not-here.json")
    assert "لا التقاط" in str(e.value)


def test_unreadable_file_fails_closed(tmp_path: Path):
    bad = tmp_path / "pack.json"
    bad.write_text("{ ليس JSON", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        pack_pages(bad)
    assert "لا تُقرأ" in str(e.value)


def test_directory_instead_of_file_fails_closed(tmp_path: Path):
    with pytest.raises(SystemExit) as e:
        pack_pages(tmp_path)
    assert "لا تُقرأ" in str(e.value)


def test_empty_pack_fails_closed(tmp_path: Path):
    empty = tmp_path / "pack.json"
    empty.write_text(json.dumps({"census": {"pages": []}, "ranges": []}), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        pack_pages(empty)
    assert "فارغة" in str(e.value)


def test_incomplete_read_fails_closed(tmp_path: Path):
    """قراءةٌ ناقصةٌ أسوأُ من غياب الاستثناء: تُبقي صفحاتِ الحزمة في التدريب بصمت."""
    partial = tmp_path / "pack.json"
    partial.write_text(json.dumps({"size_gate": {"value": 200},
                                   "census": {"pages": [{"page": 1}]},
                                   "ranges": [{"pages": [2, 3]}]}), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        pack_pages(partial)
    assert "ناقصة" in str(e.value)


def test_unknown_shape_fails_closed(tmp_path: Path):
    weird = tmp_path / "pack.json"
    weird.write_text(json.dumps({"census": {"pages": ["<p>5</p>"]}, "ranges": []}),
                     encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        pack_pages(weird)
    assert "غيرُ معروف" in str(e.value)


def test_reads_pages_from_both_census_and_ranges(tmp_path: Path):
    f = _pack_file_on_disk(tmp_path)
    assert pack_pages(f) == {1, 2, 3, 4, 5}


# ── ٣) الهويّة: المفتاحُ (doc_id, page) ──────────────────────────────────────

def test_identity_mismatch_drops_the_exclusion_and_announces():
    """حزمةُ **مستندٍ آخر** ⇒ لا استثناء (أرقامُ الصفحات لا تعني شيئًا عبر المستندات) **ويُعلَن** (F3).

    وكان يقف بالاسم؛ وهذا كان يكسر أمراً موثَّقاً (إعادةُ التقاط بيانٍ رقميّ والحزمةُ على القرص).
    والضمانةُ الحقيقيّةُ للمستند نفسِه باقية: مفتاحُ `(doc_id, page)` وسمُّ التصادم المُلتزم.
    """
    f = pack_facts(PACK, expect_identity="0" * 16)
    assert f["pages"] == set(), "حزمةُ مستندٍ آخر يجب ألا تستثني شيئاً"
    assert "لمستندٍ آخر" in (f.get("note") or ""), "الاختلافُ يجب أن يُعلَن لا أن يمرّ صامتاً"

def test_identity_recorded_in_facts(tmp_path: Path):
    facts = pack_facts(_pack_file_on_disk(tmp_path), expect_identity="3e2d360a665c88aa")
    assert facts["identity"] == "3e2d360a665c88aa" and facts["declared"] == 5 and facts["file"]


# ── ٤) الثابتُ الجوهريّ على القرص الحقيقيّ + ضبطٌ موجب ──────────────────────

def test_frozen_pack_has_zero_page_intersection_with_capture():
    did = _pack_doc_id()
    pages = pack_pages(PACK, expect_identity=did)
    captured = _captured_pages(did)
    inter = sorted(pages & captured)
    assert inter == [], (f"صفحاتٌ في الحزمة المجمّدة التُقطت للتدريب: {inter[:10]} "
                         f"(التقاطعُ ليس صفراً ⇒ الحزمةُ ليست معزولة)")


def test_intersection_poison_positive_control(tmp_path: Path):
    """ضبطٌ موجب: لو ظهرت صفحةُ حزمةٍ في الالتقاط لسقط الثابت — السَمُّ لا يمرّ دائماً."""
    pages = pack_pages(PACK, expect_identity=_pack_doc_id())
    some = sorted(pages)[0]
    fake = tmp_path / "training"
    (fake / "deadbeef" / f"pg-{some:02d}").mkdir(parents=True)
    assert sorted(pages & _captured_pages("deadbeef", where=fake)) == [some], \
        "الضبطُ الموجبُ لم يَسُمّ — الثابتُ أعمى"


def test_manifest_declares_pack_reserved_when_excluded():
    """البيانُ يُعلن المحجوزَ باسمه لمستند الحزمة، وعدّاداتُه تُغلق — والصنفُ يُبلَّغ في الفهرس."""
    man = TRAIN / _pack_doc_id() / "manifest.json"
    if not man.exists():
        pytest.skip("لا بيانَ التقاطٍ للحزمة على هذا القرص")
    d = json.loads(man.read_text(encoding="utf-8"))
    p = d.get("pages", {})
    assert "pack_reserved" in p, "البيانُ لا يُعلن عدّادَ المحجوز للحزمة"
    assert p.get("pack_reserved", 0) > 0, "لا صفحةَ محجوزةٍ للحزمة في بيانٍ بنيناه بالاستثناء"
    # الإغلاقُ يُقاس من `by_status` (الحقيقةُ الواحدة) لا من جمعٍ يُعيد العدَّ مرّتين
    by_status = p.get("by_status") or {}
    assert sum(by_status.values()) == p.get("visited", sum(by_status.values())), \
        "عدّاداتُ by_status لا تُغلق على نفسها"
    assert by_status.get("pack_reserved") == p["pack_reserved"], "عدّادُ المحجوز لا يطابق توزيعَ الحالات"
    skipped = p.get("skipped", [])
    assert len([s for s in skipped if s.get("why") == "pack_reserved"]) == p["pack_reserved"], \
        "عدّادُ المحجوز لا يطابق قائمته"
    px = d.get("pack_exclusion") or {}
    if px:
        assert px.get("identity") and px.get("file"), "وسمُ الحزمة بلا هويّةٍ أو ملفّ"
