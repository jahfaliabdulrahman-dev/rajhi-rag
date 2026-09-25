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
import pytest
import re
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.eval_pack import (  # noqa: E402
    CLASS_SOURCES, DEFINITIONS, GATE3_DECISION, PACK_SIZE, Run, _sha16, build_census,
    census_classes, gate3_closed, longest_run, main, measure_range, poisons, classify_verdict,
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


def _chain(n: int) -> dict:
    """أرضيةٌ صناعيةٌ بسلسلة أرصدةٍ متّصلة: كلُّ صفحةٍ تُقفل سلاسلَها ⇒ إحصاءٌ مكتمل."""
    pages, bal, td, tc = {}, 1000, 0, 0
    for k in range(1, n + 1):
        c, d = 10 * k, 4 * k                       # دائنٌ ثم مدينٌ ⇒ الاتجاهاتُ من سلسلة الأرصدة
        pages[k] = ([(f"{c}.00", f"{bal + c}.00"), (f"{d}.00", f"{bal + c - d}.00")],
                    {"debits": f"{td + d}.00", "credits": f"{tc + c}.00", "balance": f"{bal + c - d}.00"})
        bal += c - d; td += d; tc += c
    return pages


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
            (d / "label.json").write_text(json.dumps(
                {"doc_id": doc, "page": p, "rows": [{"amount": "1.00"}, {"amount": "2.00"}]},
                ensure_ascii=False), encoding="utf-8")
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
def test_the_population_control_calls_the_real_build_and_falls(tmp_path, capsys):
    """**شرطُ review-33 §٦/١:** الضابطُ يستدعي البوابةَ نفسَها — لا يُعيد بناء المنطق.

    العلّةُ التي أُصلحت: مجتمعُ التقاطع كان المديات وحدَها والإحصاءُ خارجَه. فالضابطُ
    يبني أرضيةً صفحتُها الملتقَطة **في الإحصاء فقط**، ثم **يُنادي `--build` الحقيقيّ**
    ويقيس مخرَجَه. ومعيارُ القبول (المُقاس في تحضير التسليم): بإعادة حقن العلّة —
    `pack_pages = المديات` — **يسقط هذا الاختبار**. وضابطٌ لم يُجرَّب سقوطُه ليس حارساً.
    """
    run = _corpus(tmp_path, pages=_chain(630))
    cap = _capture(tmp_path, mine=(5,), other=(600,))     # ص5 ملتقطة — وهي **في الإحصاء** (1..50)
    _rc = main(["--build", "--run", str(run), "--capture", str(cap),
                "--out", str(tmp_path / "out"), "--census", "50", "--capture-mode", "explicit-list"])
    assert _rc != 0, "الحكمُ يجب أن يكون FAIL بالاسم — والباقي يُقاس في السطر التالي"
    out = capsys.readouterr().out
    assert "بوابة التقاطع" in out, "الأمرُ الحقيقيُّ لم يُنادَ — لا مخرَجَ بوابة"
    assert "إحصاء 50" in out, "المجتمعُ المطبوعُ يجب أن يُشتقّ من المقيس (وفيه الإحصاء)"
    assert _rc != 0, "صفحةٌ ملتقطةٌ في الإحصاء فقط يجب أن تُسقط بوابةَ التقاطع"
    assert "intersection" in out, "السقوطُ يجب أن يكون بالاسم على بوابة التقاطع"
    # والمجتمعُ المطبوعُ = المقيس (فلا يُطبع عددٌ ويُقاس آخر)
    m = re.search(r"مجتمعُها الحزمةُ كاملةً: (\d+) = إحصاء (\d+) \+ مديات (\d+)", out)
    assert m, "سلسلةُ المجتمع غير مشتقّة"
    whole, census_pages, range_pages = (int(x) for x in m.groups())
    assert whole == census_pages + range_pages == 200, "المجتمعُ المطبوع ≠ مجموع مكوّناته"


def test_the_build_runs_the_population_to_the_line_it_prints(tmp_path, capsys):
    """سمُّ الطباعة: نسبةُ الإحصاء في المجتمع المطبوع تُقاس — لا تُكتب."""
    run = _corpus(tmp_path, pages=_chain(630))
    main(["--build", "--run", str(run), "--capture", str(_capture(tmp_path)),   # الحكمُ يُقاس أدناه
          "--out", str(tmp_path / "out2"), "--census", "50"])
    out = capsys.readouterr().out
    m = re.search(r"مجتمعُها الحزمةُ كاملةً: (\d+) = إحصاء (\d+) \+ مديات (\d+)", out)
    assert m, "المجتمعُ يجب أن يُطبع بالاشتقاق"
    whole, census_pages, range_pages = (int(x) for x in m.groups())
    assert whole == census_pages + range_pages, "عددُ المجتمع ≠ مجموع مكوّناته"


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


# ── أصنافُ الإحصاء: تُقاس من القرص، والمُجمَّعُ يُعلن ولا يُخمَّن ─────────────
def test_every_class_declares_where_it_is_measured():
    """لا تصنيفَ بلا مُسند: كلُّ صنفٍ يحمل ملفَّه وحقلَه."""
    assert set(CLASS_SOURCES) == {
        "بلا إطار", "بلا صفوف", "مرقّمة مطبوعاً", "فجوة", "غير محسومة",
        "استدراك مرساة", "إعادة قراءة", "تحكيم", "قراءة مستبدلة", "رقمٌ من خارج الصفحة"}
    for name, src in CLASS_SOURCES.items():
        assert "results/pg-*.json" in src or "slice_report" in src, f"{name} بلا مُسند"


def test_the_classes_are_counted_from_the_pages_that_carry_them():
    run = _tmpcorpus()
    # أعلامٌ على القرص: ص3 بلا إطار، ص4 بلا صفوف، وص3 وص4 فيهما إعادةُ قراءة
    for pg, extra in ((3, {"reread": "جولة"}), (4, {"recovered": "1.00"})):
        f = run.dir / "results" / f"pg-{pg:03d}.json"
        d = json.loads(f.read_text(encoding="utf-8"))
        if pg == 3:
            d.pop("footer", None)
        if pg == 4:
            d["raw_rows"] = []
        d.update(extra)
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    comp = census_classes(run)
    assert comp["classes"]["بلا إطار"]["count"] == 1
    assert comp["classes"]["بلا صفوف"]["count"] == 1
    assert comp["classes"]["إعادة قراءة"]["count"] == 1
    assert comp["classes"]["استدراك مرساة"]["count"] == 1
    assert comp["classes"]["تحكيم"]["count"] == 0


def test_a_class_without_a_page_list_on_disk_is_declared_aggregate_not_zero():
    """`checked` و`unchecked` مُجمَّعان في التقرير ⇒ يُعلنان، ولا يُحسبان صفراً ولا يُخمَّنان."""
    run = _tmpcorpus()
    rep = json.loads((run.dir / "slice_report.json").read_text(encoding="utf-8"))
    rep.setdefault("page_numbers", {})["checked"] = 7
    rep.setdefault("footer", {})["unchecked"] = 2
    (run.dir / "slice_report.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
    comp = census_classes(run)
    assert comp["classes"]["مرقّمة مطبوعاً"]["count"] == 7
    assert comp["classes"]["مرقّمة مطبوعاً"]["listed"] is False
    assert set(comp["aggregate_only"]) == {"مرقّمة مطبوعاً", "غير محسومة"}, \
        "المُجمَّعُ بلا قائمةٍ يُعلن نفسَه؛ والصنفُ الفارغُ ليس مُجمَّعاً"
    assert comp["aggregate_only_upper_bound"] >= comp["structural_union"]
    assert "المجموعُ" in comp["plan_claim_22"] or "يُعاد" in comp["plan_claim_22"]


def test_a_price_with_no_rows_is_declared_unknown_not_zero(tmp_path, capsys):
    """مقامٌ صفريٌّ ⇒ **مجهولة** لا صفر: عطبُ `ZeroDivisionError` كشفه الضابطُ الحقيقيّ."""
    run = _corpus(tmp_path, pages=_chain(630))
    d = tmp_path / "capture" / DOC / "pg-005"
    d.mkdir(parents=True)
    (d / "label.json").write_text(json.dumps({"doc_id": DOC, "page": 5}), encoding="utf-8")
    rc = main(["--build", "--run", str(run), "--capture", str(tmp_path / "capture"),
               "--out", str(tmp_path / "out3"), "--census", "50", "--capture-mode", "explicit-list"])
    out = capsys.readouterr().out
    assert "مجهولة" in out, "نسبةٌ بمقامٍ صفريّ تُعلن مجهولةً"
    assert rc in (0, 1, 2), "ولا انفجار: المسارُ يكمل إلى الحكم"
    assert "الحكم" in out, "المسارُ ينتهي بحكمٍ معلن لا بانفجار"


def test_the_verdict_separates_an_owner_condition_from_our_own_defect():
    """التصنيفُ نافعٌ فقط إن منع العطبَ من التخفّي في «شرطيٌّ» — وهذا هو الاختبار."""
    assert classify_verdict(ok=True, inter=[], blockers=[], remedy_rows=0).startswith("PASS")
    only_condition = classify_verdict(ok=False, inter=[52, 53], blockers=[], remedy_rows=1253)
    assert "شرطيٌّ" in only_condition and "1253" in only_condition
    with_defect = classify_verdict(ok=False, inter=[52], blockers=["بواباتُ المديات"], remedy_rows=9)
    assert "عطبٌ" in with_defect and "شرطيٌّ" not in with_defect
    assert "غيرُ مُصنَّف" in classify_verdict(ok=False, inter=[], blockers=[], remedy_rows=0)


def test_gate3_decision_is_dated_bounded_and_declared():
    """قرارُ المالك لا يُقبل كائناً بلا **تاريخ** وبلا **سقفٍ معلَن** — وإلا صار عرفاً سائباً."""
    assert GATE3_DECISION["date"] and GATE3_DECISION["accepted_pages"] > 0, \
        "قرارٌ بلا تاريخٍ أو بلا سقفٍ ليس قراراً"
    assert "لا يُغطّي عطباً" in GATE3_DECISION["limits"], "الحدُّ الحاكم يُصرَّح به في القرار نفسه"
    assert GATE3_DECISION["scope"], "بلا مجتمعٍ معلَن لا يُقاس التقاطعُ على من يقع"


def test_the_owner_decision_closes_the_intersection_only_within_its_ceiling():
    """القرارُ يُغلق بندَ التقاطع **داخل سقفه**، ولا يتمدّد ولا يُغطّي عطباً — والثلاثةُ تُقاس."""
    ceiling = GATE3_DECISION["accepted_pages"]
    inside = classify_verdict(ok=False, inter=list(range(1, 11)), blockers=[], remedy_rows=1253,
                              decision=GATE3_DECISION)
    assert inside.startswith("PASS") and GATE3_DECISION["date"] in inside, \
        "داخلَ السقف: PASS بتاريخ القرار لا PASS صامت"
    assert str(ceiling) in inside, "والسقفُ يُطبع مع الحكم"
    over = classify_verdict(ok=False, inter=list(range(1, ceiling + 2)), blockers=[], remedy_rows=1253,
                            decision=GATE3_DECISION)
    assert "شرطيٌّ" in over and "لا يتمدّد" in over, "فوق السقف: يعود شرطيًّا — القرارُ لا يتمدّد"
    # **الفخُّ الذي أغلقه ترتيبُ الفروع** (مقعدُ البنية): نداءٌ يُمرّر `ok=True` مع تقاطعٍ غيرِ
    # مُغلقٍ كان يقول «PASS — قطعت بواباتها» ⇒ السلامةُ كانت من المُنادي لا من الدالّة.
    assert "قطعت بواباتها" not in classify_verdict(ok=True, inter=[52], blockers=[], remedy_rows=9), \
        "تقاطعٌ بلا قرارٍ لا يُقرأ «PASS — قطعت بواباتها» ولو قال المُنادي ok=True"
    assert gate3_closed(inter=[], blockers=[], decision=GATE3_DECISION) is False, \
        "بلا تقاطع لا يوجد ما يُغلق: الحالةُ «مُغلَقةٌ بلا تقاطع» لا «مُغلَقةٌ بقرار»"
    assert gate3_closed(inter=[1, 2], blockers=[], decision=None) is False, \
        "بلا قرارٍ يبقى الحكمُ شرطيًّا («القرارُ للمالك»)"
    assert gate3_closed(inter=[1, 2], blockers=["x"], decision=GATE3_DECISION) is False, \
        "الحدُّ ① يُقاس في الدالّة نفسها لا في النصّ"


def test_the_recorded_decision_cannot_rot_on_disk():
    """**القرارُ المُلتزم في الحزمة يُقابَل بمصدره** — فإن تغيّر القرارُ (تاريخاً أو سقفاً) بقي
    `pack.json` قديماً فيُكشَف بدل أن يُقرأ قراراً سارياً. (تُتخطّى حيث لا حزمةَ على القرص: `data/` مستثنى.)"""
    pack_path = PROJ / "data" / "eval_pack" / "pack.json"
    if not pack_path.exists():
        pytest.skip("لا حزمةَ على القرص (data/ مستثنى) — المقابلةُ تُجرى في شجرة العمل")
    rec = ((json.loads(pack_path.read_text(encoding="utf-8")).get("intersection_gate") or {})
           .get("owner_decision") or {})
    drifted = [k for k, v in GATE3_DECISION.items() if rec.get(k) != v]
    assert not drifted, f"قرارُ الحزمة قديمٌ في {drifted} ⇒ يُعاد `tools/eval_pack.py --build`"
    measured = rec.get("measured_intersection")
    assert isinstance(measured, int) and 0 <= measured <= GATE3_DECISION["accepted_pages"], \
        "المقيسُ يُقيَّد بسقف القرار (`--verify` يقابله بالتقاطع الحيّ — لا يُجمَّد على صفرٍ فيُكلّف إصلاحاً كاذباً)"


def test_a_drifted_pack_fails_the_real_verify_with_a_named_reason(tmp_path, capsys):
    """**الضابطُ ينادي الأمرَ نفسَه على حزمةٍ مُجرَّبة** — لا يُعيد بناء منطق المقابلة (وإلّا لأخفى
    العطبَ الذي أظهره مقعدا المعايير والبنية · مراجعة ٦٠): حزمةٌ تُوسّع سقفَها بنفسها يجب أن تُسقط
    `--verify` بـ`rc=1` وباسمٍ مطبوع — لا أن تطبع «مخالفٌ ⇒ يُعاد `--build`» ثمّ «PASS».

    والأرضيّةُ فيها **الشاهدُ المضادّ** في الضابط نفسه: القرارُ الصحيح ⇒ `rc=0`؛ وإلّا فالأرضيّةُ لا
    تُفرّق بين الفرضيّتين فلا تُثبت شيئاً.
    """
    run = _corpus(tmp_path)
    cap = _capture(tmp_path)

    def _verify_with(decision: dict, tag: str) -> tuple[int, str]:
        pack = tmp_path / f"pack-{tag}.json"
        pack.write_text(json.dumps({
            "identity": DOC, "census": {"pages": [{"page": 1}], "size": 1, "fingerprint": _sha16("[{\"page\": 1}]")},
            "ranges": [], "size_gate": {"value": 1, "pass": True},
            "intersection_gate": {"pass": True, "owner_decision": decision}}), encoding="utf-8")
        rc = main(["--verify", "--run", str(run), "--pack", str(pack), "--capture", str(cap)])
        return rc, capsys.readouterr().out

    honest = {**GATE3_DECISION, "measured_intersection": 0}
    _, out_ok = _verify_with(honest, "honest")
    assert "يخالف قرارَ الأداة" not in out_ok, \
        "الشاهدُ المضادّ: الأرضيّةُ نفسُها بقرارٍ مطابقٍ لا تُنتج مخالفةً ⇒ فالضابطُ يقيس الانحرافَ لا الأرضيّة"
    rc, out = _verify_with({**GATE3_DECISION, "accepted_pages": 9999, "measured_intersection": 0},
                           "drifted")
    assert rc == 1, f"حزمةٌ مُحرَّفة ⇒ `rc=1` لا `rc={rc}` (وهو ما يَعِد به صفُّ السجلّ ١٥)"
    assert "يخالف قرارَ الأداة" in out and "الحكم: PASS" not in out, \
        "المخالفةُ تُسمّى في `failures` ولا تُختم بـPASS"
