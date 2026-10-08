"""البندُ ١ (R92 · وقرار 98ب): **قوالبُ التلقين وذاكرةُ الحوار** — بوّاباتٌ بلا نداء نموذج.

**العطبُ الذي تمنعه:** كان تلقينُ الوكيل **نصًّا مجمَّدًا** لا يعرف نطاقَ الكشف ولا سؤالَه السابق ⇒
فسؤالٌ تابعٌ («وماذا عن الصفحة ٤؟») يُجاب كأنّه مبتدأ، أو يُنقل فيه رقمٌ من جوابٍ سابق بلا أداة.

**وما تُثبته هذه البوّابات (لا تُدّعيه):** ① القالبُ يُصيغ بالنطاق ويُعلن **حدَّ الذاكرة** من
`MEMORY_TURNS` لا من يد ② وسطرُ الإعلان يُسمّي الإسقاطَ بعددِه ويقول «أوّلُ سؤال» للفراغ
③ ولا نداءَ شبكةٍ في المسار كلّه ④ **والتوصيلُ لا يكسر القائم:** بلا ذاكرةٍ ولا نطاقٍ يبقى التلقينُ
نصَّه القديم بحرفه — والدالّةُ اليدويّة (`format_history`/`history_pairs`) محذوفةٌ لا تعود (لا طريقان).
**ونافذةُ `trim_messages` نفسُها** (القصُّ عند النموذج والتخزينُ المحدود) تُقاس في
`tests/test_the_memory_reaches_the_model.py` حيث تُحمَّل التبعيّة.
"""

from __future__ import annotations

import socket

from statement_qa.qa import (AGENT_SYSTEM_PROMPT, MEMORY_TURNS, _memory_note,
                             build_system_prompt)


def test_the_template_renders_its_variables_and_declares_the_scope() -> None:
    """**القالبُ لا نصٌّ مجمَّد:** النطاقُ يظهر، والحدُّ يُعلن من `MEMORY_TURNS` لا يُكتب بالحرف."""
    out = build_system_prompt(scope="كشفُ ٦٢٩ صفحة · بنك الراجحي", with_memory=True)
    assert "كشفُ ٦٢٩ صفحة" in out
    assert f"آخرُ {MEMORY_TURNS} دورات" in out, "حدُّ الذاكرة يُعلن من مصدره لا من يد"
    assert "لا يُنقل عنه رقمٌ بلا أداة" in out, "القاعدةُ الحاكمة للسجلّ لا تُشطب من القالب"
    assert AGENT_SYSTEM_PROMPT.splitlines()[0] in out, "نصُّ الوكيل الأصليّ يبقى أساسَ القالب"
    assert "ذاكرةُ الحوار" not in build_system_prompt(scope="حزمةٌ بلا خيط"), \
        "مُستدعٍ بلا ذاكرةٍ يُخاطَب بحفظٍ لا وجودَ له (تصحيحُ مقعد المعايير)"


def test_the_memory_window_is_bounded_and_the_drop_is_declared() -> None:
    """**حدٌّ مُعلَن لا ذاكرةٌ تنمو:** ما سقط يُسمّى بعددِه، وبلا سجلٍّ يُعلَن «أوّلُ سؤال» صراحةً.

    (والإزاحةُ نفسها بالحرف تصل التلقينَ عند النموذج — مقيسةٌ في الملف المحمّل.)
    """
    note = _memory_note(5, 2)
    assert note == f"(و2 دورةً أقدم أُسقطت من النافذة — والحدُّ {MEMORY_TURNS})", note
    assert _memory_note(MEMORY_TURNS, 0) == "", "بلا سقوطٍ لا حشو"
    assert "أوّلُ سؤال" in _memory_note(0, 0), "بلا سجلٍّ يُقال ذلك صراحةً"


def test_the_wiring_is_backward_compatible() -> None:
    """**توافقٌ خلفيّ:** بلا ذاكرةٍ ولا نطاقٍ ⇒ التلقينُ نصُّه القديم بحرفه (فلا سلوكَ يتبدّل)."""
    assert build_system_prompt(scope="نطاق") != AGENT_SYSTEM_PROMPT, "بالنطاق يُبنى القالبُ الموسَّع"
    # والقرارُ في موضع التوصيل: `thread_id or scope` — يُقاس بالنصّ الحرفيّ في الوحدة
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[1] / "src" / "statement_qa" / "qa.py"
    text = src.read_text(encoding="utf-8")
    assert "if (thread_id or scope) else AGENT_SYSTEM_PROMPT" in text, "شرطُ التوافق الخلفيّ غائب"
    # **ولا طريقان (قرار 98ب):** الدالّةُ اليدويّةُ لا تعود بأيّ اسم.
    assert "def format_history" not in text and "def history_pairs" not in text, \
        "الدالّةُ اليدويّةُ رجعت — والسجلُّ صار رسائلَ لا نصًّا"


def test_no_network_in_the_prompt_path() -> None:
    """**«بلا كلفة» مُثبتٌ لا مُدَّعى:** يُفخّ المنفذُ فيسقط أيُّ نداءٍ — والقالبُ يمرّ."""

    def _deny(*_a, **_k):
        raise AssertionError("نداءُ شبكةٍ في مسار التلقين — والوعدُ: بلا كلفة")

    original = socket.socket.connect
    socket.socket.connect = _deny                      # type: ignore[method-assign]
    try:
        assert build_system_prompt(scope="عيّنة")
    finally:
        socket.socket.connect = original
