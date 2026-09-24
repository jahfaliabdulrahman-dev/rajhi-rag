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


# ============================================================================================
# مراجعة ٥٠ — أربعةُ ضوابطَ لِما كان بلا ضابط (والبندُ ١ كان علّةً حقيقيّةً في كودٍ أعلنتُه مُغلقًا)
# ============================================================================================
import json as _json                                                             # noqa: E402


def test_the_spend_meter_counts_forwards():
    """**البندُ المانع الأول (مراجعة ٥٠):** كان القياسُ `before − cur` وعدّادُ المزوّد **تراكميٌّ صاعد**
    (والكلفةُ في آخر الجولة `after − before`) ⇒ الناتجُ سالبٌ أبدًا ⇒ **سقفٌ لا يبلغ الميزانية**.
    الضابطُ يمسك الاتّجاه: صرفٌ ⇒ موجب. إرجاعُ الطرح المعكوس يُسقطه."""
    m = _load("eval_questions_meter", "tools/eval_questions.py")
    assert m._spent_since({"usage": 10.0}, {"usage": 10.3}) == pytest.approx(0.3)
    assert m._spent_since({"usage": 10.0}, {"usage": 10.0}) == 0.0
    assert m._spent_since({"usage": 10.0}, {"usage": 9.5}) < 0      # العكسُ يظهر سالبًا ⇒ لا يبلغ سقفًا
    assert m._spent_since({"usage": 10.0}, {"usage": 9.7}) == pytest.approx(-0.3)  # العكسُ يُقاس لا يُقدَّر
    assert m._spent_since(None, {"usage": 1.0}) is None             # لا قياس ≠ صفرُ مصروف
    assert m._spent_since({"usage": 1.0}, None) is None
    assert m._spent_since({"usage": None}, {"usage": 1.0}) is None


def test_a_substitute_is_not_in_the_denominator(tmp_path):
    """**البندُ الرابع (مراجعة ٥٠):** `--rescore` كان يستبعد النائبَ والمقارنةُ تُدخله ⇒ مجموعان على
    الأذرع نفسها (٢٧/٣٨ مقابل ٢٧/٤٠). المقامُ الآن واحدٌ والنوائبُ في عمودها."""
    import hashlib
    spec = tmp_path / "q.json"
    spec.write_text(_json.dumps({"questions": [
        {"id": "a-1", "cat": "x", "metric": "number", "expect": "number", "q": "?", "derive": {"kind": "count_rows", "page": 1}},
        {"id": "a-2", "cat": "x", "metric": "number", "expect": "number", "q": "?", "derive": {"kind": "count_rows", "page": 1}},
        {"id": "a-3", "cat": "x", "metric": "number", "expect": "number", "q": "?", "derive": {"kind": "count_rows", "page": 1}}]},
        ensure_ascii=False), encoding="utf-8")
    sha = hashlib.sha256(spec.read_bytes()).hexdigest()[:12]
    def arm(path, second_ok, second_answer):
        path.write_text(_json.dumps({"results": [
            {"id": "a-1", "ok": True, "metric": "number", "used_row_nos": [1], "trace_len": 1, "spec_sha": sha},
            {"id": "a-2", "ok": second_ok, "metric": "number", "answer": second_answer,
             "used_row_nos": [1], "trace_len": 1, "spec_sha": sha},
            {"id": "a-3", "ok": True, "metric": "number", "used_row_nos": [1], "trace_len": 1, "spec_sha": sha}]},
            ensure_ascii=False), encoding="utf-8")
    A, B = tmp_path / "A.json", tmp_path / "B.json"
    arm(A, False, "<انتهت المهلة>")          # نائبٌ في الذراع A
    arm(B, True, "3")                        # جوابٌ حقيقيٌّ في B
    cmp = _load("eval_run_compare_d", "tools/eval_run_compare.py")
    out = cmp.compare(spec, [A, B])
    tA, tB = out["totals_per_arm"]["A.json"], out["totals_per_arm"]["B.json"]
    assert tA["substitutes"] == 1 and tA["n"] == 2, f"النائبُ دخل المقام: {tA}"
    assert tB["n"] == 3
    assert out["flaky"] == [], f"المقارنةُ على ما لم يُحكم عليه تُنتج تذبذبًا وهميًّا: {out['flaky']}"


def test_a_stale_snapshot_is_a_drift(tmp_path, monkeypatch):
    """**البندُ الثاني (مراجعة ٥٠ · CI):** كانت البوّابةُ تقابل الوثائقَ بالاشتقاق الحيّ **فقط**، فلا
    ترى لقطةً متقادمة (٥٩٠ مقابل ٦٠٢) يقرأها CI ⇒ تمرّ محليًّا وتسقط هناك."""
    rc = _load("render_claims_d", "tools/render_claims.py")
    snap = tmp_path / "claims.json"
    monkeypatch.setattr(rc, "SNAPSHOT", snap, raising=False)
    snap.write_text(_json.dumps({"tests": 590}, ensure_ascii=False), encoding="utf-8")
    drift = rc.snapshot_drift({"tests": 602})
    assert drift and drift[0][0] == "tests" and drift[0][1] == 590 and drift[0][2] == 602
    snap.write_text(_json.dumps({"tests": 602}, ensure_ascii=False), encoding="utf-8")
    assert rc.snapshot_drift({"tests": 602}) == []


@pytest.mark.skipif(not (ROOT / "data/local_sample/slice_629p/results").exists(),
                    reason="بلا عيّنةِ القرص المحلّيّة")
def test_the_chain_connects_by_magnitude_not_by_signed_addition():
    """**البندُ الثالث (مراجعة ٥٠):** المبلغُ المطبوعُ **بلا إشارة**، فالربطُ بالجمع الموقَّع يعدّ الحركاتِ
    الدائنةَ وحدها (١٢٤) ويسقط ٤٩٥ مدينة. المقياسُ على **المقدار** ⇒ ٦١٩ من ٦٢١ زوجًا وفجوتان معروفتان:
    (٤٢٦→٤٢٧) و(٦٢٥→٦٢٦). وإرجاعُ الجمع الموقَّع يُسقط هذا الضابط."""
    import json as _j
    import sys as _s
    for extra in (str(ROOT), str(ROOT / "src")):
        if extra not in _s.path:
            _s.path.insert(0, extra)
    from tools import refusal_test as rt                                     # noqa: PLC0415
    run = ROOT / "data/local_sample/slice_629p"
    rows, _ = rt.build_rows(run)
    by: dict = {}
    for r in rows:
        by.setdefault(r["page"], []).append(r)
    pages = sorted(by)

    def f(v):
        try:
            return float(str(v).replace(",", "").strip())
        except Exception:                                                    # noqa: BLE001
            return None
    connected, measured, gaps = 0, 0, []
    for a, b in zip(pages, pages[1:]):
        if a + 1 != b:
            continue
        la, fb = f(by[a][-1]["balance"]), f(by[b][0]["balance"])
        raw = _j.loads((run / "results" / f"pg-{b:03d}.json").read_text()).get("raw_rows") or []
        pm = next((x for x in (f(r.get("movement")) for r in raw) if x is not None), None)
        if la is None or fb is None or pm is None:
            continue
        measured += 1                                   # المقامُ يُقاس ولا يُفترض (كان ٦٢٤ نوافذَ لا ٦٢١ زوجًا)
        if abs(abs(fb - la) - abs(pm)) < 0.005:
            connected += 1
        else:
            gaps.append((a, b))
    assert measured == 621, f"المقامُ (الأزواجُ المتجاورة) يجب أن يكون ٦٢١ لا {measured}"
    assert connected == 619, f"الربطُ بالمقدار يجب أن يعطي ٦١٩ لا {connected} (الجمعُ الموقَّع يعطي ١٢٤)"
    assert gaps == [(426, 427), (625, 626)], f"الفجوتان المعروفتان تغيّرتا: {gaps}"


def test_the_snapshot_gate_actually_fires(monkeypatch, tmp_path):
    """**المانع S-3/B2 (مراجعة ٥٠):** ضابطُ اللقطة كان يقيس *الدالّة* لا *التنصيب* — حذفُ سلكها من `main`
    يُبقيه أخضر. هذا الضابطُ يشغّل **الأمر** على وثيقةٍ تخالف لقطتها (حالةُ CI) ويطالب برمز خروجٍ غير صفري."""
    rc = _load("render_claims_gate", "tools/render_claims.py")
    monkeypatch.setattr(rc, "PROJ", tmp_path)
    monkeypatch.setattr(rc, "SNAPSHOT", tmp_path / "docs" / "claims.json")
    monkeypatch.setattr(rc, "REPORT", tmp_path / "no-such-report.json")   # بلا تقريرٍ حيّ = حالةُ CI
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    doc = tmp_path / "docs" / "QA_CHECKLIST.md"
    doc.write_text("حالياً 999 اختباراً\n", encoding="utf-8")
    (tmp_path / "docs" / "claims.json").write_text(_json.dumps({"tests": 606}, ensure_ascii=False),
                                                   encoding="utf-8")
    monkeypatch.setattr(rc, "claims",
                        lambda d: [("docs/QA_CHECKLIST.md", f"حالياً {d['tests']}", "عدد الاختبارات")])
    monkeypatch.setattr(sys, "argv", ["render_claims.py", "--check"])
    with pytest.raises(SystemExit) as e:
        rc.main()
    assert e.value.code == 1, "البوّابةُ لا تحمرّ على وثيقةٍ تخالف لقطتها (وهي حالةُ CI بعينها)"
    doc.write_text("حالياً 606 اختباراً\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e2:
        rc.main()
    assert e2.value.code == 0


def test_the_spend_formula_has_exactly_one_owner():
    """**المانع B4 (مراجعة ٥٠):** ضابطُ الاتّجاه كان يربط الدالّةَ لا مستهلكيها ⇒ إرجاعُ الصيغة المضمَّنة في
    موضع الصرف يُبقيه أخضر. هذا الضابطُ يمنع تعدُّدَ المالك: لا طرحَ لعدّاد المزوّد خارج `_spent_since`."""
    import re
    src = (ROOT / "tools" / "eval_questions.py").read_text(encoding="utf-8")
    body = src.split("def _spent_since", 1)[1].split("\ndef ", 1)[0]      # حتى أوّل def في العمود صفر
    assert body.count("return float(c) - float(b)") == 1, "المالكُ يجب أن يحمل الطرحَ وحده"
    rest = src.replace(body, "", 1)
    bad = re.findall(r"usage[^\n]{0,60}?-{1}[^\n]{0,20}?usage", rest)     # طرحُ قراءتَي عدّاد خارج المالك
    assert not bad, f"طرحُ عدّاد المزوّد خارج `_spent_since`: {bad[:2]}"
    assert src.count("_spent_since(") >= 3, "الصيغةُ تُستهلك من السقف وسطر الكلفة معًا"
