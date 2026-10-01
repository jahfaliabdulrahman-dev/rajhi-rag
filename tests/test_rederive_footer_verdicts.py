"""ضوابطُ `tools/rederive_footer_verdicts.py` — **كوربوسٌ اصطناعيٌّ بالكامل** (بلا كشفٍ ولا شبكة ولا نموذج).

البنيةُ المُعاد استعمالُها من مصنع المشروع نفسه (`tests/test_desc_pass.py::_run`): ثلاثُ صفحاتٍ
متسلسلةُ الرصيد، وتذييلاتُها التراكمية محسوبةٌ بنفس الدالة، و`break_pair` يُفسد تذييلَ صفحةٍ فيُنتج
`mismatch` حقيقيًّا. **ولا تُكتب أشكالُ الكائنات بيد** — تُبنى بدوالّ المنتج (`chain_derive` ·
`page_totals`) وتُسلسَل بـ…raw_rows كما يفعل الكاش.

**والبندُ المقيس هو قانونُ الأداة:** الخلافُ مع المُجمَّد **مقبولٌ فقط** إذا كان في الكاش سجلُّ تحكيمٍ
يفسّره؛ وإلّا فالأداةُ **تتوقف** (خروج ١) — لأنّ فرقًا بلا مفسِّر عطبٌ لا ملاحظة. والأربعةُ أدناه
ضابطٌ موجبٌ وضابطٌ سالبٌ (سمٌّ) وسجلُّ تحكيمٍ يُفسِّر، وقياسٌ متعذّرٌ يفشل مُغلَقًا.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from statement_qa.footer_oracle import page_totals  # noqa: E402
from statement_qa.vlm_reader import chain_derive  # noqa: E402
from tools.rederive_footer_verdicts import main, page_verdicts, reconcile  # noqa: E402

VERDICTS = ("ok", "mismatch", "unchecked", "absent", "gap", "cache-error")


def _run(tmp_path: Path, pages: int = 3, break_pair: int | None = None) -> Path:
    """تشغيلةٌ اصطناعية: تذييلاتٌ تراكميةٌ مطابقةٌ للصفوف، و`break_pair` يُفسد تذييلَ صفحة."""
    run = tmp_path / "data" / "local_sample" / "run"
    (run / "results").mkdir(parents=True)
    bal, prev, cum_d, cum_c = Decimal("8413.29"), None, Decimal("0"), Decimal("0")
    for pg in range(1, pages + 1):
        raw = []
        for j in range(3):
            bal -= Decimal("12.34")
            raw.append({"movement": "12.34", "balance": str(bal), "desc": f"حركة {pg}-{j}",
                        "date": "٢٠٢٤٠١٠١", "raw_movement": "12.34", "raw_balance": str(bal)})
        derived = chain_derive([{**r, "movement": Decimal(r["movement"]),
                                 "balance": Decimal(r["balance"])} for r in raw], prev_balance=prev)
        t = page_totals(derived)
        prev = t["balance"]
        cum_d, cum_c = cum_d + t["debits"], cum_c + t["credits"]
        footer = {"debits": str(cum_d + (Decimal("5") if pg == break_pair else 0)),
                  "credits": str(cum_c), "balance": str(bal)}
        (run / "results" / f"pg-{pg:03d}.json").write_text(
            json.dumps({"pg": pg, "page_no": pg, "raw_rows": raw, "footer": footer},
                       ensure_ascii=False), encoding="utf-8")
    derived_verdicts = page_verdicts(run)
    (run / "slice_report.json").write_text(json.dumps(
        {"per_page": [{"page": pg, "footer": derived_verdicts[pg]["status"]} for pg in sorted(derived_verdicts)]},
        ensure_ascii=False), encoding="utf-8")
    return run


def _freeze(run: Path, page: int, verdict: str) -> None:
    """يُزحزح حكمَ صفحةٍ في التقرير المُجمَّد — محاكاةُ «التقرير يقول غيرَ ما يقول الكاش»."""
    rep = json.loads((run / "slice_report.json").read_text(encoding="utf-8"))
    for row in rep["per_page"]:
        if row["page"] == page:
            row["footer"] = verdict
    (run / "slice_report.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")


def _arbitrate(run: Path, page: int, field: str, new: str) -> None:
    """سجلُّ تحكيمٍ في الكاش نفسِه — بالحقول الإلزاميّة كما يكتبها `tools/arbitrate_footer.py`."""
    cache = run / "results" / f"pg-{page:03d}.json"
    data = json.loads(cache.read_text(encoding="utf-8"))
    old = data["footer"][field]
    data["footer"][field] = new
    data.setdefault("arbitrated_by", []).append({
        "by": "المالك", "why": "قياسٌ اصطناعيٌّ لضابط الأداة",
        "at": "2026-10-01T00:00:00+00:00", "field": field,
        "old_value": old, "new_value": new})
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ————————————————————— ١ · ضابطٌ موجب: الكاشُ والمُجمَّد مُتّفقان —————————————————————

def test_a_clean_run_reconciles_with_no_divergence(tmp_path, capsys):
    """لا فرقَ ⇒ لا إنذار: الأداةُ لا تخلق اعتراضًا حين لا فرق (ضابطٌ موجبٌ صريح)."""
    run = _run(tmp_path)
    r = reconcile(run)
    assert r["diverged"] == {} and r["unexplained"] == {}, r
    assert r["reproduced"] == r["pages"] == 3
    assert r["tally"] and set(r["tally"]) <= set(VERDICTS)
    assert main(["--run", str(run)]) == 0
    assert "PASS" in capsys.readouterr().out


# ————————————————————— ٢ · سمّ: فرقٌ بلا مفسِّر يُوقف الأداة —————————————————————

def test_an_unexplained_divergence_blocks(tmp_path, capsys):
    """**العطبُ الذي وُجدت الأداةُ من أجله:** رقمٌ في التقرير لا يوافق الكاشَ بلا سجلّ تحكيم ⇒ خروج ١."""
    run = _run(tmp_path)
    frozen_before = page_verdicts(run)[2]["status"]
    _freeze(run, 2, "ok" if frozen_before != "ok" else "mismatch")
    r = reconcile(run)
    assert 2 in r["diverged"] and 2 in r["unexplained"], r
    assert r["diverged"][2]["arbitrated"] is False
    assert main(["--run", str(run)]) == 1
    assert "بلا تحكيم" in capsys.readouterr().out


# ————————————————————— ٣ · السجلُّ يُفسِّر الفرق — والحكمُ ينقلب قياسًا —————————————————————

def test_an_arbitrated_footer_flips_the_verdict_and_explains_the_difference(tmp_path, capsys):
    """**وهذا هو الغرضُ كلُّه:** تحكيمٌ بشريٌّ يصحّح رقمًا مطبوعًا ⇒ حكمُ الصفحة ينقلب من
    `mismatch` إلى `ok`، والفرقُ مع التقرير المُجمَّد يصير **مفسَّرًا** فيمرّ الفحص."""
    run = _run(tmp_path, break_pair=2)
    before = page_verdicts(run)[2]["status"]
    assert before == "mismatch", f"المصنعُ يفترض تذييلَ الصفحة ٢ مُفسَدًا (جاء {before})"
    _freeze(run, 2, "mismatch")                       # التقريرُ المُجمَّد يحمل الحكمَ القديم
    assert reconcile(run)["unexplained"] == {}        # لا فرقَ بعد ⇒ نظيف

    # القيمةُ الصحيحة = التذييلُ **التراكميّ** بعد الصفحة ٢ = تذييلُ ص١ (سليم) + مجموعُ صفوف ص٢
    p1 = json.loads((run / "results" / "pg-001.json").read_text(encoding="utf-8"))["footer"]
    own2 = page_totals(chain_derive(
        [{**r, "movement": Decimal(r["movement"]), "balance": Decimal(r["balance"])}
         for r in json.loads((run / "results" / "pg-002.json").read_text(encoding="utf-8"))["raw_rows"]],
        prev_balance=Decimal("8413.29") - Decimal("12.34") * 3))
    _arbitrate(run, 2, "debits", str(Decimal(p1["debits"]) + own2["debits"]))

    after = page_verdicts(run)[2]["status"]
    assert after == "ok", f"التحكيمُ لم يقلب الحكم (جاء {after})"
    # **والأثرُ ينتقل إلى الجار بأساس الدلتا** — سلوكٌ مقيسٌ لا عطب: تذييلُ ص٢ صار صحيحًا،
    # فدلتا ص٣ (تذييل ٢ ← تذييل ٣) صارت مطابقةً أيضًا.
    assert page_verdicts(run)[3]["status"] == "ok", "أثرُ التحكيم لا ينتقل إلى الجار"
    _freeze(run, 3, "ok")                             # فيُعاد تجميدُ الجار على حكمه الصحيح
    r = reconcile(run)
    assert r["diverged"][2] == {"frozen": "mismatch", "recomputed": "ok", "arbitrated": True}
    assert r["unexplained"] == {}, r
    assert main(["--run", str(run)]) == 0
    assert "تحكيمٌ مسجَّل" in capsys.readouterr().out


# ————————————————————— ٤ · تعذّرُ القياس يفشل مُغلَقًا —————————————————————

def test_an_unmeasurable_run_exits_two_not_zero(tmp_path, capsys):
    """لا كاشَ ⇒ لا قياس. والغيابُ ليس نظافة: الخروجُ ٢ لا ٠."""
    empty = tmp_path / "لا-كاش"
    empty.mkdir()
    assert main(["--run", str(empty)]) == 2
    assert "تعذّرُ القياس" in capsys.readouterr().err


def test_the_tool_reads_only_and_never_touches_the_cache(tmp_path):
    """الأداةُ قارئة: لا تكتب في الكاش ولا في التقرير المُجمَّد (تُقاس البايتاتُ قبل وبعد)."""
    run = _run(tmp_path)
    before = {f.name: f.read_bytes() for f in sorted((run / "results").glob("pg-*.json"))}
    before["slice_report.json"] = (run / "slice_report.json").read_bytes()
    main(["--run", str(run)])
    after = {f.name: f.read_bytes() for f in sorted((run / "results").glob("pg-*.json"))}
    after["slice_report.json"] = (run / "slice_report.json").read_bytes()
    assert after == before, "أداةُ قياسٍ عدّلت ما تقيسه"
