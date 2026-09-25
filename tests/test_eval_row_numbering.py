"""رقمُ الصفّ **بترقيم النظام** — الضابطُ الذي كان يجب أن يميّز الفرضيّتين.

**الدرسُ المدفوع (REVIEW-48 · P-1):** قاعدةُ حُكمٍ تقبل ترقيمَ الصفحة وترفض ترقيمَ الكشف، وضابطُها
التسعةَ عشرَ لم يكشفها لأنّ صفحةَ الضابط كانت **الأولى** في بياناتها ⇒ الترقيمان يتطابقان فيها.
الضابطُ الذي لا يميّز بين الفرضيّتين ليس ضابطاً — فهذا الملفّ يبني أرضيّةً **يتأكّد فيهما أنهما مختلفان**
(`assert` صريح)، ويبني الجوابَ بدالّة النظام نفسها (`qa_tools._ref` على مخرَج `_number_rows`).

والأرضيّةُ تحمل عطباً ثانياً مقصوداً: صفٌّ لا يُشتقّ رصيدُه ⇒ `build_rows` **يُسقطه** ⇒ ترقيمُ السلسلة
ينزاح عن ترقيم قارئ الحزمة ⇒ أيُّ مطابقةٍ تعتمد على الفهرس الخامّ تُخطئ الصفحةَ والمبلغ.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


def _load():
    spec = importlib.util.spec_from_file_location("eval_questions", ROOT / "tools" / "eval_questions.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eq = _load()


def _mini_run(tmp: pathlib.Path) -> pathlib.Path:
    run = tmp / "run"
    (run / "results").mkdir(parents=True)
    rows = {
        1: [("1.00", "1.00"), ("2.00", "3.00")],
        # الثاني في الصفحة ٢ لا حركةَ ولا رصيدَ له ⇒ `build_rows` يُسقطه (وهذا ما يجعل الترقيمين يفترقان)
        2: [("3.00", "6.00"), ("", "")],
        3: [("4.00", "10.00"), ("9.00", "19.00"), ("1.00", "20.00")],
    }
    for p, rs in rows.items():
        (run / "results" / f"pg-{p:03d}.json").write_text(json.dumps(
            {"pg": p, "raw_rows": [{"date": "01/01/2022", "desc": "x", "movement": m, "balance": b}
                                   for m, b in rs]}, ensure_ascii=False))
    return run


def _chain(run: pathlib.Path) -> list[dict]:
    """عالمُ الصفوف الواحد كما تُبنيه السلسلةُ فعلاً: `build_rows` ثم ترقيمُ `qa_tools`."""
    from statement_qa import qa_tools
    from tools import refusal_test as rt

    return qa_tools._number_rows(rt.build_rows(run)[0])


def _argmax_q(page: int) -> dict:
    return {"id": "t", "cat": "استشهاد", "metric": "citation", "expect": "row_index", "q": "؟",
            "derive": {"kind": "argmax_row", "page": page}}


def test_the_fixture_really_separates_the_two_numberings(tmp_path):
    """**حجرُ الأساس**: لو تطابق الترقيمان لكان هذا الملفُّ أعمى كسابقه."""
    from statement_qa import qa_tools
    from tools import refusal_test as rt

    run = _mini_run(tmp_path)
    chain = qa_tools._number_rows(rt.build_rows(run)[0])
    tops_chain = [r["row_no"] for r in chain if r["page"] == 3 and r["movement"] == 9.0]
    corpus = eq.Corpus(run, [])
    local = [i + 1 for i, r in enumerate(corpus.rows(3)) if r.get("movement") == "9.00"]
    assert tops_chain == [5], tops_chain
    assert local == [2], local
    assert tops_chain != local, "الأرضيّةُ يجب أن تفصل الترقيمين"


def test_truth_reports_the_system_row_number(tmp_path):
    """الحقيقةُ تُعرّف هويّةَ الصفّ **كما تراه الأدوات** (‏`(صفحة N، صف row_no)`)."""
    run = _mini_run(tmp_path)
    c = eq.Corpus(run, [])
    tv, _ = eq.truth(_argmax_q(3), c, {}, _chain(run))
    assert tv["tops"] == [5], tv          # ٥ = ترقيمُ الكشف بعد إسقاط صفٍّ من الصفحة ٢، لا ٢ ولا ٦
    assert tv["amount"] == 9.0


def test_a_correct_answer_built_with_the_tools_passes(tmp_path):
    """**الضابطُ الموجب**: جوابٌ بصيغة النظام نفسها (`qa_tools._ref`) يجب أن يُقبَل."""
    from statement_qa import qa_tools
    from tools import refusal_test as rt

    run = _mini_run(tmp_path)
    chain = qa_tools._number_rows(rt.build_rows(run)[0])
    top = next(r for r in chain if r["row_no"] == 5)
    ans = f"أكبر مبلغ 9.00 ريال في {qa_tools._ref(top)} (الحركةُ دائنة)"
    c = eq.Corpus(run, [])
    tv, _ = eq.truth(_argmax_q(3), c, {}, _chain(run))
    ok, why = eq.score_answer(_argmax_q(3), tv, ans, eq._Trace({"used_row_nos": [5]}), chain)
    assert ok, why


def test_the_row_before_the_top_is_rejected(tmp_path):
    """**الضابطُ السالب (S-5)**: الصفُّ **قبل** القمّة يجب أن يُرفض — والقاعدةُ كانت تمرّره."""
    run = _mini_run(tmp_path)
    c = eq.Corpus(run, [])
    tv, _ = eq.truth(_argmax_q(3), c, {}, _chain(run))
    ok, why = eq.score_answer(_argmax_q(3), tv, "أكبر مبلغ 9.00 ريال في (صفحة 3، صف 4)",
                              eq._Trace({"used_row_nos": [4]}), [{"row_no": 4, "page": 3, "movement": 900.0}])
    assert not ok, why


def test_trace_maps_to_pages_with_the_system_numbering(tmp_path):
    """الأثرُ ترقيمُه ترقيمُ السلسلة ⇒ تحويلُه إلى صفحاتٍ يجب أن يستعمل نفسَ العالم (وإلّا أخطأ الصفحة)."""
    from statement_qa import qa_tools
    from tools import refusal_test as rt

    run = _mini_run(tmp_path)
    chain = qa_tools._number_rows(rt.build_rows(run)[0])
    c = eq.Corpus(run, [])
    tv, _ = eq.truth(_argmax_q(3), c, {}, _chain(run))
    ans = "أكبر مبلغ 9.00 ريال في (صفحة 3، صف 5)"
    ok, why = eq.score_answer(_argmax_q(3), tv, ans, eq._Trace({"used_row_nos": [5]}), chain)
    assert ok and "3" in why, why
