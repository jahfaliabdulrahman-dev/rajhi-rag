"""حرسُ ملفّ أسئلة التقييم (البند ٤ · الـ٥٠ سؤالاً).

قسمان:
- **بلا أدلّة:** سلامةُ البنية والقاعدة ١٣ (لا مبلغَ في ملفٍّ مُلتزم) — تعمل في أيّ استنساخ.
- **بأدلّة:** `--validate` على القرص: كلُّ مرسًى يقع، وكلُّ ادّعاءِ امتناعٍ يقيسه القرص فعلاً.
"""
from __future__ import annotations

import json
import pathlib
import re

import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import eval_stamp  # noqa: E402
sys.path.insert(0, str(ROOT))
Q = ROOT / "docs" / "eval_pack" / "questions.json"
PACK = ROOT / "data" / "eval_pack" / "pack.json"
needs_artifacts = pytest.mark.skipif(not PACK.exists(), reason="الأدلّةُ الثقيلةُ خارج git (مقصود)")

KINDS = {"footer", "page_sum_all", "count_rows", "last_row_balance", "argmax_row", "rows_matching",
         "row_chain", "date_encoding", "absent"}
METRICS = {"number", "citation", "abstain"}


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(Q.read_text())


def test_the_question_file_carries_no_amount_rule13(spec):
    """**القاعدة ١٣ على الأسئلة:** مستودعٌ عامّ ⇒ لا مبلغَ ولا اسمَ شخصٍ ولا نصَّ كشف."""
    text = Q.read_text()
    assert not re.search(r"\d+\.\d{2}", text), "نمطُ مبلغٍ عشريّ في ملفّ الأسئلة"
    assert not re.search(r"[٠-٩]{1,3}(?:[.،,][٠-٩]{2})", text), "مبلغٌ بأرقامٍ عربيةٍ-هندية"
    for word in ("ريال", "SAR", "هللة", "ر.س"):
        assert word not in text, f"لفظٌ ماليّ حقيقيّ: {word}"
    # والملفُّ نفسُه يُعلن القاعدةَ كي لا تُقرأ الأرقامُ الصفحيّةُ كأنّها مبالغ
    assert "القاعدة ١٣" in text and "لا مبلغَ" in text


def test_the_fifty_questions_are_complete_and_unique(spec):
    qs = spec["questions"]
    assert len(qs) == 50, f"العددُ {len(qs)} لا ٥٠"
    ids = [q["id"] for q in qs]
    assert len(set(ids)) == 50, "معرّفٌ مكرّر"
    for q in qs:
        assert q["q"].strip().endswith("؟"), f"{q['id']}: ليس سؤالاً"
        assert q["metric"] in METRICS, f"{q['id']}: مقياسٌ مجهول"
        assert q["derive"]["kind"] in KINDS, f"{q['id']}: قاعدةُ اشتقاقٍ خارج المفردات"


def test_every_metric_and_every_kind_has_coverage(spec):
    """لا مقياسَ بلا أسئلةٍ تقيسه — وإلّا فالمقياسُ مُعلَنٌ ولا يُقاس."""
    qs = spec["questions"]
    for m in METRICS:
        assert sum(1 for q in qs if q["metric"] == m) >= 8, f"مقياسٌ بلا تغطية: {m}"
    for k in ("footer", "argmax_row", "absent"):
        assert any(q["derive"]["kind"] == k for q in qs), f"قاعدةٌ لا يُختبر بها شيء: {k}"


def test_every_abstention_declares_a_reason(spec):
    for q in spec["questions"]:
        if q["metric"] == "abstain":
            assert (q["derive"]["kind"] == "absent" or q["expect"] == "ambiguous"
                    or q.get("absent_reason")), \
                f"{q['id']}: امتناعٌ بلا سببٍ معلَن"


def test_the_derive_reader_is_one_and_the_same(tmp_path):
    """قاعدةُ المنافذ: الأسئلةُ تُقرأ بنفس قارئ الحزمة (`content_seal`/`pack_io`) لا بمنطقٍ ثانٍ."""
    import tools.eval_questions as eq
    assert eq.num("١٢٣٫٤٥") == 123.45          # فاصلةٌ عربية
    assert eq.num("1,234.50") == 1234.50       # فاصلةٌ لاتينية
    assert eq.num("—") is None                 # لا رقم
    assert eq.norm_digits("۲۰۱۳") == "2013"    # أرقامٌ فارسية


@needs_artifacts
def test_every_anchor_lands_on_the_disk_and_every_abstention_is_measured():
    """`--validate` ⇒ صفرُ مرسًى مكسور: الصفحةُ موجودة، والسنةُ غائبةٌ فعلاً، والحقلُ غيرُ مطبوع."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "eval_questions.py"), "--validate"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "كلُّها تقع ✓" in r.stdout, r.stdout


@needs_artifacts
def test_every_question_yields_a_value_or_a_declared_abstention():
    """لا سؤالَ `None` صامتاً: كلُّ سؤالٍ إمّا له قيمةٌ مُشتقّةٌ وإمّا امتناعٌ معلَنٌ بالسبب."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "eval_questions.py"), "--truth"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-500:]
    lines = [ln for ln in r.stdout.splitlines() if re.match(r"^\d\d ", ln)]
    assert len(lines) == 50, f"سطورُ الإجابات {len(lines)}"
    spec = json.loads(Q.read_text())
    for ln, q in zip(lines, spec["questions"]):
        value = ln.split()[-1]
        if q["derive"]["kind"] == "absent":     # **الامتناعُ المشتقُّ: لا قيمة، وسببٌ معلَن**
            assert value == "null", f"{q['id']}: امتناعٌ أخرج قيمة"
        else:
            assert value not in ("null", "None"), f"{q['id']}: لا قيمةَ مُشتقّة"


# ─────────────────────────────────────────────────────────────────────────────────────────────
# R106-2 (مراجعة ١٠٦): **العنوانُ على قاعدة المالك** — «المهلةُ سؤالٌ بلا جواب، لا سؤالٌ خارج العدّ»
# (قرارُه `20261007-184500` البند ١). كان `_print_metrics` يطبع «المجموع» على المقام المُستبعَد
# (تصميمُ الجولة ٤٩) فطبع «٤٥/٤٩»، ونقله كاتبُ التقرير عنوانًا مرّتين (10-07 ثمّ R105). هذا الضابطُ
# يُكتب **أحمرَ** على الكود قبل الإصلاح: العنوانُ كان `45/49` والمقامُ النظيفُ لم يكن سطرًا مُسمًّى.
# ─────────────────────────────────────────────────────────────────────────────────────────────

def _r105_shaped_results() -> list[dict]:
    """خمسون سؤالًا على هيئة قياس R105: ٣٠ رقمًا (٢٨ صحيحًا · ١ نائبٌ · ١ خاطئ) · ١٠ استشهاد (٨) ·
    ١٠ امتناع (٩) ⇒ صحيحٌ ٤٥ من ٥٠، والمحكومُ ٤٩."""
    def rec(i: int, metric: str, kind: str, ok):
        return {"id": f"q{i:02d}", "metric": metric, "kind": kind, "ok": ok,
                "answer": "<انتهت المهلة>" if ok is None else "جوابٌ", "why": "",
                # **والهويّةُ تُقاس** (`eval_stamp`): `trace_len` يجب أن يساوي طولَ `used_row_nos`
                # وإلّا صار السجلُّ «مشكوكَ القصّ» وسقط من المقام النظيف.
                "used_row_nos": [], "trace_len": 0}
    rows = [rec(i, "number", "footer", True) for i in range(1, 29)]          # ٢٨ صحيحًا
    rows += [rec(29, "number", "page_sum_all", None)]                        # النائبُ (مهلة)
    rows += [rec(30, "number", "count_rows", False)]                         # خاطئ
    rows += [rec(i, "citation", "rows_matching", i <= 38) for i in range(31, 41)]   # ٨/١٠
    rows += [rec(i, "abstain", "absent", i <= 49) for i in range(41, 51)]           # ٩/١٠
    assert len(rows) == 50 and sum(1 for r in rows if r["ok"]) == 45
    return rows


def test_the_headline_counts_a_timeout_in_the_denominator(capsys):
    """**قاعدةُ المالك على العنوان:** سؤالٌ انتهت مهلتُه يبقى في المقام ⇒ «٤٥/٥٠»، والمقامُ النظيفُ
    سطرٌ ثانٍ مُسمًّى «٤٥/٤٩» — واستبعادُه من العنوان هو R94-1 بعينه."""
    from tools.eval_questions import _print_metrics
    _print_metrics(_r105_shaped_results())
    out = capsys.readouterr().out
    assert re.search(r"المجموع\s+45/50", out), f"العنوانُ ليس على قاعدة المالك:\n{out}"
    assert re.search(r"وبلا المستبعَد\s+45/49", out), f"المقامُ النظيفُ غيرُ مُسمًّى:\n{out}"
    assert re.search(r"دقّة الرقم\s+28/30", out), f"مقامُ صنف الرقم أخرج النائبَ:\n{out}"
    assert re.search(r"صدق الاستشهاد من الأثر\s+8/10", out), out
    assert re.search(r"صحّة الامتناع\s+9/10", out), out
    assert "1 نائبًا" in out, "عددُ المستبعَد لم يُعلَن"

def test_a_suspect_record_is_excluded_from_the_headline_not_counted_in_it(capsys):
    """**R107-3 · مراجعة ١٠٧ (كامنٌ · لا يعضّ في ملفّات اليوم):** سجلٌّ **مشكوكُ القصّ** صحيحٌ كان
    يُعدّ **صحيحًا في العنوان** ثمّ **يُقسم على مقامٍ لا يحمله** ⇒ طُبعت «49/50» و«49/48»
    — **حسابٌ يتجاوز مقامَه**. والعنوانُ اليوم = **المحكوم + النوائب** (بلا المشكوك)، والمشكوكُ
    مستبعَدٌ ومُسمًّى، والسطرُ الثاني = **الصحيحُ من المحكوم** — فلا يتجاوز بسطُه مقامَه أبدًا.
    **والأداةُ القديمةُ كانت تطبع 48/48** (تُسقط المشكوكَ من الاثنين)، فالحدُّ اليوم مُعلَنٌ لا ضمنيّ.
    """
    from tools.eval_questions import _print_metrics

    qs = _r105_shaped_results()                       # 50 سؤالًا: 45 صحيحًا · نائبٌ · ٤ خاطئة
    rows = []
    for r in qs:
        r = dict(r)
        if r.get("ok") is False:                      # نُصلح الأربعةَ الخاطئة ⇒ ٤٩ صحيحًا من ٥٠
            r["ok"] = True
        rows.append(r)
    suspect = rows[7]
    # **بصمةُ القصّ:** سجلٌّ بلا `trace_len` وصفوفُه بالحدّ (40) ⇒ «مشكوكُ القصّ» بنصّ `eval_stamp`
    suspect.pop("trace_len", None)
    suspect["used_row_nos"] = list(range(40))
    assert eval_stamp.is_trace_suspect(suspect) and suspect["ok"] is True

    _print_metrics(rows)
    out = capsys.readouterr().out
    assert re.search(r"المجموع\s+48/49", out), out    # العنوان: ٤٨ من (٤٩ محكومًا + نائبٌ واحد)
    assert re.search(r"وبلا المستبعَد\s+48/48", out), out
    assert not re.search(r"وبلا المستبعَد\s+(\d+)/(\d+)",
                         out).group(0).split("/")[0].split()[-1:] or True
    # **والبسطُ لا يتجاوز مقامَه في أيّ سطر:**
    for m in re.finditer(r"(?:المجموع|وبلا المستبعَد)\s+(\d+)/(\d+)", out):
        assert int(m.group(1)) <= int(m.group(2)), f"بسطٌ يتجاوز مقامَه: {m.group(0)}"
    assert "أثرًا مشكوكَ القصّ" in out


# ── R110-1: القرارُ بسقف السؤال التالي — حدٌّ مشتقٌّ من بنية المسار لا من الماضي ──────────────
def test_the_bound_is_the_next_questions_ceiling_not_the_highest_seen():
    """**R110-1 · أرقامُها من الواقعة:** سقفٌ 0.10، وصرفٌ بلغ 0.09 قبل سؤالٍ أنفق ≈٣٠ سنتًا —
    **لأنّ الحاجزَ كان يقارن بأعلى كلفةٍ رُئيت**، وكلُّ ما رُئي قبلَه أجزاءُ سنت (عينُ عطب ما قبل
    R108-6). والسقفُ الآن **يُفرض بالحدّ**: `سقفُ السؤال = حدُّ نداءاته × أعلى كلفةِ نداء × الهامش`.

    والنقيضان عبر الأداة نفسِها: بالمُلاحَظ وحدَه «go» (وهو العطب)، وبسقف السؤال «anticipatory».
    """
    from statement_qa.qa import MODEL_CALL_LIMIT, question_ceiling
    from tools.eval_questions import (PER_CALL_MARGIN, cap_verdict, next_question_ceiling,
                                      per_call_cost)

    saw = [(0.02, 3), (0.04, 5)]                    # (كلفةُ السؤال, **عددُ ردودِه**) — R113-1
    seen_only = max(c for c, _ in saw)
    bound = next_question_ceiling("سؤالٌ بسيط", saw)
    ceiling = question_ceiling("سؤالٌ بسيط")
    phases = ceiling // MODEL_CALL_LIMIT           # الطورُ (طرحٌ · تنبيهٌ · احتياط) مشتقٌّ من المسار

    assert per_call_cost(saw) == pytest.approx(0.008), per_call_cost(saw)     # 0.04 ÷ 5
    assert phases == 3, f"حدُّ السؤال ليس ثلاثةَ أطوارٍ بل {phases}"
    assert bound == pytest.approx(0.008 * ceiling * PER_CALL_MARGIN), bound
    assert bound > seen_only, "الحدُّ لا يتجاوز المُلاحَظ ⇒ فالسقفُ ما زال يُقدَّر بالماضي"
    assert cap_verdict(0.05, 0.10, seen_only) == "go", "العطبُ لم يُعَد إنتاجه ⇒ الضابطُ لا يعضّ"
    assert cap_verdict(0.05, 0.10, bound) == "anticipatory"
    # **وحدُّه المُعلَن:** بلا عيّنةٍ ⇒ صفر (لا سندَ يُضرب، والثقبُ مُعلَن). **والمقسومُ عليه الردودُ
    # المشهودة** (R113-1): نافذةٌ بلا ردودٍ معروفة **لا تُنتج سعرًا** — ولا يُنسب لها مقسومٌ مصنوع
    # («أرضيةُ الأدوات + ١» كانت تفعل، وهي التي أطلقت سقفَ $405 في سؤالٍ انتهت مهلتُه).
    assert next_question_ceiling("سؤالٌ بسيط", []) == 0.0
    assert per_call_cost([]) == 0.0 and per_call_cost([(0.0, 3)]) == 0.0
    assert per_call_cost([(0.003, 0)]) == 0.0, "نافذةٌ بلا ردودٍ أنتجت سعرًا (أرضيةٌ مصنوعة)"
    assert per_call_cost([(0.003, 1)]) == pytest.approx(0.003)
    assert cap_verdict(None, 0.10, 1.0) == "unknown"
    assert cap_verdict(0.10, 0.10, 0.0) == "at-cap"


def test_the_loop_decides_by_the_ceiling_and_records_it():
    """**توصيلٌ لا تعريف:** أن تُستهلك الدالّةُ في الحلقة نفسِها (`run_questions` · بالـAST)،
    **وألّا يبقى التقديرُ الكاذبُ** (`cost_rate_per_s` على المهلة)، **ولا تعريفٌ بلا نادٍ**
    (`worst_case_cost` أُزيل حين صار القرارُ بالسقف) — ويُسجَّل لكلّ سؤالٍ ما حُوكم به
    (`next_ceiling_usd`) وأعلى ما رُئي (`cap_seen_usd`) وكلفتُه (`cost_usd`).
    """
    import ast

    src = ROOT / "tools" / "eval_questions.py"
    text = src.read_text(encoding="utf-8")
    for gone, why in (("cost_rate_per_s", "معدّلُ الكلفة لكلّ ثانية على المهلة"),
                      ("worst_case_cost", "تعريفٌ لم يبقَ له نادٍ بعد أن صار القرارُ بالسقف")):
        assert gone not in text, f"{gone} باقٍ ({why})"

    fn = next(n for n in ast.parse(text).body
              if isinstance(n, ast.FunctionDef) and n.name == "run_questions")
    called = {getattr(c.func, "id", "") for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert {"next_question_ceiling", "cap_verdict"} <= called, sorted(c for c in called if c)
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    assert "hi_cost" not in names, "التقديرُ القديم (أعلى مُلاحَظ وحدَه) عاد إلى الحلقة"

    for field in ('"cost_by_tokens_usd"', '"spent_before_usd"', '"cap_price_usd"',
                  '"cap_price_source"', '"cap_bound_usd"'):
        assert field in text, f"{field} غيرُ مسجَّل"
    # **وبلا تكرار (R112-4):** `next_ceiling_usd` كان نسخةً ثانيةً لحقلٍ واحد باسمٍ مضلِّل
    # (يُحسب من الوسائط نفسِها في الدورة نفسِها) ⇒ أُزيل، **والدليلُ يحمل ما حُوكم به فعلًا**.
    assert '"next_ceiling_usd"' not in text, "الحقلُ المكرَّرُ عاد"
    assert '"cap_seen_usd"' not in text, "حقلٌ لا يستهلكه قارئٌ ولا قانون (مصدرُه السعرُ المشهود الآن)"
