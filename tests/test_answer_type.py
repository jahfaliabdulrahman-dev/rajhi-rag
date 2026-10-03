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

    def invoke(self, _msgs):
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

    # وبسؤالٍ وصفيٍّ (لا يحتاج أداة) يصل الجوابُ المُقيَّد باستشهاداته
    res2 = q._answer_one(store=_Store(), question="بيّن الصفوف التي فيها رسوم حوالة", rows=rows,
                         chunks=None, llm=object(), k=2, footers=None)
    assert res2.answer.startswith("المجموع"), res2.answer[:40]
    assert res2.citation_mode == "typed" and res2.cited_row_ids == [1, 4]
    assert res2.unsupported_citations == [1, 4], "الإصلاحُ لم يُقابَل بالأثر"
