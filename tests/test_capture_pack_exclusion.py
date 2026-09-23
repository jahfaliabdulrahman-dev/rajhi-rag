"""سَمُّ الاستثناء — الحارسُ الذي لا يسقط لم يُثبت أنه حارس.

ثلاثةُ أشياء تُقاس هنا:
  ١) `pack_pages` تقرأ صفحاتِ الحزمة من ملفِّها (لا تُكتب بيد) وتفشل **مُغلَقةً** عند غياب القائمة
     أو فراغها — لأنّ استثناءً بلا صفحاتٍ يمرّ صامتاً هو أسوأُ من غياب الاستثناء.
  ٢) **الثابتُ الجوهريّ:** لا صفحةَ التقاطٍ واحدة من صفحات الحزمة المجمّدة ⇒ التقاطعُ صفرٌ **بالبناء**
     لا بالفحص المتأخّر (السَمُّ يقرأ القرصَ الحقيقيّ ويقارن).
  ٣) وسَمُ الحكم: لو زُرعت صفحةُ حزمةٍ في الالتقاط لسقط الثابت (ضبطٌ موجب) — يُقاس على مجلدٍ مؤقّت.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _mod(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


cap = _mod("capture_training", "tools/capture_training.py")

PACK = ROOT / "data/eval_pack/pack.json"
TRAIN = ROOT / "data/training"


def _pack_file() -> dict:
    if not PACK.exists():
        pytest.skip("لا حزمةَ على هذا القرص (الالتقاطُ والحزمةُ خارج git)")
    return json.loads(PACK.read_text(encoding="utf-8"))


def _pack_doc_id() -> str:
    """هويةُ الحزمة — والقياسُ أوّلاً: `identity` في هذه الحزمة **نصٌّ** لا قاموس."""
    d = _pack_file()
    ident = d.get("identity")
    got = d.get("doc_id") or (ident.get("doc_id") if isinstance(ident, dict) else ident)
    if not got:
        pytest.skip("الحزمةُ بلا هويّةٍ (doc_id) — لا مقارنةَ بلا مفتاح")
    return str(got)


def _captured_pages(doc_id: str, where: Path | None = None) -> set[int]:
    """صفحاتُ الالتقاط الفعليّة **لمستندٍ بعينه** — والمفتاحُ (doc_id, page) لا page.

    صفحةُ ٥ في مستندٍ ليست صفحةَ ٥ في آخر (والحزمةُ نفسُها تُعلن هذا المفتاح في بوابة التقاطع).
    فمقارنةُ الأرقام بلا هويّةٍ تُنتج تلوّثاً وهميّاً، أو تُخفي تلوّثاً حقيقيّاً.
    """
    root = where if where is not None else TRAIN
    doc = root / doc_id
    if not doc.is_dir():
        pytest.skip(f"لا التقاطَ للمستند {doc_id} على هذا القرص")
    out = {int(d.name.split("-")[-1]) for d in doc.glob("pg-*")
           if d.name.split("-")[-1].isdigit()}
    if not out:
        pytest.skip("مجلدُ الالتقاط فارغٌ (لم تُلتقط صفحةٌ)")
    return out


# ── ١) القراءة والفشلُ المُغلَق ─────────────────────────────────────────────

def test_no_pack_given_means_no_exclusion():
    assert cap.pack_pages(None) == set()


def test_missing_file_fails_closed(tmp_path: Path):
    gone = tmp_path / "not-here.json"
    with pytest.raises(SystemExit) as e:
        cap.pack_pages(gone)
    assert "لا التقاط" in str(e.value)


def test_empty_pack_fails_closed(tmp_path: Path):
    empty = tmp_path / "pack.json"
    empty.write_text(json.dumps({"census": {"pages": []}, "ranges": []}), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        cap.pack_pages(empty)
    assert "فارغة" in str(e.value)


def test_reads_pages_from_both_census_and_ranges(tmp_path: Path):
    f = tmp_path / "pack.json"
    f.write_text(json.dumps({"census": {"pages": [{"page": 3}, {"page": 7}]},
                             "ranges": [{"pages": [{"page": 11}, {"page": 12}]}]}),
                 encoding="utf-8")
    assert cap.pack_pages(f) == {3, 7, 11, 12}


# ── ٢) الثابتُ الجوهريّ: التقاطعُ صفرٌ بالبناء ───────────────────────────────

def test_frozen_pack_has_zero_page_intersection_with_capture():
    pages = cap.pack_pages(PACK)
    captured = _captured_pages(_pack_doc_id())
    inter = sorted(pages & captured)
    assert inter == [], (f"صفحاتٌ في الحزمة المجمّدة التُقطت للتدريب: {inter[:10]} "
                         f"(التقاطعُ ليس صفراً ⇒ الحزمةُ ليست معزولة)")


def test_intersection_poison_positive_control(tmp_path: Path):
    """ضبطٌ موجب: لو ظهرت صفحةُ حزمةٍ في الالتقاط لسقط الثابت — السَمُّ لا يمرّ دائماً."""
    pages = cap.pack_pages(PACK)
    some = sorted(pages)[0]
    fake = tmp_path / "training"
    (fake / "deadbeef" / f"pg-{some:02d}").mkdir(parents=True)
    assert sorted(pages & _captured_pages("deadbeef", where=fake)) == [some], \
        "الضبطُ الموجبُ لم يَسُمّ — الثابتُ أعمى"


def test_manifest_declares_pack_reserved_when_excluded():
    """البيانُ يُعلن المحجوزَ باسمه لمستند الحزمة: عدّادٌ صريح لا صفحةٌ تختفي صامتة."""
    man = TRAIN / _pack_doc_id() / "manifest.json"
    if not man.exists():
        pytest.skip("لا بيانَ التقاطٍ للحزمة على هذا القرص")
    p = json.loads(man.read_text(encoding="utf-8")).get("pages", {})
    assert "pack_reserved" in p, "البيانُ لا يُعلن عدّادَ المحجوز للحزمة"
    # والحسابُ يُغلق على نفسه: `pack_reserved` **داخل** `skipped` (لا يُعدّ مرّتين)
    assert p.get("pack_reserved", 0) > 0, "لا صفحةَ محجوزةٍ للحزمة في بيانٍ بنيناه بالاستثناء"
    skipped = p.get("skipped", [])
    reserved = [s for s in skipped if s.get("why") == "pack_reserved"]
    assert len(reserved) == p["pack_reserved"], "عدّادُ المحجوز لا يطابق قائمته"
    total = p.get("captured", 0) + p.get("holdout_reserved", 0) + len(skipped)
    assert total == p.get("visited", total), "عدّاداتُ البيان لا تُغلق على نفسها"
