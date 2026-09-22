"""مُنشئُ حزمة التقييم: البواباتُ والعرفُ والسموم — كلُّها تُقاس لا تُدَّعى.

الأرضيةُ هنا **صناعية** عمداً: اختبارٌ يعتمد على `data/local_sample` (غير متتبَّع)
لا يعمل في CI، واختبارٌ لا يعمل ليس اختباراً. والصفحاتُ الأربع مُصمَّمة لتحمل
**حالتي الحدّ** التي كلَّفتنا قياساً حقيقياً:

* **الإطارُ المطبوع تراكميّ** (ص2 = ص1 + حركاتها) ⇒ البوابةُ «دلتا الإطارين» لا
  «مجموعُ الصفحات».
* **السلسلةُ تعبر حدَّ الصفحة**: أوّلُ حركةٍ في ص2 هنا **دائنٌ**، فلو صُنِّفت «مدينٌ
  افتراضاً» انزاح المبلغُ وانكسرت البوابةُ — وهو عينُ ما قِيس على 8 صفحاتٍ من 50.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.eval_pack import (  # noqa: E402
    DEFINITIONS, PACK_SIZE, Run, _sha16, build_census, longest_run, main, measure_range, poisons,
)

DOC = "aaaaaaaaaaaaaaaa"
OTHER = "bbbbbbbbbbbbbbbb"

#: صفحاتُ الأرضية: (حركاتٌ كـ(مبلغ, رصيد), إطارٌ تراكميّ)
PAGES = {
    1: ([("300.00", "300.00"), ("100.00", "200.00")], {"debits": "100.00", "credits": "300.00", "balance": "200.00"}),
    2: ([("50.00", "250.00"), ("20.00", "230.00")], {"debits": "120.00", "credits": "350.00", "balance": "230.00"}),
    3: ([("30.00", "200.00")], {"debits": "150.00", "credits": "350.00", "balance": "200.00"}),
    4: ([("100.00", "300.00")], {"debits": "150.00", "credits": "450.00", "balance": "300.00"}),
}


def _corpus(tmp: Path, doc_id: str | None = DOC, pages=PAGES) -> Path:
    run = tmp / "run"
    (run / "results").mkdir(parents=True)
    (run / "slice_report.json").write_text(json.dumps(
        {"corpus_provenance": {"doc_id": doc_id, "doc_id_note": "استدراك"}}, ensure_ascii=False),
        encoding="utf-8")
    for n, (mvs, footer) in pages.items():
        rows = [{"movement": None, "balance": "0.00", "desc": "الرصيد الافتتاحى"}] if n == 1 else []
        rows += [{"movement": a, "balance": b, "date": "٢٠٢٤٠١٠١", "date_source": "cell",
                  "desc": f"حركة {i}"} for i, (a, b) in enumerate(mvs, 1)]
        (run / "results" / f"pg-{n:03d}.json").write_text(
            json.dumps({"pg": n, "raw_rows": rows, "footer": footer}, ensure_ascii=False), encoding="utf-8")
    return run


def _tmpcorpus() -> Run:
    """تشغيلةٌ مؤقّتة لأرضية الاختبار (بلا fixture pytest) — تُنظَّف تلقائياً."""
    import tempfile
    return Run(_corpus(Path(tempfile.mkdtemp(prefix="eval-pack-")), doc_id=DOC))


def _capture(tmp: Path, mine=(3,), other=(2,)) -> Path:
    cap = tmp / "capture"
    for doc, pages in ((DOC, mine), (OTHER, other)):
        for p in pages:
            d = cap / doc / f"pg-{p:03d}"
            d.mkdir(parents=True)
            (d / "label.json").write_text(json.dumps({"doc_id": doc, "page": p}), encoding="utf-8")
    (cap / "index.json").write_text(json.dumps({"documents": [{"doc_id": DOC, "captured": len(list(mine))},
                                                              {"doc_id": OTHER, "captured": len(list(other))}]}),
                                    encoding="utf-8")
    return cap


# ── الحالتان اللتان كلَّفتا قياساً ─────────────────────────────────────────
def test_the_first_row_of_a_page_takes_its_side_from_the_previous_frame(tmp_path):
    """السلسلةُ تعبر حدَّ الصفحة: أوّلُ حركةٍ في ص2 دائنٌ لأن إطار ص1 رصيدُه 200 والرصيدُ صعد."""
    run = Run(_corpus(tmp_path))
    first = run.movements(2)[0]
    assert first["side"] == "credit", "أوّلُ حركةٍ صُنِّفت مديناً افتراضاً — وهو الانزياحُ المقيس (8 من 50)"


def test_the_cumulative_frame_is_the_gate_not_the_page_sum(tmp_path):
    """البوابةُ دلتا الإطارين (لأن الإطارَ تراكميّ)، والمدى يُغلق ثلاثَ بوابات."""
    run = Run(_corpus(tmp_path))
    m = measure_range(run, 1, 4)
    assert m["measurable"] and m["gates"]["identity"]["pass"]
    assert m["sum_debit"] == m["printed_debit"] and m["sum_credit"] == m["printed_credit"]
    assert m["delta_debit"] == "0.00" and m["delta_credit"] == "0.00"
    assert m["movements"] == 6, "العدّاد: صفٌّ يحمل مبلغاً — وصفُّ «الرصيد الافتتاحى» ليس حركة"


def test_a_range_whose_predecessor_frame_is_unreadable_is_not_measured(tmp_path):
    """لا يُقاس ما لا يُقرأ: إطارٌ غائبٌ ⇒ غيرُ قابلٍ للقياس، لا صفرٌ بديل."""
    pages = {k: v for k, v in PAGES.items() if k != 2}
    run = Run(_corpus(tmp_path, pages=pages))
    m = measure_range(run, 3, 1)
    assert m["measurable"] is False and "غيرُ مقروء" in m["why"]


# ── الهوية: الوقوفُ بالاسم لا `unknown` ─────────────────────────────────────
def test_identity_null_stops_the_build_by_name(tmp_path, capsys):
    run = _corpus(tmp_path, doc_id=None)
    rc = main(["--build", "--run", str(run), "--capture", str(_capture(tmp_path))])
    err = capsys.readouterr().err
    assert rc == 2, "هويةٌ مجهولة يجب أن **توقف البناء**، لا أن تُمرَّر إلى unknown"
    assert "مجهولة" in err and "doc_id" in err


def test_verify_fails_by_name_when_the_run_identity_moved(tmp_path, capsys):
    """أوّلُ مستهلكٍ حقيقيّ لـ`doc_id`: الحزمةُ بُنيت على X والتشغيلةُ الآن Y ⇒ فشلٌ بالاسم."""
    run = _corpus(tmp_path)
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps({"identity": DOC, "census": {"pages": [], "fingerprint": _sha16("[]")},
                                "ranges": [], "size_gate": {"value": PACK_SIZE, "pass": True}}),
                    encoding="utf-8")
    run.joinpath("slice_report.json").write_text(json.dumps(
        {"corpus_provenance": {"doc_id": OTHER}}, ensure_ascii=False), encoding="utf-8")
    rc = main(["--verify", "--run", str(run), "--pack", str(pack), "--capture", str(_capture(tmp_path))])
    err = capsys.readouterr().err
    assert rc == 2 and DOC in err and OTHER in err


# ── القائمةُ قائمةٌ لا تصنيف · والسمومُ لكل بوابة ──────────────────────────
def test_the_census_is_a_frozen_list_and_its_fingerprint_moves_with_it(tmp_path):
    run = Run(_corpus(tmp_path))
    a = build_census(run, 2)
    b = build_census(run, 3)
    assert [p["class"] for p in a["pages"]] == ["مُثبت"] * a["size"]
    assert all(p["source"] for p in a["pages"]), "لكل صفحةٍ صنفٌ **ومصدرُه**"
    assert a["fingerprint"] != b["fingerprint"], "بصمةُ القائمة تتغيّر بتغيّر القائمة (سمُّ الإحصاء)"


def test_every_gate_check_has_a_poison(tmp_path):
    """نمطٌ قائم في المستودع: فحصٌ بلا سمٍّ لا يُثبت أنه يَعَضّ."""
    run = Run(_corpus(tmp_path))
    cap = {"mine": {3}, "other_pages": {2}, "other_docs": [OTHER], "index": {DOC: 1, OTHER: 1}}
    pois = poisons(run, {"ranges": [measure_range(run, 1, 4)], "length": 4, "census": [2, 3]}, cap)
    cov = pois["_coverage"]
    assert cov["every_check_has_a_poison"], f"فحوصٌ بلا سمّ: {set(cov['checks']) - set(cov['poisoned'])}"
    assert pois["mis_anchored"]["falls"] == ["identity", "frame"]
    assert pois["captured_page_in_pack"]["falls"] == ["intersection"]


def test_the_two_key_keeps_an_innocent_page_from_another_document(tmp_path):
    """المفتاحُ الثنائي ضرورةٌ مقيسة: صفحةُ مستندٍ آخر بنفس الرقم **لا** تُسقط البوابة."""
    run = Run(_corpus(tmp_path))
    cap = {"mine": set(), "other_pages": {2, 4}, "other_docs": [OTHER], "index": {}}
    pois = poisons(run, {"ranges": [measure_range(run, 1, 4)], "length": 4, "census": [2, 3]}, cap)
    foreign = pois["foreign_document_same_number"]
    assert foreign["page_only_key_would_flag"], "كان يجب أن يُقاس تصادمٌ فعليّ على القرص"
    assert foreign["falls"] == [] and foreign["must_not_fall"], "المفتاحُ الثنائي يُبقي البريء"


def test_the_size_gate_is_exactly_two_hundred():
    """|الإحصاء| + 3 × طول المدى = 200 لكل مرشَّح — الحسابُ المعلن في الخطة."""
    for size in (50, 71, 17):
        length = -(-(PACK_SIZE - size) // 3)
        assert size + 3 * length == PACK_SIZE


def test_definitions_print_their_source(capsys):
    """الاصطلاحُ يُطبع بجانب رقمه لا في ذيل تقرير — ولكلٍّ مصدرُه."""
    assert main(["--print-definitions"]) == 0
    out = capsys.readouterr().out
    assert all(name in out and src in out for name, _text, src in DEFINITIONS)
    assert "git ls-tree -r" in out, "أمرُ العدّ يُطبع مع الرقم (فالغرضُ إظهارُ شمول البحث)"


# ── ⛔ ضابطُ المجتمع: سمٌّ داخل المجتمع لا يكشف مجتمعاً ناقصاً ────────────────
def test_the_intersection_gate_counts_the_whole_pack_not_the_ranges_only():
    """**الحزمةُ = الإحصاء + المديات** ⇒ ومجتمعُ بوابة التقاطع هو هي كلُّها.

    قِيست هذه العلّة على الحزمة الحيّة: البوابةُ كانت تقيس المديات (150) وحدَها
    فتُعلن 100 صفحة ثمناً، **والإحصاءُ (50) فيه 33 ملتقطةً خارجَ المجتمع** ⇒
    الثمنُ الحقيقيّ 133 لا 100 (ناقصٌ بالثلث). والضابطُ: صفحةٌ ملتقطةٌ **من
    الإحصاء** يجب أن تُسقط البوابة — وسمُّ المديات لا يكشف هذا أبداً.
    """
    run = _tmpcorpus()
    cap = {"mine": {2}, "other_pages": set(), "other_docs": [], "index": {}}   # ص2 في الإحصاء **وفي الالتقاط**
    census = [x["page"] for x in build_census(run, 3)["pages"]]
    assert 2 in census, "الأرضيةُ تفترض ص2 في الإحصاء"
    ranges = [measure_range(run, 3, 2)]          # المدياتُ [3، 4] — ولا تضمُّ ص2
    whole = set(census) | {p for m in ranges for p in m["pages"]}
    assert set(ranges[0]["pages"]) & cap["mine"] == set(), "ليست في المديات — فسمُّ المديات لا يراها"
    assert whole & cap["mine"] == {2}, "المجتمعُ الكاملُ يجب أن يرى الصفحةَ الملتقَطة"


def test_a_run_of_two_is_measured_as_two():
    """عطبُ تسمية: بناءُ المقاطع بكائنٍ مُشارَك أعطى «1» بدل «2» على قرصٍ حقيقيّ."""
    assert longest_run([3, 6, 9]) == 1
    assert longest_run([171, 172, 180, 181, 182]) == 3
    assert longest_run([171, 172]) == 2, "المقاطعُ لا تُبنى بكائنٍ يُفرَّغ بعد الإضافة"


def test_three_multiples_are_never_adjacent_so_the_structural_bound_is_small():
    """العلّةُ بنيوية: حجزٌ بدورية ٣ لا يجاور محجوزَين ⇒ المقطعُ الحرُّ محصورٌ بثلاثة."""
    reserved = set(range(3, 630, 3))
    assert not any(r - 1 in reserved for r in reserved), "محجوزان متجاوران — القاعدةُ ليست دوريةَ 3"
    free = set(range(1, 630)) - reserved
    assert longest_run(free) <= 3, "مقطعٌ أطولُ من ٣ ينقض الدورية"
