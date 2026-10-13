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
