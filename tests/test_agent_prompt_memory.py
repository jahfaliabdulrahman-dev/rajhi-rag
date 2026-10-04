"""البندُ ١ (R92): **قوالبُ التلقين وذاكرةُ الحوار** — بوّاباتٌ بلا نداء نموذج.

**العطبُ الذي تمنعه:** كان تلقينُ الوكيل **نصًّا مجمَّدًا** لا يعرف نطاقَ الكشف ولا سؤالَه السابق ⇒
فسؤالٌ تابعٌ («وماذا عن الصفحة ٤؟») يُجاب كأنّه مبتدأ، أو يُنقل فيه رقمٌ من جوابٍ سابق بلا أداة.

**وما تُثبته هذه البوّابات (لا تُدّعيه):** ① القالبُ يُصيغ بالمتغيّرين ويُعلن النطاقَ في متنه
② والنافذةُ محدودةٌ بـ`MEMORY_TURNS` **والإسقاطُ يُعدّ ويُسمّى** ③ ولا نداءَ شبكةٍ في المسار كلّه
④ **والتوصيلُ لا يكسر القائم:** بلا ذاكرةٍ ولا نطاقٍ يبقى التلقينُ نصَّه القديم بحرفه.
"""

from __future__ import annotations

import socket

from statement_qa.qa import (AGENT_SYSTEM_PROMPT, MEMORY_TURNS, build_system_prompt,
                             format_history)


def test_the_template_renders_its_variables_and_declares_the_scope() -> None:
    """**القالبُ لا نصٌّ مجمَّد:** النطاقُ والسجلُّ يظهران في التلقين المُصاغ."""
    out = build_system_prompt(scope="كشفُ ٦٢٩ صفحة · بنك الراجحي",
                              history=[("كم عدد الحركات؟", "١٠٣ حركة")])
    assert "كشفُ ٦٢٩ صفحة" in out and "كم عدد الحركات؟" in out and "١٠٣ حركة" in out
    assert "لا يُنقل عنه رقمٌ بلا أداة" in out, "القاعدةُ الحاكمة للسجلّ لا تُشطب من القالب"
    assert AGENT_SYSTEM_PROMPT.splitlines()[0] in out, "نصُّ الوكيل الأصليّ يبقى أساسَ القالب"


def test_the_memory_window_is_bounded_and_the_drop_is_declared() -> None:
    """**حدٌّ مُعلَن لا ذاكرةٌ تنمو:** آخرُ `MEMORY_TURNS` دورات، وما سقط يُسمّى بعدده."""
    short = format_history([("س١", "ج١"), ("س٢", "ج٢")])
    assert short.count("سؤالٌ سابق") == 2 and "أُسقطت" not in short
    long = format_history([("س١", "ج١"), ("س٢", "ج٢"), ("س٣", "ج٣"), ("س٤", "ج٤"), ("س٥", "ج٥")])
    assert long.count("سؤالٌ سابق") == MEMORY_TURNS, long
    assert "أُسقطت" in long and "2" in long, "الإسقاطُ يجب أن يُعدّ لا أن يُخفى"
    assert "أوّلُ سؤال" in format_history(None), "بلا سجلٍّ يُقال ذلك صراحةً"


def test_the_wiring_is_backward_compatible() -> None:
    """**توافقٌ خلفيّ:** بلا ذاكرةٍ ولا نطاقٍ ⇒ التلقينُ نصُّه القديم بحرفه (فلا سلوكَ يتبدّل)."""
    assert build_system_prompt() != AGENT_SYSTEM_PROMPT, "بلا مدخلٍ يُبنى القالبُ الموسَّع"
    # والقرارُ في موضع التوصيل: `history or scope` — يُقاس بالنصّ الحرفيّ في الوحدة
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[1] / "src" / "statement_qa" / "qa.py"
    text = src.read_text(encoding="utf-8")
    assert "if (history or scope) else AGENT_SYSTEM_PROMPT" in text, "شرطُ التوافق الخلفيّ غائب"


def test_no_network_in_the_prompt_path() -> None:
    """**«بلا كلفة» مُثبتٌ لا مُدَّعى:** يُفخّ المنفذُ فيسقط أيُّ نداءٍ — والقالبُ يمرّ."""

    def _deny(*_a, **_k):
        raise AssertionError("نداءُ شبكةٍ في مسار التلقين — والوعدُ: بلا كلفة")

    original = socket.socket.connect
    socket.socket.connect = _deny                      # type: ignore[method-assign]
    try:
        assert build_system_prompt(scope="عيّنة", history=[("س", "ج")])
    finally:
        socket.socket.connect = original
