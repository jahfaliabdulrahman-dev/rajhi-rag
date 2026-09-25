"""الجدولُ الذهبيُّ للمُحلّل: **نسخةٌ واحدة** يقرؤها الضابطُ والبوّابةُ معًا.

**ولماذا وحدةٌ مستقلّةٌ خفيفة (لا داخل `tests/test_parser.py`)؟** لأنّ هذا الضابط يجب أن يعضّ في الـCI
الخفيف أيضًا، وذلك الملفُّ يستورد `statement_qa.parser` وفيه `import polars` — فسقط الـCI عند إدراجه
(قياسٌ مؤرَّخ: 2026-09-25 · تشغيلُ الـCI على `de00196` ⇒ `ModuleNotFoundError: No module named 'polars'` · `rc=2`).
وهذه الوحدةُ لا تستورد إلّا ستاندرد + `tools/qa_gate` + الوحدةَ الموروثة التي فيها نصُّ القاعدة.

**العلّةُ التي وُلدت لأجلها:** بوّابةُ التسليم قارنت مفتاحًا (`٦١,١٦٥١٢`) بقيمةٍ لا ينتجها المُحلّل، فبقيت
حمراءَ ≈٢٫٤ يومًا حتى صار الأحمرُ عاديًّا — لأنّ جدولَها كان **نسخةً ثانية** من الحقيقة بلا ضابطٍ يقابله.
فصار الجدولُ موضعًا واحدًا (`PARSER_GOLDENS` في `tools/qa_gate.py`) وهذا الملفُّ يقابله بالمُحلّل.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from statement_qa.vlm_reader import _parse_amount  # noqa: E402

from tools.qa_gate import PARSER_GOLDENS  # noqa: E402


def test_the_gate_goldens_agree_with_the_locked_rule():
    """**كلُّ زوجٍ في الجدول يُقابَل بالمُحلّل** — وجدولٌ فارغٌ يسقط (صفرٌ يُقرأ نجاحًا).

    والمرساةُ الحاكمةُ هي **نصُّ القاعدة** في `src/statement_qa/legacy/arabic_digit_parser.py:19`
    («لا نقطةَ ⇒ انظر آخر فاصلة: أكثرُ من ٣ أرقامٍ بعدها ⇒ النقطةُ ضاعت»)، لا الجدولُ نفسه.
    """
    assert PARSER_GOLDENS, "الجدولُ الذهبيُّ فارغ: صفرُ مدخلٍ ليس نتيجةً"
    mismatched: dict[str, tuple[str, str]] = {}
    for tok, want in PARSER_GOLDENS.items():
        got = _parse_amount(tok)
        if got != Decimal(want):
            mismatched[tok] = (str(got), want)
    assert not mismatched, (
        f"الجدولُ الذهبيُّ يخالف المُحلّلَ والوثيقة: {mismatched} — "
        "المصدرُ الحاكم: src/statement_qa/legacy/arabic_digit_parser.py:19")
    # **ومرساةٌ نصّيّةٌ مستقلّةٌ عن الجدول** على القاعدة نفسِها: النقطةُ العشريّةُ الضائعة.
    assert _parse_amount("٦١,١٦٥١٢") == Decimal("61165.12"), (
        "القيمةُ الذهبية عادت لمخالفة الوثيقة والضابط")
