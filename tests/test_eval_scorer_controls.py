"""ضوابطُ المصحِّح — **بمدخلاتٍ مصطنعةٍ بلا أدلّة** (لهذا لم تكن السويتُ تلتقط عللَ الحُكم).

الدرسُ (مراجعةٌ مستقلّة ٢٠٢٦-٠٩-٢٤): «٥٦٥ اختباراً تنجح ولا واحدٌ منها ينادي `score_answer`» ⇒ مرّ المصحِّحُ
معكوساً (`truth` يُعيد فهرسَ صفٍّ ويُقارَن بمبالغ) فحكم على أجوبةٍ صحيحةٍ بالفشل. القاعدةُ: **لكلّ قاعدةِ حُكمٍ
ضابطٌ موجبٌ وضابطٌ سالب** — وإلّا فالحُكمُ زعمٌ بلا دليل.
"""

from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("eval_questions", ROOT / "tools" / "eval_questions.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eq = _load()


class _Trace:
    """أثرٌ مصطنع: ما استُشهد به فعلاً (نفسُ عقد `_Trace` في الأداة)."""

    def __init__(self, used=(), scope="in_scope", refused=False):
        self.used_row_nos = list(used)
        self.scope = scope
        self.refused = refused


ROWS = [  # صفحة ٧: ٢٢٠٫٠٠ قمة · بقيةٌ أدنى · صفحاتٌ أخرى للتحكّم
    {"page": 7, "movement": 12.50, "balance": 100.00},
    {"page": 7, "movement": 220.00, "balance": 320.00},
    {"page": 7, "movement": 220.00, "balance": 540.00},
    {"page": 8, "movement": 5.00, "balance": 545.00},
]


def _q(kind: str, **d):
    return {"id": "t", "cat": "اختبار", "metric": "citation", "expect": "rows",
            "q": "؟", "derive": {"kind": kind, **d}}


# ── الاستشهاد على القمة (`argmax_row`) — كان معكوساً: فهرسُ صفٍّ يُقارَن بمبلغ ──────────────────

def test_argmax_correct_answer_passes():
    t = {"amount": 220.00, "tops": [1, 2], "tie": True}
    ok, why = eq.score_answer(_q("argmax_row", page=7), t, "أكبر مبلغ 220.00 ريال (صفّان متعادلان: مرتين)",
                              _Trace(used=[2, 3]), ROWS)
    assert ok, why


def test_argmax_wrong_amount_fails():
    t = {"amount": 220.00, "tops": [1, 2], "tie": True}
    ok, _ = eq.score_answer(_q("argmax_row", page=7), t, "أكبر مبلغ 12.50 ريال فقط",
                            _Trace(used=[1]), ROWS)
    assert not ok


def test_argmax_tie_must_be_declared():
    t = {"amount": 220.00, "tops": [1, 2], "tie": True}
    ok, why = eq.score_answer(_q("argmax_row", page=7), t, "أكبر مبلغ 220.00 ريال في الصف الثالث",
                              _Trace(used=[2]), ROWS)
    assert not ok and "التعادل" in why        # المبلغُ صحيحٌ لكن جزمَ بلا إعلانِ تعادلٍ وهو متعادل


def test_argmax_row_index_is_not_an_amount():
    """العلّةُ الأصلية: مبلغٌ يساوي فهرسَ الصفّ يجب ألّا يُمرَّر بوصفه قمةً."""
    t = {"amount": 220.00, "tops": [2], "tie": False}
    ok, _ = eq.score_answer(_q("argmax_row", page=7), t, "الصفّ 2 هو القمة (2.00 ريال)",
                            _Trace(used=[1]), ROWS)
    assert not ok


# ── الامتناع — الاختراعُ مبلغٌ بلا سند في الأثر، لا كلُّ رقمٍ في الجواب ────────────────────────

def _abs_q():
    return {"id": "t", "cat": "امتناع", "metric": "abstain", "expect": "absent", "q": "؟",
            "derive": {"kind": "absent", "reason": "page_outside_pack", "page": 700}}


def test_abstention_with_unsupported_amount_fails():
    ok, why = eq.score_answer(_abs_q(), None, "لا يوجد؛ أقربُ رقمٍ 1,234.56", _Trace(used=[1]), ROWS)
    assert not ok and "بلا سند" in why


def test_abstention_echoing_a_page_number_is_not_an_invention():
    """**الانحدارُ المقيس**: جوابٌ ردّ رقمَ الصفحة المسؤول عنها فحُسب «مخترعاً» (العدّادُ القديم)."""
    ok, why = eq.score_answer(_abs_q(), None, "الصفحة 700 غير موجودة في الكشف (لا توجد بيانات)",
                              _Trace(used=[]), ROWS)
    assert ok, why


def test_abstention_scope_gate_counts_as_pass():
    ok, why = eq.score_answer(_abs_q(), None, "لا يمكنني الإجابة", _Trace(scope="out_of_scope"), ROWS)
    assert ok and "النطاق" in why


# ── السلسلة — «لا يتساويان» نفيٌ صريحٌ لا يُسقَط بقائمةٍ فقيرة ────────────────────────────────

def _chain_q():
    return {"id": "t", "cat": "سلسلة", "metric": "number", "expect": "chain", "q": "؟",
            "derive": {"kind": "row_chain", "a": 7, "b": 8}}


def test_chain_correct_negation_passes():
    ok, why = eq.score_answer(_chain_q(), {"equal": False, "diff": 37.0},
                              "لا، لا يتساويان: الفرق 37.00 ريال", _Trace(), ROWS)
    assert ok, why


def test_chain_affirmative_fails():
    ok, _ = eq.score_answer(_chain_q(), {"equal": False, "diff": 37.0},
                            "نعم، الرصيدان متّصلان تماماً", _Trace(), ROWS)
    assert not ok


# ── الرقم — مطابقةُ المبلغ المُشتقّ ───────────────────────────────────────────────────────────

def _number_q(kind, **d):
    return {"id": "t", "cat": "رقمي", "metric": "number", "expect": "number", "q": "؟",
            "derive": {"kind": kind, **d}}


def test_number_match_passes_and_mismatch_fails():
    ok, _ = eq.score_answer(_number_q("last_row_balance", page=8), 545.00, "الرصيدُ الأخير 545.00", _Trace(), ROWS)
    assert ok
    ok, _ = eq.score_answer(_number_q("last_row_balance", page=8), 545.00, "الرصيدُ الأخير 540.00", _Trace(), ROWS)
    assert not ok
