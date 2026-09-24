"""ضوابطُ البوّابات — تُشغَّل على العلل التي **لا** يكشفها السلوكُ العاديّ.

**الدرسُ المدفوع (الجولة ٤٩ · البند ٥):** ثلاثةُ إصلاحاتٍ (القصّ S-1/P-2، والبوّابة S-3، والبصمة S-4) مرّت
وفي المستودع **٥٩٠ اختبارًا خضراء لا واحدَ منها يسقط عند إرجاعها** ⇒ إصلاحٌ بلا ضابطٍ ليس إصلاحًا.
**وكلُّ ضابطٍ هنا مصمَّمٌ على مخرَج المُنتِج نفسه** لا على قيمةٍ اخترتُها: البصمةُ تُقاس بما يُخرجه
`_spec_sha` عند فشل القراءة، والصفحةُ الغائبةُ تُقاس بمسار `--rescore` الحقيقيّ.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

RUN = ROOT / "data/local_sample/slice_629p"
needs_run = pytest.mark.skipif(not (RUN / "results").exists(), reason="بلا أدلّةِ القرص (data/local_sample)")


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ES = _load("eval_stamp", "tools/eval_stamp.py")


# ─────────────── S-4: البصمةُ بصيغةٍ لا بقيمةٍ بعينها (والضابطُ يقرأ مخرَجَ المُنتِج) ───────────────

def test_the_producers_own_failure_value_is_not_publishable():
    """**الضابطُ على المُنتِج**: نُفقِد `_spec_sha` ملفَّها فتُخرج قيمتَها الحقيقيّة، ثم نطالب برفضها."""
    EQ = _load("eval_questions_s4", "tools/eval_questions.py")
    real = pathlib.Path.read_bytes

    def boom(self, *a, **k):
        if str(self).endswith("questions.json"):
            raise OSError("لا ملفّ")
        return real(self, *a, **k)

    pathlib.Path.read_bytes = boom
    try:
        v = EQ._spec_sha()
    finally:
        pathlib.Path.read_bytes = real
    assert v == "?" or not v, f"تغيّر مخرَجُ الفشل: {v!r} — حدِّث هذا الضابط"
    assert ES.is_publishable({"spec_sha": v}, v) is False, "بصمةُ الفشل مرّت كبصمةٍ صحيحة (الجولة ٤٩ · S-4)"


@pytest.mark.parametrize("bad", ["?", "؟", "", None, "4facf540abd", "ZZZZZZZZZZZZ"])
def test_only_a_twelve_hex_sha_is_a_sha(bad):
    """١٢ خانةً ست عشريّة أو لا شيء — فالعلّةُ تموت بصيغتها لا بقيمةٍ واحدة."""
    assert ES.is_publishable({"spec_sha": bad}, bad) is False
    assert ES.is_publishable({"spec_sha": "4facf540abd4"}, "4facf540abd4") is True


# ─────────────── P-2: المقصوصُ يُستبعَد مُعلَنًا (وضابطُ الشجرة على القصّ) ───────────────

def test_the_writer_no_longer_truncates_the_trace():
    """حصادةُ ارتدادٍ نصّيّة: القصُّ `[:40]` عاد ⇒ يسقط. (لا سبيلَ لقياسه بلا طرحٍ مدفوع.)"""
    src = (ROOT / "tools/eval_questions.py").read_text()
    assert "or [])[:40]" not in src, "عاد قصُّ الأثرِ عند ٤٠ (الجولة ٤٩ · P-2)"
    assert '"trace_len"' in src, "لا يُحفظ طولُ الأثر ⇒ لا يُفرَّق المقصوصُ من الكامل"


def test_a_suspect_trace_is_excluded_from_the_published_total(tmp_path):
    """سجلٌّ بـ٤٠ مرجعًا بلا `trace_len` = مشكوكُ القصّ ⇒ يُستبعَد ويُعلَن، لا يُحسب."""
    from tools import eval_run_compare as erc

    spec = tmp_path / "q.json"
    spec.write_text(json.dumps({"questions": [
        {"id": "a", "cat": "c", "metric": "number", "expect": "number", "q": "؟", "derive": {"kind": "x"}},
        {"id": "b", "cat": "c", "metric": "number", "expect": "number", "q": "؟", "derive": {"kind": "x"}},
    ]}, ensure_ascii=False))
    sha = hashlib.sha256(spec.read_bytes()).hexdigest()[:12]
    arm = tmp_path / "A.json"
    arm.write_text(json.dumps({"results": [
        {"id": "a", "ok": True, "metric": "number", "spec_sha": sha, "used_row_nos": list(range(1, 41))},
        {"id": "b", "ok": True, "metric": "number", "spec_sha": sha, "used_row_nos": [1], "trace_len": 1},
    ]}, ensure_ascii=False))
    out = erc.compare(spec, [arm])
    assert out["totals_per_arm"]["A.json"]["trace_excluded"] == 1, out["totals_per_arm"]
    assert out["totals_per_arm"]["A.json"]["n"] == 1, "المقصوصُ دخل المقام (الجولة ٤٩ · P-2)"


# ─────────────── S-1: التغطيةُ الناقصةُ تُعلَن ولا تُقاس على تقاطعٍ أضيق ───────────────

def test_a_missing_id_is_a_failed_invariant(tmp_path):
    from tools import eval_run_compare as erc

    spec = tmp_path / "q.json"
    spec.write_text(json.dumps({"questions": [
        {"id": "a", "cat": "c", "metric": "number", "expect": "number", "q": "؟", "derive": {"kind": "x"}},
        {"id": "b", "cat": "c", "metric": "number", "expect": "number", "q": "؟", "derive": {"kind": "x"}},
    ]}, ensure_ascii=False))
    sha = hashlib.sha256(spec.read_bytes()).hexdigest()[:12]
    full = tmp_path / "A.json"
    full.write_text(json.dumps({"results": [{"id": i, "ok": True, "metric": "number", "spec_sha": sha,
                                             "used_row_nos": [1], "trace_len": 1} for i in ("a", "b")]}))
    hole = tmp_path / "B.json"
    hole.write_text(json.dumps({"results": [{"id": "a", "ok": True, "metric": "number", "spec_sha": sha,
                                             "used_row_nos": [1], "trace_len": 1}]}))
    out = erc.compare(spec, [full, hole])
    assert out["missing_ids"]["B.json"] == ["b"], out["missing_ids"]
    assert out["invariants"]["arms_cover_the_pack"] is False, "تغطيةٌ ناقصة مرّت كسلامة (الجولة ٤٩ · S-1)"


# ─────────────── S-3: لا فرعَ يعبر البوّابة، ولا كتابةَ فوق الشاهدِ قبل الحكم ───────────────

@needs_run
def test_rescore_cannot_pass_the_anchor_gate(tmp_path, capsys):
    """**تجربةُ المراجعة نفسُها**: سؤالٌ يشير إلى صفحةٍ غيرِ موجودة ⇒ `--rescore` يُرفَض (rc=2) ولا يكتب."""
    EQ = _load("eval_questions_s3", "tools/eval_questions.py")
    spec = tmp_path / "q_bad.json"
    spec.write_text(json.dumps({"questions": [
        {"id": "bad-01", "cat": "رقمي", "metric": "number", "expect": "number",
         "q": "كم صفًّا في الصفحة ٩٩٩٩؟", "derive": {"kind": "count_rows", "page": 9999}},
    ]}, ensure_ascii=False))
    sha = hashlib.sha256(spec.read_bytes()).hexdigest()[:12]
    arm = tmp_path / "arm.json"
    original = json.dumps({"results": [{"id": "bad-01", "answer": "٧", "ok": False, "spec_sha": sha,
                                        "used_row_nos": [1], "trace_len": 1}]}, ensure_ascii=False, indent=1)
    arm.write_text(original)
    rc = EQ.main(["--rescore", "--questions", str(spec), "--run", str(RUN), "--out", str(arm)])
    capsys.readouterr()
    assert rc == 2, f"`--rescore` عبر البوّابة (rc={rc}) — الجولة ٤٩ · S-3"
    assert arm.read_text() == original, "كُتب فوق الشاهدِ قبل الحكم (الجولة ٤٩ · S-3)"


@needs_run
def test_a_substitute_is_not_an_answer(tmp_path, capsys):
    """**النائبُ ليس جوابًا** (P-3): لا يُحكم عليه فشلاً ولا يدخل المقام."""
    EQ = _load("eval_questions_s3b", "tools/eval_questions.py")
    spec = tmp_path / "q_ok.json"
    spec.write_text(json.dumps({"questions": [
        {"id": "cnt-01", "cat": "رقمي", "metric": "number", "expect": "number",
         "q": "كم صفًّا في الصفحة ١؟", "derive": {"kind": "count_rows", "page": 1}},
    ]}, ensure_ascii=False))
    sha = hashlib.sha256(spec.read_bytes()).hexdigest()[:12]
    arm = tmp_path / "arm.json"
    arm.write_text(json.dumps({"results": [{"id": "cnt-01", "answer": "<انتهت المهلة>", "ok": False,
                                            "spec_sha": sha, "used_row_nos": [], "trace_len": 0}]},
                              ensure_ascii=False, indent=1))
    rc = EQ.main(["--rescore", "--questions", str(spec), "--run", str(RUN), "--out", str(arm)])
    txt = capsys.readouterr().out
    assert rc == 0 and "نائبًا" in txt and "المجموع" in txt, txt[-400:]
    saved = json.loads(arm.read_text())["results"][0]
    assert saved.get("substitute") is True and saved.get("ok") is None, saved
