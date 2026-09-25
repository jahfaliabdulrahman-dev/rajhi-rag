"""ضوابطُ الثلاثة التي بقيت بلا ضابطٍ من مراجعة ٥٠ (ومراجعة ٥١ أعادت إحصاءها):

1. **بصمةُ `--rescore` من الملفّ المُستعمل فعلًا** — لا من مسارٍ ثابتٍ في الكود.
2. **الحكمُ قبل الكتابة** — سجلٌّ بلا شاهدٍ على السؤال المطروح لا يُمحى ملفُّه.
3. **القصّ بتهجئةٍ أخرى** — سجلٌّ مقصوصٌ بـ`>= 40` وبلا `trace_len` يُوسم مشكوكًا (كان `== 40` وحدها).

كلُّها سلوكيّة: تُشغّل الدالّةَ وتقيس أثرَها على القرص، وتسقط إذا أُعيدت العلّة.
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


def _harness(tmp_path, monkeypatch, seed_sha: str):
    m = _load("evalq_rescore", "tools/eval_questions.py")
    stamp = _load("eval_stamp_rescore", "tools/eval_stamp.py")
    qs = [{"id": "q01", "q": "س", "type": "count_rows", "cat": "count", "metric": "مُحاكى",
           "expect": "…", "derive": {"kind": "mock"}}]
    qfile = tmp_path / "questions.json"
    qfile.write_text(json.dumps({"questions": qs}, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "answers.json"
    out.write_text(json.dumps({"results": [{"id": "q01", "q": "س", "answer": "جوابٌ مُحاكى",
                                            "used_row_nos": [1], "ok": True, "spec_sha": seed_sha}]},
                              ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(m, "truth", lambda q, c, pack, rows: ({"kind": "مُحاكى"}, "مُحاكى"))
    monkeypatch.setattr(m, "score_answer", lambda q, t, ans, res, rows: (True, "ok"))
    a = types.SimpleNamespace(out=out, questions=qfile, allow_stale=False)
    return m, stamp, a, qs, out


def test_rescore_stamps_the_questions_file_it_actually_used(tmp_path, monkeypatch):
    """الملفُّ المستعملُ هو `a.questions` — لا مسارٌ ثابتٌ في الكود (كان يُشهد لغير ما قيس)."""
    m0 = _load("evalq_rescore0", "tools/eval_questions.py")
    m, _stamp, a, qs, out = _harness(tmp_path, monkeypatch, seed_sha="x" * 12)
    cur = m._spec_sha(a.questions)
    # البذرةُ تحمل بصمةَ **الملفّ المستعمل** ⇒ الحكمُ قابلٌ للنشر فيُكتب الملفّ.
    data = json.loads(out.read_text())
    data["results"][0]["spec_sha"] = cur
    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rc = m.rescore(a, qs, None, {}, {}, [])
    written = json.loads(out.read_text())["results"][0]["spec_sha"]
    assert rc == 0, f"إعادةُ الحكم على بصمةٍ مطابقةٍ يجب أن تنجح لا {rc}"
    assert written == cur, "البصمةُ المكتوبةُ ليست بصمةَ الملفّ الذي أُعيد الحكمُ عليه"
    assert cur != m0._spec_sha(ROOT / "tools/eval_questions.py"), "شهادةٌ على مسارٍ آخر — ملفٌّ مختلفٌ ⇒ بصمةٌ مختلفة"


def test_a_record_without_a_witness_is_not_written_over(tmp_path, monkeypatch):
    """**الحكمُ قبل الكتابة**: سجلٌّ شاهدُه على نصٍّ آخر ⇒ `rc=3` و**الملفُّ لا يُمحى**."""
    m, _stamp, a, qs, out = _harness(tmp_path, monkeypatch, seed_sha="س" * 12)
    before = out.read_bytes()
    rc = m.rescore(a, qs, None, {}, {}, [])
    assert rc == 3, f"سجلٌّ لا شاهدَ له يجب أن يوقف الكتابة برمزٍ غيرِ صفريّ لا {rc}"
    assert out.read_bytes() == before, "مُحي الشاهدُ بلا مقابل: كُتب الملفُّ ثم رُفض النشر"


def test_the_truncated_trace_has_two_spellings(tmp_path, monkeypatch):
    """القصُّ يُعرف **بالحدّ أو بما فوقه** وبأيّ صيغة — لا بـ`== 40` وحدها."""
    stamp = _load("eval_stamp_trunc", "tools/eval_stamp.py")
    cap = stamp.TRACE_CAP
    assert stamp.is_trace_suspect({"used_row_nos": list(range(cap))}) is True, "التهجئةُ القديمة (٤٠) تسقط"
    assert stamp.is_trace_suspect({"used_row_nos": list(range(cap + 5))}) is True, "تهجئةٌ أخرى (٤٥) تمرّ صامتة"
    assert stamp.is_trace_suspect({"used_row_nos": list(range(cap + 5)), "trace_len": cap + 5}) is False, \
        "السجلُّ الحديث يحمل trace_len فلا يُوسم"
    assert stamp.is_trace_suspect({"used_row_nos": [1, 2, 3]}) is False, "أثرٌ قصيرٌ لا يُوسم"


def test_a_record_whose_declared_length_disagrees_with_its_trace_is_suspect():
    """**الهويّةُ تُقاس لا تُصدَّق** (مراجعة ٥٢ · مقعدُ البنية F6).

    كان وجودُ `trace_len` وحده علامةَ «نظيف» بلا مقارنة ⇒ سجلٌّ مقصوصٌ يحمل طولًا مخالفًا يمرّ
    **قابلًا للنشر** على مسارات القراءة (`--rescore` · أداة المقارنة)، وإن أمسكه الكاتبُ وحدَه.
    والقياسُ على السجلات المحفوظة (٢٠٢٦-٠٩-٢٤): **صفرُ سجلٍ يحمل `trace_len`** ⇒ لا إعادةَ تصنيفٍ
    لأيّ سجلٍّ قائم (تُقاس لا تُدَّعى: `grep -l trace_len docs/evidence data/eval_pack`).
    """
    stamp = _load("eval_stamp_identity", "tools/eval_stamp.py")
    assert stamp.is_trace_suspect({"used_row_nos": [1, 2, 3], "trace_len": 45}) is True, \
        "طولٌ مخالفٌ للأثر ⇒ مشكوك (لا نظيف)"
    assert stamp.is_trace_suspect({"used_row_nos": [1, 2, 3], "trace_len": 3}) is False, "متطابقٌ ⇒ نظيف"
    assert stamp.is_trace_suspect({"used_row_nos": [1, 2, 3], "trace_len": "x"}) is True, \
        "طولٌ غيرُ رقميّ ⇒ لا يُوثق به"

