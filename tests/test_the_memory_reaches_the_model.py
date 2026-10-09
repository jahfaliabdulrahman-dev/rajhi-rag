"""إثباتُ ما لم يُثبت: **هل يصل السجلُّ والنطاقُ إلى تلقين النموذج فعلًا؟** (R92 · وقرار 98ب)

**ما كان غيرَ مُثبت:** بوّاباتُ البند ١ تُثبت أنّ الدالّة النقيّة تُصيغ الإعلان، وتُثبت أنّ الواجهةَ
**تنادي** بالكلمتين — **ولا تُثبت أنّ ما يُصاغ يبلغ النموذج**. والفرقُ هو الذي يفرّق بين «ميزةٌ
مكتوبة» و«ميزةٌ تعمل».

**كيف يُثبت بلا كلفة:** ببديلِ نموذجٍ **مسجِّل** يُقاس عند حدود المزوّد نفسِها — فما تراه عينُ
النموذج: رسائلُ الخيط (الشرط ١: **رسائلُ لا نصٌّ في التعليمات**)، والنافذةُ بـ`trim_messages`
(الشرط ٣: آخرُ ثلاث دورات والإسقاطُ مُسمًّى بعددِه)، والمخزنُ محدودٌ بالحذف لا بالإخفاء.
والمسحُ عند القراءة (R93-2 · شرط ٢) يُقاس هنا سلوكيًّا وبالـAST في `tests/test_app_binds_history.py`.

**ولماذا `_run_agent` لا `answer_question`:** الثانيةُ لا تبلغ الأولى إلّا بعد بوّابة النطاق
الرقمية — وهي بوّابةٌ صحيحةٌ تُصنَّف صفَّ اختبارٍ واحد «خارج النطاق». فيُقاس الموضعُ الذي
**يُبنى فيه التلقين فعلًا**، ويُقاس **التمريرُ عبر السلسلة** بالـAST في آخر ضابط هنا.

**وما لا يُثبته هذا الملف (يُقال صراحةً):** أن يجيب النموذجُ **أحسن** — أثرٌ لا يُقاس إلا بنداءٍ
مدفوع، وتكلفتُه تُطلب من المالك قبل إنفاقها. **والنِّسبُ المُقيَّدة (`response_format`) لا تُقاس
بالبديل:** قياساتُ العقد (2026-10-08) أثبتت أنّ بديلًا لا يُنتج مخرجاتٍ مُقيَّدة يدور حتى
`GraphRecursionError`، فتُقاس الذاكرةُ على نثرٍ صريح (`response_format=None`) — والمسارُ واحدٌ
لا يتغيّر بالنوع.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

# **حارسُ التبعيّات (قاعدةٌ مقيسة):** بيئتا الـCI بلا LangChain ⇒ بلا هذا السطر **يسقط الاستيرادُ**
# بدل أن يُتخطّى، فيقرأ المشرفُ «فشلٌ» ويظنّ العطبَ في المنطق. الحدُّ: في البيئة الكاملة يعمل (6✓).
pytest.importorskip("langchain")

from langchain_core.language_models.chat_models import BaseChatModel       # noqa: E402
from langchain_core.messages import AIMessage                              # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult              # noqa: E402

from statement_qa import qa                                               # noqa: E402
from statement_qa.qa import MEMORY_TURNS, build_system_prompt              # noqa: E402

QA_SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "statement_qa" / "qa.py"
ROWS = [{"page": 1, "row": 1, "description": "شراء", "amount": "10.00",
         "debit": "10.00", "credit": None, "balance": "100.00",
         "derived_movement": "10.00", "opening": False, "proven": True}]
Q = "وماذا عن الصفحة ٢؟"


class _Recorder(BaseChatModel):
    """بديلُ نموذجٍ **مسجِّل**: يرى ما يصل إليه فعلًا (رسائلُ لا نصّ) — بلا كلفةٍ وبلا مزوّد."""
    calls: list = []

    def _generate(self, messages, stop=None, run_manager=None, **kw):
        self.calls.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=AIMessage("الجواب"))])

    def bind_tools(self, tools, **kw):      # create_agent يربط الأدوات — والمسجِّل يقبلها بلا أثر
        return self

    @property
    def _llm_type(self):
        return "recorder"


def _texts(msgs) -> list[str]:
    return [str(getattr(m, "content", "")) for m in msgs]


def _human(msgs) -> list[str]:
    return [t for m, t in zip(msgs, _texts(msgs)) if getattr(m, "type", "") == "human"]


def _system(msgs) -> str:
    return "\n".join(t for m, t in zip(msgs, _texts(msgs)) if getattr(m, "type", "") == "system")


class _AgentText:
    """بديلُ نتيجة الوكيل — يكفي ليمرّ المسار بلا نموذجٍ حقيقيّ."""

    mode = "tools"
    numbers: list = []
    cited_row_ids: list = []
    unsupported_citations: list = []


def _capture(monkeypatch) -> dict:
    """محطّةُ التقاط التلقين عند `_run_agent` — تُقيس ما **يبنى** لا ما يُرسل (وإرسالُه للمسجِّل)."""
    seen: dict = {}

    def _fake_agent(llm, tools, system_prompt, user_content, **_kw):
        seen["system"], seen["user"] = system_prompt, user_content
        return "الجواب", _AgentText(), "tools"

    monkeypatch.setattr(qa, "_run_agent", _fake_agent)
    return seen


def _ask(**kw):
    return qa._answer_with_tools(object(), ROWS, "قطعةُ سياق", Q, **kw)


def test_the_previous_turn_reaches_the_model_as_messages() -> None:
    """**الدعوى الحاكمة (شرط ١):** السجلُّ السابق يبلغ النموذجَ **رسائلَ** — لا نصًّا داخل
    التعليمات. والقياسُ عند مدخل النموذج نفسه (البديلُ المسجِّل) لا عند نية الكاتب.

    **والكتابةُ صريحةٌ هنا** (R99 · عقدٌ جديد): `_run_agent` صار **يقرأ ولا يكتب** — الكتابةُ
    الوحيدةُ `qa.remember` تُناديها الواجهةُ بما عرضته. فالضابطُ يكتب كما يكتب الإنتاج.
    """
    llm = _Recorder()
    sp = build_system_prompt(scope="كشفُ الاختبار")
    q1 = "كم عدد الحركات في الصفحة ١؟"
    qa._run_agent(llm, [], sp, q1, thread_id="t-reach")
    qa.remember("t-reach", q1, "الجواب")
    qa._run_agent(llm, [], sp, Q, thread_id="t-reach")
    msgs = llm.calls[-1]
    joined = "\n".join(_texts(msgs))
    assert q1 in joined, "السؤالُ السابقُ لم يبلغ النموذج"
    assert "الجواب" in joined, "الجوابُ السابقُ لم يبلغ النموذج (رسائلُ لا نصّ)"
    assert Q in joined, "السؤالُ الحاليُّ لم يبلغ النموذج"
    assert "كشفُ الاختبار" in _system(msgs), "النطاقُ لم يبلغ التلقين"
    assert q1 not in _system(msgs), \
        "السجلُّ عاد نصًّا داخل التعليمات — والشرط ١: رسائلُ لا نصّ"


def test_the_window_keeps_three_turns_and_names_the_drop() -> None:
    """**النافذةُ بـ`trim_messages` (شرط ٣):** آخرُ `MEMORY_TURNS` دورات عند النموذج، والساقطُ
    يُسمّى بعددِه — والمخزنُ لا ينمو بلا سقف (حذفٌ من الحافظة لا إخفاءٌ في التلقين)."""
    llm = _Recorder()
    tid = "t-window"
    for i in range(MEMORY_TURNS + 3):
        qa._run_agent(llm, [], build_system_prompt(), f"س{i}", thread_id=tid)
        qa.remember(tid, f"س{i}", "الجواب")      # الكتابةُ صريحةٌ (R99: `_run_agent` يقرأ ولا يكتب)
    msgs = llm.calls[-1]
    humans = _human(msgs)
    assert humans == [f"س{i}" for i in (2, 3, 4, 5)], \
        f"النافذةُ ليست آخرَ {MEMORY_TURNS} دورات + السؤال: {humans}"
    # **والإسقاطُ يُسمّى بعددِ ما سقط في هذه الخطوة** — والسجلُّ محدودٌ بالحذف (شرط ٣)، فما أُسقط
    # في خطوةٍ سابقة لا أثرَ له يُعدّ من جديد (وهو أقوى من القيد القديم: لا يبقى أصلًا).
    assert f"(و1 دورةً أقدم أُسقطت من النافذة — والحدُّ {MEMORY_TURNS})" in _system(msgs), \
        "الإسقاطُ لم يُسمَّ بعدده عند النموذج"
    # **والتسميةُ صادقةٌ لكلِّ مقدار** (الصيغةُ تُعدّ سقوطَها لا رقمًا واحدًا): خيطٌ بخمسِ دوراتٍ
    # يُسقط دفعةً واحدةً دَورتَين — وهذا قياسُ الصيغة على مدخلٍ كبير لا يبلغه التخزينُ المحدود.
    from langchain_core.messages import AIMessage as _AI, HumanMessage as _H

    prior = [m for i in range(5) for m in (_H(f"س{i}", id=f"h{i}"), _AI(f"ج{i}", id=f"a{i}"))]
    kept, removals, note = qa._window(prior)
    assert len(kept) == 2 * MEMORY_TURNS and len(removals) == 2 * 2, (len(kept), len(removals))
    assert note == f"(و2 دورةً أقدم أُسقطت من النافذة — والحدُّ {MEMORY_TURNS})", note
    # **وعلى شكلِ الإنتاج (دورُ الأداة أربعُ رسائل لا ثنتان):** النافذةُ تُبقي ثلاثَ دوراتٍ على
    # الحالتين — وهذا قياسُ العطب الذي أمسكه مقعدُ البنية (قبل التصحيح: يبقى **دورةٌ واحدة** من
    # أربع ويُعلَن «و6 أُسقطت»؛ ووحدةُ الميزانية صارت **دُورًا** بموضعِ عدٍّ واحد `_turns`).
    from langchain_core.messages import ToolMessage as _T

    tool_msgs = []
    for i in range(4):
        tool_msgs += [_H(f"ط{i}", id=f"th{i}"),
                      _AI("؟", id=f"tq{i}", tool_calls=[{"name": "sum_rows", "args": {}, "id": f"tc{i}"}]),
                      _T("نتيجة", id=f"tt{i}", tool_call_id=f"tc{i}"),
                      _AI(f"ج{i}", id=f"ta{i}")]
    kept2, removals2, note2 = qa._window(tool_msgs)
    assert len(kept2) == 4 * 3 and _human(kept2) == ["ط1", "ط2", "ط3"], \
        f"النافذةُ ليست ثلاثَ دوراتٍ على شكل الأداة: {[m.type for m in kept2]}"
    assert len(removals2) == 4 and note2 == f"(و1 دورةً أقدم أُسقطت من النافذة — والحدُّ {MEMORY_TURNS})", \
        (len(removals2), note2)
    stored = qa._thread_messages({"configurable": {"thread_id": tid}})
    assert len(stored) <= 2 * MEMORY_TURNS + 2, f"الحافظةُ تنمو بلا سقف: {len(stored)} رسالة"


def test_a_new_statement_wipes_the_conversation() -> None:
    """**R93-2 · شرط ٢ (جهةُ الحافظة):** `clear_conversation` يمحو الخيط — فكلُّ قراءةٍ تبدأ نظيفة.
    (ومسارُ الواجهة الكاملُ يُقاس بالـAST في `test_app_binds_history::test_the_read_wipes_the_conversation_too`
    — وهذا الضابطُ يقيس الدالّةَ عند الحافظة وحدها، لا سيناريو النقر.)"""
    llm = _Recorder()
    tid = "t-wipe"
    qa._run_agent(llm, [], build_system_prompt(), "سؤالٌ سابق", thread_id=tid)
    qa.remember(tid, "سؤالٌ سابق", "جوابٌ سابق")     # الكتابةُ صريحةٌ (R99)
    qa.clear_conversation(tid)
    qa._run_agent(llm, [], build_system_prompt(), "سؤالٌ جديد", thread_id=tid)
    msgs = llm.calls[-1]
    assert _human(msgs) == ["سؤالٌ جديد"], "القديمُ عاد بعد المسح — والكشفُ الجديدُ يبدأ نظيفًا"
    assert "أوّلُ سؤال" in _system(msgs), "المسحُ المُعلن («أوّلُ سؤال») غاب"


def test_without_memory_the_prompt_is_the_old_one_to_the_letter(monkeypatch) -> None:
    """**وقياسُ النقيض:** بلا خيطٍ ولا نطاقٍ ⇒ نصُّ الوكيل الأصليّ بحرفه (لا انزلاقَ صامت)."""
    seen = _capture(monkeypatch)
    _ask()
    assert seen["system"] == qa.AGENT_SYSTEM_PROMPT


def test_the_model_is_asked_the_question_it_was_given(monkeypatch) -> None:
    """**ولا يُنقل النصُّ من مكانه:** سؤالُ المستخدم المُرسَل هو السؤالُ نفسُه."""
    seen = _capture(monkeypatch)
    _ask(scope="نطاق")
    assert Q in seen["user"]


def test_the_whole_chain_forwards_the_two_arguments() -> None:
    """**والسلسلةُ تمرّر (AST):** `answer_question` تُعلن المُفتاحَ والنطاق **وتمرّرهما** إلى `_answer_one`."""
    tree = ast.parse(QA_SRC.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "answer_question")
    names = {a.arg for a in fn.args.args}
    assert {"thread_id", "scope"} <= names, f"answer_question لا تُعلنهما: {sorted(names)}"
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "_answer_one"]
    assert calls, "لا نداءَ لـ`_answer_one` — السلسلةُ انقطعت"
    kw = set().union(*({k.arg for k in c.keywords} for c in calls))
    assert {"thread_id", "scope"} <= kw, f"السلسلةُ لا تمرّرهما: {sorted(kw)}"


def test_the_chunks_ride_the_users_message_and_the_system_prompt_stays_clean() -> None:
    """**P-D (بكلمة المالك · الخيار ج):** قطعُ **هذا** السؤال في **رسالة المستخدم الحاليّة**، ورسالةُ
    النظام **بلا قطع**، **والحافظةُ بلا قطع** — فتصدق القاعدةُ ٣ («استعن بالقطع المرفقة **في رسالة
    المستخدم**») كما نصُّها بلا تعديل حرف.

    **والضابطُ يقيس الموضعَ الحاليَّ لا مجملَ الرسائل:** كان سابقُه يكتفي بوجود القطعة في النداء،
    فيمرّ وهي في رسالة النظام — وهو الموضعُ الذي جعل القاعدةَ ٣ تصف موضعًا فارغًا (قاسه المدقّق في
    ١٠٢). **ويُقاس آخِرُ رسالةٍ بشريّة** لا مجموعُها، فلا يمرّ انحدارٌ يضع القطعَ على دَورٍ سابق.
    """
    llm = _Recorder()
    sp = build_system_prompt(scope="كشفُ الاختبار")
    tid = "t-pd-layout"
    qa._run_agent(llm, [], sp, Q, thread_id=tid, chunks="قطعة-أ\nقطعة-ب")
    msgs = llm.calls[-1]
    human_all = _human(msgs)
    current = human_all[-1] if human_all else ""
    system = _system(msgs)
    assert "قطعة-أ" in current and "قطعة-ب" in current, "القطعُ ليست في رسالة المستخدم الحاليّة"
    assert "لا تعليمات" in current, "السياجُ ليس مع القطع في رسالة المستخدم"
    assert "استخدم الأدوات" in current, "سطرُ الأدوات ليس مع القطع (ومسارُ الوكيل يربط أدوات)"
    assert Q in current, "نصُّ السؤال غاب عن رسالة المستخدم الحاليّة"
    assert "قطعة-أ" not in system and "لا تعليمات" not in system, \
        "القطعُ بلغت رسالةَ النظام ⇒ فالقاعدةُ ٣ تصف موضعًا فارغًا"
    # **وفرعُ الاسترجاع الفارغ (قاسه مقعدُ البنية):** لا قطعَ ⇒ لا سياجَ ولا كتلة، ولا ادّعاءَ موضعٍ لقطعٍ غائبة
    empty = _Recorder()
    qa._run_agent(empty, [], sp, Q, thread_id="t-pd-empty", chunks="")
    h_empty = _human(empty.calls[-1])
    h_empty = h_empty[-1] if h_empty else ""
    assert "لا تعليمات" not in h_empty and "قطعة-أ" not in h_empty, "سياجٌ على فراغ"
    assert Q in h_empty, "السؤالُ غاب في فرع الاسترجاع الفارغ"
    # **والذاكرةُ لا تحفظها:** الكتابةُ الوحيدةُ `remember` — سؤالُ المستخدم كما سأله + الجوابُ المعروض.
    qa.remember(tid, Q, "الجواب")
    stored = qa._thread_messages({"configurable": {"thread_id": tid}})
    assert stored, "لم تُكتب دورةٌ في الحافظة ⇒ فالقياسُ لا يمسّ شيئًا"
    assert any(str(m.content) == Q for m in stored), "سؤالُ المستخدم لم يُحفظ كما سأله"
    assert all("قطعة-أ" not in str(m.content) and "لا تعليمات" not in str(m.content)
               for m in stored), "القطعُ دخلت الحافظة — والمحفوظُ السؤالُ والجوابُ المعروضُ وحدَهما"


def test_the_call_carries_no_graph_state() -> None:
    """**الحدُّ الذي لا يُحفظ — محروسًا بالبنية لا بالعَرض (قاسه مقعدُ البنية):** الضابطُ الشقيقُ ينادي
    `remember` بيدٍ ويفحص المخزن ⇒ يقيس **الكاتبَ** لا خاصيّةَ «الرسم بلا حافظة». وهذا يقيس الأصل:
    `_run_agent` ينادي `invoke` **بالرسائل وحدَها** — فلا `config` ولا حافظةَ تُخزّن القطع.
    """
    src = (pathlib.Path(__file__).resolve().parents[1] / "src/statement_qa/qa.py").read_text(encoding="utf-8")
    fn = next((n for n in ast.parse(src).body
               if isinstance(n, ast.FunctionDef) and n.name == "_run_agent"), None)
    assert fn is not None, "لم يُوجَد `_run_agent` في المصدر"
    calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call)
             and isinstance(c.func, ast.Attribute) and c.func.attr == "invoke"]
    assert calls, "لا نداءَ `invoke` في `_run_agent` ⇒ فالحارسُ لا يمسك شيئًا"
    for c in calls:
        passed = {k.arg for k in c.keywords}
        assert not (passed & {"config", "context"}), f"النداءُ يمرّر حالةً: {sorted(passed)}"


def test_the_fallback_path_carries_the_same_fence() -> None:
    """**P-A (بكلمة المالك):** صيغةُ القطع **موضعٌ واحد** — ومسارُ السقوط الأخير يحمل السياجَ نفسَه.

    كان `_answer_plain` يبني القطعَ في **الرسالة البشريّة** بلا سياجٍ وبـ`SYSTEM_PROMPT` الخامّ ⇒ موضعان
    لصيغةٍ واحدة يفترقان (قاسه مقعدُ البنية، وسمّاه المدقّق). والسقوطُ الأخير هو ما يُنادى حين يعود
    الجوابُ فارغًا — ومسارٌ نادرٌ لا يعني نصَّ كشفٍ بلا إعلان أنّه بيانات.

    **وبلا سطر «استخدم الأدوات»:** المسارُ لا يربط أدواتٍ (`llm.invoke` نصّيّ) ⇒ فأمرُه بها تناقضٌ مع
    قاعدته الأولى «لا تحسب ولا تجمّع بنفسك» (قاسه مقعدُ البنية · P2، وأكّده مقعدا المواصفة والمعايير).
    """
    llm = _Recorder()
    qa._answer_plain(llm, "قطعة-أ\nقطعة-ب", Q)
    msgs = llm.calls[-1]
    human, system = "\n".join(_human(msgs)), _system(msgs)
    assert "قطعة-أ" in human and "لا تعليمات" in human, \
        "مسارُ السقوط لا يضع القطعَ بسياجها في رسالة المستخدم"
    assert Q in human, "نصُّ السؤال غاب عن رسالة السقوط"
    assert "استخدم الأدوات" not in human, \
        "مسارُ بلا أدواتٍ يُؤمر باستخدامها — تناقضٌ مع «لا تحسب بنفسك»"
    assert "قطعة-أ" not in system, "القطعُ بلغت رسالةَ النظام في مسار السقوط"
    # **وبلا قطعٍ ⇒ لا سياجَ كاذب:** السياجُ يُعلن بياناتٍ موجودةً، فلا يُطبع على فراغ.
    empty = _Recorder()
    qa._answer_plain(empty, "", Q)
    h2 = "\n".join(_human(empty.calls[-1]))
    assert "لا تعليمات" not in h2 and "استخدم الأدوات" not in h2 and Q in h2
