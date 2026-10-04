"""بوّابةُ المال **الخفيفة**: تعمل في أضيق خطوة CI (بلا LangChainَ ولا numpy) — فلا تُتخطّى حيث تُشحن.

**العلّةُ التي تمنعها (قِيس):** بوّابةُ المال كانت في `test_money_string_fields.py` وهي تستورد `qa_tools`
(ومعه LangChain) ⇒ فتُتخطّى في كلّ خطوةٍ خفيفة ⇒ **بوّابةٌ مُسجَّلةٌ لا تعمل**. والوحدةُ `statement_qa.money`
**بلا تبعيّات**، فهذه البوّابةُ تستوردها **مباشرةً من ملفّها** (importlib) فلا يجرّها `__init__` إلى تبعيّات.
"""

from __future__ import annotations

import importlib.util
import pathlib

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "statement_qa" / "money.py"
_spec = importlib.util.spec_from_file_location("rajhi_money_under_test", _SRC)
assert _spec and _spec.loader
money_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(money_mod)
money = money_mod.money


def test_text_money_is_formatted_not_refused() -> None:
    """جوهرُ العطب: العقدُ يخزّن المال نصًّا ⇒ التنسيقُ يجب أن يقبله."""
    assert money("100.00") == "100.00"
    assert money("1234.5") == "1,234.50"
    assert money("9,001.00") == "9,001.00", "الفواصلُ لا تُسقط التحويل"


def test_numbers_and_absences() -> None:
    assert money(100) == "100.00" and money(2.5) == "2.50"
    assert money(None) == "" and money("") == ""
    assert money(None, dash="—") == "—", "غيابُ القيمة يُعلَن بنصّه لا يُخترع له رقم"


def test_a_non_number_is_shown_as_it_is() -> None:
    """**ولا تُبتلع:** قيمةٌ ليست رقمًا تُعرَض كما هي (إخفاؤها يجعل الصامتَ يُقرأ نجاحًا)."""
    assert money("غير رقم") == "غير رقم"


def test_the_interface_modules_defer_to_this_one() -> None:
    """**مالكٌ واحد:** `render.money` و`app._money` تُفوَّضان إلى الوحدة (بنصّها لا بالاستدعاء)."""
    for path, needle in (("src/statement_qa/render.py", "from statement_qa.money import money as _m"),
                         ("app.py", "from statement_qa.money import money as _m")):
        text = (pathlib.Path(__file__).resolve().parents[1] / path).read_text(encoding="utf-8")
        assert needle in text, f"{path}: لا يُفوَّض إلى الموضع الواحد"
        assert '{v:,.2f}' not in text, f"{path}: ما زال يُنسّق بنفسه (نسخةٌ ثانية)"
