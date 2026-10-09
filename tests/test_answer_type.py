"""بوّاباتُ جوابٍ مُقيَّدٍ نوعًا (أ-٤) — **بلا نداءِ نموذجٍ واحد**: يُقاس البديلُ في موضع النموذج.

**البوابة (من الخارطة):** «سؤالٌ يعود بكائنٍ مقيَّد نوعًا فيه `cited_row_ids` مُصرَّحٌ بها، ويُقابَل
بالأثر». وقياسُها المدفوع **ينتظر كلمة المالك** — أمّا ما يُقاس هنا فالشكلُ والمقابلةُ والوضعُ المُعلَن:
«**النوعُ يُصلح الاستخراج · والأثرُ يُصلح الصدق**» ⇒ كلاهما يُقاس ببديلٍ في موضع النموذج، بكلفة صفر.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import statement_qa.qa as q                       # noqa: E402

# **والحارسُ على التبعيّات لا على الاستيراد** (مقعدُ أ-٤ P1 · مُثبت): كان `try: import … except
# ImportError: skip` — وقد **أعدمه** الاستيرادُ المتسامحُ في الوحدة نفسِها (الاستيرادُ ينجح دائمًا)
# ⇒ فمجموعةٌ تدّعي التخطّي و**تسقط ٤ من ٦** في البيئة الخفيفة. فيُحرس الآن على ما يلزم فعلًا.
_DEPS = []
for _mod in ("pydantic", "langchain"):
    try:
        __import__(_mod)
    except ImportError:                           # noqa: PERF203
        _DEPS.append(_mod)
pytestmark = pytest.mark.skipif(
    bool(_DEPS), reason=f"طبقةُ الوكيل تحتاج {'، '.join(_DEPS)} — تُقاس في البيئة الكاملة")
from statement_qa.qa_tools import citation_truth   # noqa: E402
from statement_qa.render import evidence_mode      # noqa: E402


class _Msg:
    """رسالةٌ بشكل LangChain الحقيقيّ (`.content`) — فالبديلُ يحاكي الشكلَ لا يُبسّطه."""

    def __init__(self, content):
        self.content = content


class _Store:
    """مخزنٌ بديل: بلا فهرسةٍ ولا شبكة ⇒ مسارُ الاسترجاع يمرّ فارغًا ويُقاس ما بعده."""

    def similarity_search_with_score(self, *_a, **_k):
        return []


class _Agent:
    """بديلُ الوكيل: يُعيد ما نُريد بلا شبكةٍ ولا نموذج."""

    def __init__(self, payload):
        self.payload = payload

    def invoke(self, _msgs, **_kw):
        # **التوقيعُ يتبع العقد** (سابقةُ هذه الحيلة في `test_qa_footer_tool`): كان `_run_agent`
        # يمرّر `config=` (معرّفَ الخيط — قرار 98ب)، ثمّ `context=` (سياقُ النداء — R99)، **وبعد P-1
        # ينادي `invoke(messages)` وحدَها** (القطعُ صارت في التلقين، والذاكرةُ تُكتب في `remember`).
        # و`**_kw` تتبعُ العقد لا تستثنيه: البديلُ الذي يتخلّف عن توقيعٍ يتغيّر يسقط بـ`TypeError`
        # يلتقطه `except Exception` في `_answer_one`، فيظهر العطبُ بعيدًا عن سببه (قِيس مرّتين).
        return self.payload


def _patch_agent(monkeypatch, payload, *, reject_kwargs=False):
    """يُبدّل `create_agent` ويلتقط الوسائطَ ⇒ يُقاس التمريرُ بلا نموذج."""
    seen: dict = {}

    def fake(**kw):
        seen.update(kw)
        if reject_kwargs and "response_format" in kw:
            raise TypeError("unexpected keyword argument 'response_format'")
        return _Agent(payload)

    import langchain.agents as la
    monkeypatch.setattr(la, "create_agent", fake)
    return seen


def test_the_answer_type_declares_its_citations():
    """النوعُ يُصرّح: نصٌّ + أرقامُ صفوفٍ صحيحة + امتناعٌ صريح."""
    a = q.Answer(answer="المجموع ١٠٠", cited_row_ids=[5, 7])
    assert a.cited_row_ids == [5, 7] and a.refused is False
    b = q.Answer(answer="لا أستطيع", cited_row_ids=["3"])   # نصٌّ رقميّ يُقيَّد عددًا
    assert b.cited_row_ids == [3]
    assert set(q.Answer.model_fields) >= {"answer", "cited_row_ids", "refused"}


def test_a_citation_without_a_witness_is_named():
    """**«الأثرُ يُصلح الصدق»:** استشهادٌ لا شاهدَ له في الأثر يُسمّى ولا يُحذف."""
    trace = [{"tool": "sum_rows", "row_nos": [5, 6]}]
    got = citation_truth([5, 7, 9], trace)
    assert got["witnessed"] == [5, 6]
    assert got["unsupported"] == [7, 9], got
    assert citation_truth([5], [])["unsupported"] == [5]      # بلا أثر: كلُّ استشهادٍ بلا شاهد
    assert citation_truth(["7", "كذا"], trace)["cited"] == [7]  # مدخلٌ غيرُ رقميّ لا يُخترع له صفّ


def test_the_agent_is_built_with_the_type_and_the_downgrade_is_declared(monkeypatch):
    """**التوصيلُ يُقاس ببديلٍ في موضع النموذج:** الوسيطُ يمرّ فعلًا، ونسخةٌ لا تعرفه ⇒ `prose` مُعلَن."""
    seen = _patch_agent(monkeypatch, {"messages": [_Msg("نثرٌ")]})
    text, parsed, mode = q._run_agent(object(), [], "s", "u", response_format=q.Answer)
    assert "response_format" in seen and seen["response_format"] is q.Answer, seen.keys()
    assert (text, parsed, mode) == ("نثرٌ", None, "prose"), "بلا كائنٍ مُقيَّد يُعلَن النصّيّ"

    _patch_agent(monkeypatch, {"messages": [_Msg("نثرٌ")]}, reject_kwargs=True)
    text2, _p2, mode2 = q._run_agent(object(), [], "s", "u", response_format=q.Answer)
    assert text2 == "نثرٌ" and mode2 == "prose", "نسخةٌ ترفض الوسيط ⇒ لا انحدارَ صامت"


def test_the_typed_field_wins_over_the_prose(monkeypatch):
    """**«النوعُ يُصلح الاستخراج»:** النصُّ يقول شيئًا والكائنُ يقول غيرَه ⇒ الكائنُ يُعتمد."""
    payload = {"structured_response": q.Answer(answer="من النوع: ١٢٣", cited_row_ids=[3]),
               "messages": [_Msg("من النثر: ٩٩٩")]}
    _patch_agent(monkeypatch, payload)
    text, parsed, mode = q._run_agent(object(), [], "s", "u", response_format=q.Answer)
    assert (text, mode) == ("من النوع: ١٢٣", "typed")
    assert parsed.cited_row_ids == [3]


def test_the_panel_prefers_the_typed_citations():
    """اللوحةُ تعرض **المُصرَّح به** لا ما قُصّ من النثر — و`none` تبقى أولًا (تعذُّرُ الأدوات)."""
    class _R:
        used_row_nos = [5]
        cited_row_ids = [3, 7]
        citation_mode = "typed"

    assert evidence_mode(_R()) == "typed"
    _R.citation_mode = "prose"
    assert evidence_mode(_R()) == "tools"
    _R.tools_failed = True
    assert evidence_mode(_R()) == "none", "جوابٌ لم يُحسَب لا تُعرض له أدلّةٌ ولو استشهد"


def test_the_whole_answer_carries_the_typed_citations(monkeypatch):
    """**من السؤال إلى الكائن:** المسارُ الكاملُ يُقاس بوكيلٍ بديلٍ — بلا نداءٍ مدفوع."""
    rows = [{"row_no": i, "page": 1, "printed_page": 1, "desc": f"سطر {i}", "date": "2026-01-01",
             "movement": "10.00", "side": "debit", "balance": "10.00", "printed_movement": "10.00",
             "printed_balance": "10.00", "counted": 1, "row_state": "عادي", "source": "طباعة"}
            for i in range(1, 6)]
    payload = {"structured_response": q.Answer(answer="المجموع ١٠٫٠٠", cited_row_ids=[1, 4]),
               "messages": [_Msg("نثرٌ لا يهمّ")]}
    _patch_agent(monkeypatch, payload)
    # الأدواتُ تُبنى من الصفوف نفسِها ⇒ فالشاهدُ يأتي من أثرٍ حقيقيّ حين تُستدعى
    res = q._answer_one(store=_Store(), question="كم مجموع السحوبات؟", rows=rows, chunks=None,
                        llm=object(), k=2, footers=None)
    # **وهنا المسارُ الصادقُ الآخر:** سؤالٌ رقميٌّ ولم تُستدع أداة ⇒ **رفضٌ لا وسم** (لا رقمَ بلا حساب)
    assert res.ungrounded is True and res.answer.startswith("لم أستطع"), res.answer[:60]
    # **وامتناعٌ لا يحمل استشهادًا** (مقعدُ أ-٤ P3): كان الكائنُ يقول «لم أستطع» ومعه نوعٌ واستشهادات
    assert res.citation_mode == "prose" and res.cited_row_ids == [], (
        res.citation_mode, res.cited_row_ids)

    # **وبسؤالٍ وصفيٍّ يصل الجوابُ المُقيَّد باستشهاداته** — بشرط ألّا يحمل الجوابُ **مبلغًا** (فالبوّابةُ
    # تقرأ الجوابَ منذ R104-1: مبلغٌ بلا نداءِ أداةٍ يُرفض ولو كان السؤالُ وصفيًّا — ويقاس أدناه).
    _patch_agent(monkeypatch, {"structured_response":
                               q.Answer(answer="الصفوف ١ و٤ فيها رسوم حوالة", cited_row_ids=[1, 4]),
                               "messages": [_Msg("نثرٌ لا يهمّ")]})
    res2 = q._answer_one(store=_Store(), question="بيّن الصفوف التي فيها رسوم حوالة", rows=rows,
                         chunks=None, llm=object(), k=2, footers=None)
    assert res2.answer.startswith("الصفوف"), res2.answer[:40]
    assert res2.citation_mode == "typed" and res2.cited_row_ids == [1, 4]
    assert res2.unsupported_citations == [1, 4], "الإصلاحُ لم يُقابَل بالأثر"


def test_a_money_answer_without_a_tool_call_is_refused_even_when_the_question_is_not_numeric(monkeypatch):
    """**R104-1 — P2 قائمٌ على `main` (قاسه المدقّق في مراجعة ١٠٤):** بوّابةُ «لا رقمَ بلا أداة» كانت تقرأ
    **السؤال** (`needs_tools` ⇒ «كم/مجموع/عدد…») ولا تقرأ **الجواب** ⇒ فسؤالُ سلسلةٍ بلا كلمةٍ رقميّة
    («هل يتّصل الرصيد…؟») يُجاب بمبالغَ **لم تحسبها أداةٌ** ويُعرض للمستخدم **بلا إنذار** — وقِيس في الحزمة:
    `chn-04` بستّةَ عشرَ رقمًا وصفرِ صفوف.

    **وما يقيسه هذا الضابط:** جوابٌ يحمل مبلغًا بشكل المال (خانتان عشريّتان) بلا **نداءِ أداة** ⇒ توجيهٌ
    بقاعدةٍ ثمّ **رفض** — أيًّا كانت صيغةُ السؤال. **وحدُّه:** «صف 23» و«2026» ليست مبالغَ (بلا كسرٍ عشريّ)،
    فلا تُطلَق البوّابةُ على جوابٍ وصفيٍّ سليم.
    """
    rows = [{"row_no": i, "page": 1, "printed_page": 1, "desc": f"سطر {i}", "date": "2026-01-01",
             "movement": "10.00", "side": "debit", "balance": "10.00", "printed_movement": "10.00",
             "printed_balance": "10.00", "counted": 1, "row_state": "عادي", "source": "طباعة"}
            for i in range(1, 6)]
    # سؤالٌ **بلا** كلمةٍ رقميّة («هل…؟») وجوابٌ يحمل مبالغَ بلا أيّ أداة
    _patch_agent(monkeypatch, {"structured_response":
                               q.Answer(answer="لا يتّصل: رصيد 242.00 مقابل 236.00", cited_row_ids=[]),
                               "messages": [_Msg("نثرٌ لا يهمّ")]})
    res = q._answer_one(store=_Store(), question="هل يتّصل رصيد الصفحة الثانية برصيد الأولى؟",
                        rows=rows, chunks=None, llm=object(), k=2, footers=None)
    assert res.ungrounded is True, "مبلغٌ في الجواب بلا نداءِ أداةٍ مرّ بلا رفض"
    assert res.answer.startswith("لم أستطع"), res.answer[:60]
    assert res.tools_used == [], f"أدواتٌ بلا رفض: {res.tools_used}"
    # **ونقيضُه:** المبلغُ نفسه **مع** نداءِ أداة (ولو بلا صفوف) يمرّ — فالحدُّ `_tool_was_used` لا `used`
    assert q._tool_was_used([{"tool": "page_footer", "row_nos": []}]) is True


def test_a_numeric_answer_without_money_is_not_refused_by_the_new_branch(monkeypatch):
    """**ولا تُوسَّع البوّابةُ بلا حدّ:** جوابٌ وصفيٌّ فيه أرقامٌ **بلا شكلِ المال** («الصفوف ١ و٤» ·
    «الصفحة 628») يمرّ كما كان — فالحدُّ **شكلُ المبلغ** لا وجودُ رقم."""
    rows = [{"row_no": i, "page": 1, "printed_page": 1, "desc": f"سطر {i}", "date": "2026-01-01",
             "movement": "10.00", "side": "debit", "balance": "10.00", "printed_movement": "10.00",
             "printed_balance": "10.00", "counted": 1, "row_state": "عادي", "source": "طباعة"}
            for i in range(1, 6)]
    _patch_agent(monkeypatch, {"structured_response":
                               q.Answer(answer="الصفحة 628 فيها الصفوف 12 و34", cited_row_ids=[]),
                               "messages": [_Msg("نثرٌ لا يهمّ")]})
    res = q._answer_one(store=_Store(), question="بيّن الصفوف التي فيها رسوم حوالة", rows=rows,
                        chunks=None, llm=object(), k=2, footers=None)
    assert res.ungrounded is False, "رقمٌ بلا شكلِ مبلغٍ أُرفض خطأً"
    assert res.answer.startswith("الصفحة 628"), res.answer[:40]


def test_a_failed_tool_path_carries_no_type_and_no_citation(monkeypatch):
    """**إصلاحُ الصنف لا الموضع** (قاسه السؤالُ المدفوع الأوّل · مُثبت):

    أصلحتُ فرعَ الامتناع وتركتُ فرعَ **تعذُّر الأدوات** ⇒ فقِيس في نداءٍ حقيقيّ أنّ جوابًا **بلا أثرِ
    أداةٍ** يحمل `citation_mode="typed"` واستشهادات ستٍّ (`unsupported=[...]`) — أي **استشهادٌ بلا
    حساب**. والقاعدة: **من لا أثرَ له لا نوعَ له** — والمعيارُ واحدٌ في الفرعين.
    """
    rows = [{"row_no": i, "page": 1, "printed_page": 1, "desc": f"س{i}", "date": "2026-01-01",
             "movement": "10.00", "side": "debit", "balance": "10.00", "printed_movement": "10.00",
             "printed_balance": "10.00", "counted": 1, "row_state": "عادي", "source": "طباعة"}
            for i in range(1, 4)]

    def _boom(**_kw):                       # الوكيلُ يفشل: أدواتُه لم تجرِ
        raise RuntimeError("عطبٌ مُفتعَل في الوكيل")

    class _LLM:
        """نموذجٌ بديلٌ للنثر: `_answer_one` يسقط إلى `_answer_plain` بعد تعذُّر الأدوات."""

        def invoke(self, _msgs):
            return _Msg("نثرٌ بلا أداة")

    import langchain.agents as la
    monkeypatch.setattr(la, "create_agent", _boom)
    res = q._answer_one(store=_Store(), question="كم مجموع السحوبات؟", rows=rows, chunks=None,
                        llm=_LLM(), k=2, footers=None)
    assert res.tools_failed is True, "لم يُقَس مسارُ تعذُّر الأدوات"
    assert res.citation_mode == "prose" and res.cited_row_ids == [], (
        f"جوابٌ بلا أثرِ أداةٍ حمل نوعًا أو استشهادًا: {res.citation_mode} · {res.cited_row_ids}")
    assert res.unsupported_citations == []


def test_a_compound_question_carries_its_parts_tool_names(monkeypatch):
    """**R104-1 · P1 (قاسه مقعدا المواصفة والبنية):** جمعُ الأجزاء كان يبني `QAResult` المُدمَج
    بـ`used_row_nos` وحدَها **ويُسقِط `tools_used`** ⇒ فسؤالٌ مركّبٌ (وهو نصفُ أسئلة الحزمة، ومنها
    `chn-03` و`chn-04` في تجربة R104) يُسجَّل «بلا أدوات» أيًّا كان ما استدعاه النموذج — وهو **عينُ ما
    وُلد الحقلُ لفصله** («صفرُ صفوف» ≠ «لا نداء»).

    **وما يقيسه:** سؤالٌ مركّبٌ جزآن، كلٌّ استدعى أداةً ⇒ الأسماءُ تجتمع في النتيجة المُدمَجة. ولو أُسقِط
    الدمجُ لسقط الضابط (وهو نقصٌ مُثبتٌ في شجرة R104 قبل الإصلاح).
    """
    rows = [{"row_no": i, "page": 1, "printed_page": 1, "desc": f"سطر {i}", "date": "2026-01-01",
             "movement": "10.00", "side": "debit", "balance": "10.00", "printed_movement": "10.00",
             "printed_balance": "10.00", "counted": 1, "row_state": "عادي", "source": "طباعة"}
            for i in range(1, 6)]
    calls = {"n": 0}

    def fake(store, part, rows_, chunks, llm, k, footers=None, thread_id=None, scope=""):
        calls["n"] += 1
        return q.QAResult(answer=f"جزءٌ {calls['n']}", sources=[], used_row_nos=[calls["n"]],
                         tools_used=["row_chain"] if calls["n"] == 1 else ["page_footer"])

    monkeypatch.setattr(q, "_answer_one", fake)
    assert len(q.split_compound("هل يتّصل الرصيد؟ وما مجموع المدين؟")) > 1, "المِثالُ ليس مركّبًا"
    res = q.answer_question(store=_Store(), question="هل يتّصل الرصيد؟ وما مجموع المدين؟", rows=rows,
                            chunks=None, llm=object(), k=2, footers=None)
    assert sorted(res.tools_used) == ["page_footer", "row_chain"], \
        f"أسماءُ أجزاء السؤال المركّب غابت أو ضاعت: {res.tools_used}"
    assert res.used_row_nos == [1, 2], res.used_row_nos