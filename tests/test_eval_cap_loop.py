"""ضابطٌ **سلوكيّ** لحلقة السقف — يشغّل `run_questions` نفسَها بمزوّدٍ مُحاكى (صفرُ صرف) ويسأل:

    هل توقّفت الحلقة؟ وأين؟ وبأيّ رمز خروج؟

مراجعة ٥١ · البند «قبل أي صرف»: «ضابطاه يفحصان الدالة ونص المصدر **لا التوقف**. رفعتُ عتبة التوقف ألف
ضعف فبقيت الاختبارات الـ٦٠٨ خضراء.» ⇒ هذا الملفّ يقيس **التوقّفَ في الحلقة**، ويرسب إذا رُفعت العتبة
أو نُزع `break` أو صار التوقّفُ يُعاد بـ0. (الاختبارُ لا يمسّ الشبكة: كلُّ نداءات المزوّد مُستبدَلة.)
"""

import importlib.util
import json
import pathlib
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Meter:
    """عدّادُ مزوّدٍ مُحاكى: يُقرأ **قبل كلّ سؤال**، وكلفةُ كلّ نداءٍ `per_call`، ويتأخّر `lag` نداءً."""

    def __init__(self, per_call: float, lag: int = 0, reverse: bool = False):
        self.per_call, self.lag, self.reverse, self.calls = per_call, lag, reverse, 0

    def read(self):
        shown = max(0, self.calls - self.lag) * self.per_call
        if self.reverse:
            shown = -abs(shown)
        return {"usage": shown, "limit": 999.0}


class _Ans:
    answer, used_row_nos, scope, refused = "جوابٌ مُحاكى", [1], "ok", False


def _questions_file(tmp_path) -> pathlib.Path:
    """ملفُّ أسئلةٍ صغيرٌ في `tmp` — فلا يُتخطّى الضابطُ أبدًا (ضابطٌ متخطّى ثقب، لا ضابط)."""
    p = tmp_path / "questions.json"
    p.write_text(json.dumps({"questions": [{"id": f"q{i:02d}", "q": f"س{i}", "type": "count_rows",
                                            "cat": "count", "metric": "مُحاكى", "expect": "…",
                                            "derive": {"kind": "mock"}} for i in range(1, 9)]},
                            ensure_ascii=False), encoding="utf-8")
    return p


def _run(tmp_path, monkeypatch, meter: _Meter, budget: float, n: int = 8):
    m = _load("evalq_cap_loop", "tools/eval_questions.py")
    import tools.refusal_test as rt
    from statement_qa import chunking, qa, retriever

    monkeypatch.setattr(rt, "build_rows", lambda run: ([{"row_no": 1, "text": "س", "page": 1}], 1))
    monkeypatch.setattr(chunking, "chunk_rows", lambda rows: [{"text": "س", "row_no": 1}])
    monkeypatch.setattr(retriever, "build_index", lambda chunks: object())
    monkeypatch.setattr(qa, "build_llm", lambda model=None: None)

    def _answer(store, qtext, rows=None, chunks=None, llm=None):
        meter.calls += 1                     # الكلفةُ تُحتسب عند النداء — كما يفعل المزوّد
        return _Ans()

    monkeypatch.setattr(qa, "answer_question", _answer)
    monkeypatch.setattr(m, "_key_usage", meter.read)
    monkeypatch.setattr(m, "truth", lambda q, c, pack, rows: ({"kind": "مُحاكى"}, "مُحاكى"))
    monkeypatch.setattr(m, "score_answer", lambda q, t, ans, res, rows: (True, "ok"))
    qs = [{"id": f"q{i:02d}", "q": f"س{i}", "type": "count_rows", "cat": "count", "metric": "مُحاكى",
           "expect": "…", "derive": {"kind": "mock"}} for i in range(1, n + 1)]
    a = types.SimpleNamespace(
        run=ROOT / "data/local_sample/slice_629p", model=None, out=tmp_path / "answers.json",
        budget=budget, timeout=5, only=None, questions=_questions_file(tmp_path), rescore=False, execute=False)
    rc = m.run_questions(a, qs, None, {}, {})
    out = tmp_path / "answers.json"
    saved = json.loads(out.read_text()) if out.exists() else {}
    return rc, saved.get("results", [])


def test_the_cap_stops_the_loop_with_an_instant_meter(tmp_path, monkeypatch):
    """$0.60 بـ$0.30/السؤال ⇒ **سؤالان لا أكثر**، ورمزُ خروجٍ غيرُ صفريّ (3)."""
    rc, results = _run(tmp_path, monkeypatch, _Meter(0.30), 0.60)
    assert len(results) == 2, f"لم تتوقّف الحلقة عند السقف: طُرح {len(results)} سؤالاً"
    assert rc == 3, f"التوقّفُ بالسقف يجب أن يُقرأ رمزًا غيرَ صفريّ لا {rc}"


def test_the_cap_bound_with_a_lagging_meter_is_the_declared_one(tmp_path, monkeypatch):
    """عدّادٌ متأخّرٌ نداءً واحدًا ⇒ **ثلاثةُ نداءات** (٠٫٩٠ من ٠٫٦٠) — وهذا **الحدُّ المُعلَن**:
    التجاوزُ الأقصى = (التأخّر + ١) نداءً. الاختبارُ يقيسه ليَرسُب لو انفتح السقف (كان ٨) أو انسدّ تمامًا."""
    rc, results = _run(tmp_path, monkeypatch, _Meter(0.30, lag=1), 0.60)
    assert len(results) == 3, f"التأخّرُ نداءً واحدًا يجب أن يسمح بنداءٍ زائدٍ واحدٍ لا {len(results)}"
    assert rc == 3, f"رمزُ الخروج {rc}: التوقّفُ يجب أن يُعلَن"


def test_a_reverse_meter_halts_and_does_not_read_as_success(tmp_path, monkeypatch):
    """عدّادٌ تراجعيّ ⇒ **وقوفٌ مُسمّى برمز 4**، ولا يُقرأ «نجاحًا» في أيّ أتمتة (مراجعة ٥١ · البند ٥)."""
    rc, results = _run(tmp_path, monkeypatch, _Meter(0.30, reverse=True), 0.60)
    assert rc == 4, f"التوقّفُ عند عدّادٍ تراجعيّ يجب أن يكون 4 لا {rc}"
    assert len(results) == 1, f"يجب أن يتوقّف قبل السؤال الثاني لا بعد {len(results)}"


def test_without_a_budget_the_loop_is_not_capped(tmp_path, monkeypatch):
    """**الضابطُ الموجب**: بلا ميزانيةٍ يمرّ كلُّ السؤال — فلا يكون «التوقّف» أثرَ عطبٍ آخر."""
    rc, results = _run(tmp_path, monkeypatch, _Meter(0.30), 0)
    assert len(results) == 8, f"بلا سقفٍ يجب أن تُطرح الثمانية، طُرق {len(results)}"
    assert rc == 0, f"بلا سقفٍ ولا فشلٍ ⇒ 0، صار {rc}"
