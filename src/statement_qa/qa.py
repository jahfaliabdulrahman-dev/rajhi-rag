"""QA layer: LangChain agent with DETERMINISTIC tools over the verified table.

Contract (plan + owner rules):
- The model NEVER computes: every number comes from a tool call or a retrieved
  chunk. Answers quote evidence (page/row); missing evidence → refusal string.
- With `rows` supplied, a LangChain agent runs with tools from qa_tools
  (sum/count/extremes/page summary/**page rows**/search) — so "كم مجموع السحوبات؟" gets a
  real computed number, not a refusal.
- The tools record an execution TRACE (which rows each call selected); the
  evidence panel is built from that trace — what BUILT the numbers — not from
  the row refs the answer prose happens to repeat.
- Without rows (or if the agent path fails), falls back to strict one-shot RAG.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

# **والاستيرادُ متسامحٌ عن قصد (قِيس):** كان `from pydantic import …` في الرأس ⇒ فصارت الوحدةُ
# تحتاج pydantic **لتُستورَد**، فنقص جمعُ البيئة الخفيفة (بلا langchain/pydantic) بلا رسالة.
# **والرقمُ المقيسُ بدقّة (مقعدُ أ-٤ · مُثبت):** صافي الفرق **٢١ ضابطًا** = ١٥ من ملفّ الإفصاح
# (`test_disclosure_and_provenance.py`) + ٦ من ملفّ أ-٤ الجديد. **والأصلُ لا يحمل الاستيرادَ بعد**
# ⇒ فالرقمُ أُعيد إنتاجُه **بمحاكاة رأسٍ صارم** في نسخةٍ منفصلة (1007 ⇒ 1028)، لا من التاريخ.
# والآن تُستورَد الوحدةُ دائمًا، وتعمل النوعيّةُ حيث يوجد pydantic، **وتُتخطّى ضوابطُ النوع
# صراحةً** حيث لا يوجد (`pytestmark` في `tests/test_answer_type.py`) — حارسٌ يُطلَق فعلًا.
try:                                    # pragma: no cover - depends on installed stack
    from pydantic import BaseModel, Field
    _PYDANTIC = True
except ImportError:                     # pragma: no cover
    _PYDANTIC = False

    class BaseModel:                    # بديلٌ صامتٌ لا يُتحقَّق منه شيء: يكفي ليُستورَد الملفّ
        def __init__(self, **kw):
            self.__dict__.update(kw)

    def Field(default=None, **_kw):     # noqa: N802 — اسمٌ من pydantic يُحاكى عند غيابه
        return default
from decimal import Decimal

from statement_qa.retriever import retrieve

# «آخر رصيد»-style questions: the closing row can legitimately rank below
# top-k on a long statement (workshop top-12 #7: «آخر رصيد» لا يجيب). For
# these the LAST page's chunks are appended deterministically — the honest
# retrieval bridge, no scoring tricks.
def _normalize_ar(text: str) -> str:
    """Drop hamza/diacritic variants before matching (audit P2-9).

    «اخر رصيد» — the way this is normally typed, without a hamza — did not
    match a pattern written «آخر رصيد», so the deterministic bridge to the last
    page silently did not fire for 9 of the 15 phrasings tested, including the
    commonest one. Normalising the question is cheaper and more honest than an
    ever-longer alternation.
    """
    out = str(text or "")
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه")):
        out = out.replace(a, b)
    return re.sub(r"[\u064b-\u0652\u0640]", "", out)   # diacritics + tatweel


_CLOSING_RE = re.compile(
    r"اخر\s*رصيد|الرصيد\s*(?:الاخير|الختامي|النهائي|الحالي|المتبقي)"
    r"|رصيد\s*(?:ختامي|نهائي|متبقي)|الختامي|نهايه\s*الكشف|اقفل\s*الحساب"
    r"|بكم\s*اقفل|كم\s*(?:تبقي|باقي)|closing\s*balance|balance\s*at\s*end",
    re.IGNORECASE)


def boost_last_page(hits: list[dict], chunks, question: str) -> list[dict]:
    """Append the final page's chunks for closing-balance questions.

    Pure and deterministic: nothing is re-scored; missing last-page chunks
    are appended at the end so the tools/answer/sources can see them."""
    if not chunks or not _CLOSING_RE.search(_normalize_ar(question or "")):
        return hits
    last_page = max(c.page for c in chunks)
    have = {(h.get("page"), h.get("row_start"), h.get("row_end"))
            for h in hits}
    extra = [c for c in chunks
             if c.page == last_page
             and (c.page, c.start_row, c.end_row) not in have]
    if not extra:
        return hits
    return hits + [{
        "chunk_id": c.chunk_id, "page": c.page, "row_start": c.start_row,
        "row_end": c.end_row, "text": c.text, "score": 0.0,
    } for c in extra]

SYSTEM_PROMPT = """أنت محاسب مدقق تعمل على كشف حساب بنكي (الراجحي) حُوّل لنص.
أجب عن السؤال اعتماداً حصرياً على "القطع المرفقة" أدناه.
قواعد صارمة:
1. كل رقم تذكره يجب أن يكون مكتوباً حرفياً في القطع — لا تحسب ولا تجمع بنفسك.
2. إن لم تكفِ القطع للجواب قل حرفياً: "غير موجود في الكشف" — لا تخمّن.
3. ألزم كل رقم بمصدره: (صفحة N، صفوف X–Y).
4. أجب بالعربية بإيجاز مع ذكر أرقام الصفحات والصفوف."""

AGENT_SYSTEM_PROMPT = """أنت محاسب مدقق تعمل على كشف حساب بنكي (الراجحي).
لديك أدوات حتمية (tools) تجري الحسابات على الجدول المُستخرج المُتحقق منه.
قواعد صارمة:
1. أي سؤال عن مجموع/إجمالي/عدد/أعلى/أدنى/آخر رصيد/ملخص صفحة ⇒ استدعِ الأداة المناسبة أولاً.
   **وأيُّ سؤالٍ عن رقمٍ مطبوعٍ في صفحةٍ بعينها** («إجمالي الصفحة ٥» · «المدين في الصفحة ١٢»)
   ⇒ `page_footer(page=N)` تقرأ **تذييلَ الورقة المطبوع** وحكمَه — **ولا تجمع صفوفَ الصفحة لتجيب عنه**:
   التذييلُ **تراكميّ من أوّل الكشف**، فمجموعُ صفوفِ صفحةٍ واحدةٍ لا يساويه إلا في الأولى. وإن جاء الحكمُ
   **غير مطابق** فاذكره، وإن كان **بلا تذييل** فقل ذلك ولا تخمّن.
   و**أيُّ سؤالٍ عن صفٍّ بعينه داخل صفحة** («أكبر حركةٍ في الصفحة N» · «صفوفُ الصفحة N» · «آخرُ حركةٍ فيها»)
   ⇒ `page_rows(page=N)` تُسرَد الصفوفَ بأرقامها (على مستوى الكشف لا من ١ داخل الصفحة) ومنها يُقرأ الأكبرُ/الأخير.
2. انقل الأرقام من مخرجات الأدوات حرفياً — لا تُجرِ أي جمع أو طرح بنفسك أبداً.
3. للأسئلة الوصفية استعن بالقطع المرفقة في رسالة المستخدم.
4. إن لم تكفِ الأدوات والقطع قل حرفياً: "غير موجود في الكشف" — لا تخمّن.
5. ألزم كل رقم بمصدره (صفحة/صف). أجب بالعربية بإيجاز.
6. الاتجاه (مدين/دائن) يصف اتجاه الحركة فقط وليس نوعها: «مدين» ≠ «سحب صراف آلي».
   لأسئلة النوع (سحوبات صراف آلي، تحويلات، إيداعات، نقاط بيع، سداد) استخدم tx_type،
   وللمبلغ المحدد استخدم amount معه (مثال «سحب بـ1000» ⇒ tx_type="سحب صراف آلي", amount=1000)،
   وإن ظهر المبلغ نفسه بأنواع أخرى فاذكر ذلك صراحةً في الجواب."""


def build_llm(model_name: str | None = None):
    """ChatOpenAI pointed at OpenRouter (key from env / ~/.hermes/.env)."""
    from langchain_openai import ChatOpenAI

    from statement_qa.api_key import get_api_key

    key = get_api_key()
    model = model_name or os.environ.get("OPENROUTER_MODEL", "z-ai/glm-5.3-flash")
    return ChatOpenAI(
        model=model,
        base_url="https://openrouter.ai/api/v1",
        api_key=key,
        temperature=0,
    )


def format_hits(hits: list[dict]) -> str:
    blocks = []
    for h in hits:
        blocks.append(f"--- القطعة {h['chunk_id']} (صفحة {h['page']}، "
                      f"صفوف {h['row_start']}–{h['row_end']}) ---\n{h['text']}")
    return "\n\n".join(blocks)


def _text(content) -> str:
    """LangChain message content -> plain string (handles block lists)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            (p.get("text", "") if isinstance(p, dict) else str(p))
            for p in content)
    return str(content)


class Answer(BaseModel):
    """**جوابٌ مُقيَّدٌ نوعًا (بوّابةُ أ-٤):** الاستشهادُ يُسلَّم هنا — لا يُقصّ من النثر.

    **والعِلّة:** كان الجوابُ نصًّا ثمّ تُستخرَج أرقامُ الصفوف منه بتعبيرٍ نمطيّ ⇒ فالاستشهادُ
    **مُستنتَجٌ** من نصٍّ حرّ، ولا شيءَ يمنع نموذجًا من كتابة رقمٍ بلا شاهد. والنوعُ يقلب الاتّجاه:
    `cited_row_ids` يُطلب صراحةً، **ويُقابَل بالأثر** (`citation_truth`) ⇒ فما لا شاهدَ له يُسمّى.
    """
    answer: str = Field(description="الجوابُ بالعربية، بأرقامٍ حقيقيةٍ من الكشف")
    cited_row_ids: list[int] = Field(
        default_factory=list, description="أرقامُ الصفوف العامة التي استُشهد بها (وما لا شاهدَ له يُعلَن)")
    refused: bool = Field(default=False, description="True إن امتنع: لا شاهدَ يحمل الجواب")


# ── قوالبُ التلقين وذاكرةُ الحوار (R92 · البند ١) ────────────────────────────────
# **العطبُ الذي يمنعه:** كان تلقينُ الوكيل **نصًّا مجمَّدًا** لا يعرف نطاقَ الكشف ولا سؤالَه السابق ⇒
# فسؤالٌ تابعٌ يُجاب كأنّه مبتدأ، أو يُنقل فيه رقمٌ من جوابٍ سابق بلا أداة. فصار التلقينُ **قالبًا
# بمتغيّرين** عبر `ChatPromptTemplate` من LangChain — **وبتراجعٍ مُعلَن** إلى القالب نفسه يدويًّا.
_TEMPLATE_HEAD = (
    "{system}\n\n"
    "**نطاقُ الكشف الذي تعمل عليه:** {scope}\n"
    "**وسجلُّ الحوار السابق (يُستأنس به لفهم السؤال، ولا يُنقل عنه رقمٌ بلا أداة):**\n{history}"
)
MEMORY_TURNS = 3          # **حدٌّ مُعلَن:** آخرُ ثلاث دورات — لا ذاكرةٌ تنمو بلا سقف


def _render_template(system: str, scope: str, history: str) -> str:
    """قالبُ التلقين: `ChatPromptTemplate` إن أمكن، **وإلّا القالبُ نفسه يدويًّا**.

    **والحارسُ واسعٌ قصْدًا:** ضيقُه (`ImportError` وحدَه) أسقط مسارَ الوكيل إلى البديل النصّيّ في
    بيئةٍ لم تُهيّأ فيها المكتبة (قِيس: ضابطان سقطا بـ`AttributeError`). فأيُّ تعذُّرٍ ⇒ النصُّ نفسه
    — **لا سلوكَ آخر**.
    """
    try:
        from langchain_core.prompts import ChatPromptTemplate          # noqa: PLC0415
        tpl = ChatPromptTemplate.from_messages([("system", _TEMPLATE_HEAD)])
        return tpl.format_messages(system=system, scope=scope, history=history)[0].content
    except Exception:                            # noqa: BLE001
        return _TEMPLATE_HEAD.format(system=system, scope=scope, history=history)


def format_history(history) -> str:
    """آخرُ `MEMORY_TURNS` دورةً — **ويُعلن ما أُسقط** بدل أن يُخفى."""
    if not history:
        return "لا سجلَّ سابق (هذا أوّلُ سؤال في الجلسة)."
    items = list(history)
    kept = items[-MEMORY_TURNS:]
    parts = [f"- سؤالٌ سابق: {q}\n  جوابُه: {a}" for q, a in kept]
    if len(items) > len(kept):
        parts.append(f"(و{len(items) - len(kept)} دورةً أقدم أُسقطت من النافذة — والحدُّ {MEMORY_TURNS})")
    return "\n".join(parts)


def history_pairs(messages) -> list[tuple[str, str]]:
    """سجلُّ الواجهة (`role`/`content`) ⇒ أزواجُ (سؤال، جواب) — **بلا اختراع قواعد**.

    دورُ المستخدم يفتح الزوج، ودورُ المساعد يُغلقه؛ ودورٌ مكرَّرٌ أو ناقصٌ **يُهمَل** بدل أن يُخمَّن
    (سجلٌّ بجوابٍ بلا سؤالٍ أو سؤالٍ بلا جواب لا يُنسب إلى أحدهما).
    """
    pairs: list[tuple[str, str]] = []
    pending = None
    for m in messages or []:
        if isinstance(m, dict):
            role, content = m.get("role", ""), m.get("content", "")
        else:
            role, content = getattr(m, "role", ""), getattr(m, "content", "")
        if role == "user":
            pending = str(content or "")
        elif role == "assistant" and pending is not None:
            pairs.append((pending, str(content or "")))
            pending = None
    return pairs


def build_system_prompt(scope: str = "", history=None) -> str:
    """تلقينُ الوكيل من القالب — بمتغيّرَي النطاق والسجلّ (وكلاهما مُعلَن في الجواب)."""
    return _render_template(AGENT_SYSTEM_PROMPT, scope or "غيرُ مُعلَن", format_history(history))


def _run_agent(llm, tools, system_prompt: str, user_content: str,
               response_format=None) -> tuple[str, object | None, str]:
    """create_agent (langchain 1.x) مع نوعٍ مُقيَّد، و**وضعٌ يُعلَن**: `typed` أو `prose`.

    **ولا انحدارَ صامت:** نسخةٌ لا تعرف الوسيط ترفع `TypeError` ⇒ يُبنى بلا نوعٍ **ويُعلَن**
    أنّ الجواب نصّيّ (`prose`)، فلا يُقرأ لاحقًا كأنّ استشهادَه مُصرَّحٌ به. وكذلك مسارُ
    `create_react_agent` الاحتياطيّ ⇒ `prose`. **ولا نداءَ نموذجٍ هنا في الاختبار** (يُقاس ببديل).
    """
    typed = response_format is not None
    try:
        from langchain.agents import create_agent
    except ImportError:  # pragma: no cover - depends on installed stack
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, tools, prompt=system_prompt)
        typed = False
    else:
        kw = {"model": llm, "tools": tools, "system_prompt": system_prompt}
        if typed:
            kw["response_format"] = response_format
        try:
            agent = create_agent(**kw)
        except TypeError:      # نسخةٌ لا تعرف `response_format` ⇒ بلا نوع، ويُعلَن ذلك
            agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt)
            typed = False
    res = agent.invoke({"messages": [{"role": "user", "content": user_content}]})
    parsed = res.get("structured_response") if isinstance(res, dict) else None
    if typed and parsed is not None and getattr(parsed, "answer", None):
        return str(parsed.answer).strip(), parsed, "typed"
    msgs = res.get("messages", []) if isinstance(res, dict) else []
    if not msgs:
        return "", None, "prose"
    # **والوضعُ يوصف ما سُلِّم لا ما طُلب** (أمسكه ضابطُ النوع): إن مرّرنا الوسيطَ ولم يعد كائنٌ
    # مُقيَّد، فالجوابُ **نثرٌ** ⇒ يُعلَن كذلك، وإلّا قُرئ استشهادُه لاحقًا كأنّه مُصرَّحٌ به وهو مُقتطع.
    return _text(msgs[-1].content).strip(), None, "prose"


def _answer_with_tools(llm, rows, context: str, question: str,
                       footers=None, history=None,
                       scope: str = "") -> tuple[str, list[dict], object | None, str]:
    from statement_qa.qa_tools import make_qa_tools

    trace: list[dict] = []
    tools = make_qa_tools(rows, trace=trace, footers=footers)
    user = (f"القطع المرفقة:\n{context}\n\n"
            f"إن احتجت حساب أي رقم فاستخدم الأدوات.\n\nالسؤال: {question}")
    # **توافقٌ خلفيّ تامّ:** بلا ذاكرةٍ ولا نطاقٍ يبقى التلقينُ نصَّه القديم بحرفه.
    system_prompt = (build_system_prompt(scope=scope, history=history)
                     if (history or scope) else AGENT_SYSTEM_PROMPT)
    text, parsed, mode = _run_agent(llm, tools, system_prompt, user,
                                    response_format=Answer)
    return text, trace, parsed, mode


def _tool_was_used(trace: list[dict]) -> bool:
    """هل استُدعيت أداةٌ فعلًا (ولو بلا صفوف)؟ — شاهدُ الفوتر المطبوع ليس صفًّا (R77)."""
    return any(c.get("tool") for c in (trace or []))


def _answer_plain(llm, context: str, question: str) -> str:
    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", f"القطع المرفقة:\n{context}\n\nالسؤال: {question}"),
    ]
    return _text(llm.invoke(messages).content).strip()


@dataclass
class QAResult:
    answer: str
    sources: list[dict]
    # Global statement row numbers the TOOLS actually selected (evidence
    # backbone). None/[] when the answer came from prose (no tools ran).
    used_row_nos: list[int] | None = None
    tools_failed: bool = False
    refused: bool = False
    scope: str = "in_scope"
    # A NUMERIC question answered without a single tool call. Not a failure —
    # a recollection, and it must be labelled as one (Gate 4, case F).
    ungrounded: bool = False
    # **الاستشهادُ المُصرَّح به (أ-٤):** من النوعِ لا من النثر — ومقابَلٌ بالأثر.
    cited_row_ids: list[int] = field(default_factory=list)
    citation_mode: str = "prose"          # typed | prose — يُعلَن ولا يُخمَّن
    unsupported_citations: list[int] = field(default_factory=list)

    def __str__(self) -> str:
        src = "; ".join(f"صفحة {s['page']} ص{s['row_start']}–{s['row_end']}"
                        for s in self.sources)
        return f"{self.answer}\n[المصادر: {src}]"


_INTERROGATIVE = ("كم", "هل", "ما ", "ماذا", "أي ", "ما هي", "ما هو")
_NUMERIC_HINT = ("كم", "مجموع", "إجمالي", "اجمالي", "عدد", "نسبة", "متوسط")


def split_compound(question: str) -> list[str]:
    """Split a two-part question — but only where splitting is safe.

    Splitting on every «و» would cut «المدين والدائن» in half; requiring an
    interrogative word on BOTH sides of a separator keeps the split honest.
    Measured case F: one half existed in the statement and one did not, and the
    compound question was answered from prose without a single tool call.
    """
    q = (question or "").strip()
    if not q:
        return []
    def _clean(part: str) -> str:
        p = part.strip(" ؟?.")
        for pref in ("وكم", "وهل", "وما", "وماذا"):   # the conjunction, not a word
            if p.startswith(pref):
                return p[1:]
        return p

    for sep in ("،", " و", "؟"):
        parts = [_clean(p) for p in q.split(sep)]
        parts = [p for p in parts if p]
        if len(parts) < 2:
            continue
        if all(any(m in p for m in _INTERROGATIVE) for p in parts):
            return parts
    return [q]


def needs_tools(question: str) -> bool:
    """Does the question ask for a NUMBER? Then prose is not an answer."""
    return any(m in (question or "") for m in _NUMERIC_HINT)


def _data_facts(rows) -> tuple[set, int | None, frozenset]:
    """What the statement itself proves: its years, its last page, its amounts.

    Computed once per question from the rows the caller passes. Empty input
    returns empties, and the gate then stays open — it may only refuse what it
    can prove.
    """
    years: set[int] = set()
    max_page: int | None = None
    amounts: set[Decimal] = set()
    from statement_qa.ordering import parse_gregorian

    for r in rows or ():
        g = parse_gregorian(r.get("date"))
        if g:
            years.add(int(g[:4]))
        page = r.get("page")
        if isinstance(page, int):
            max_page = page if max_page is None else max(max_page, page)
        for value in (r.get("movement"), r.get("balance")):
            if value is None:
                continue
            try:
                amounts.add(Decimal(str(value)).quantize(Decimal("0.01")))
            except Exception:  # noqa: BLE001
                continue
    return years, max_page, frozenset(amounts)


def answer_question(store, question: str, rows=None, chunks=None,
                    llm=None, k: int = 4, footers=None, history=None,
                    scope: str = "") -> QAResult:
    """Agent-with-tools answer when rows exist; strict RAG fallback otherwise.

    `chunks` (optional): the run's chunks — used ONLY to boost the last page
    for closing-balance questions (see boost_last_page).
    `footers` (optional): the page's **printed** footer totals + verdict — the
    external referee, made answerable (R77). Absent ⇒ the tool says so."""
    # THE GATE RUNS BEFORE THE MODEL. Three measured defects (Gate 4) came from
    # handing a model with tools a question whose premise sits outside the
    # document: it refused once and answered the same question the next time.
    # Determinism here is not a stronger prompt, it is not asking at all.
    from statement_qa.scope import classify

    if rows:
        _years, _max_page, _amounts = _data_facts(rows)
        gate = classify(question, _years, _max_page, _amounts)
        if gate.kind != "in_scope":
            return QAResult(answer=gate.answer, sources=[], used_row_nos=[],
                            refused=gate.kind == "out_of_scope",
                            scope=gate.kind)

    llm = llm or build_llm()

    # A compound question is TWO questions, and the second half is where the
    # routing went wrong: measured case F asked for a sum that exists and a
    # count that does not, and got prose for both. Each half is answered — and
    # grounded — on its own.
    parts = split_compound(question)
    if len(parts) > 1:
        results = [_answer_one(store, part, rows, chunks, llm, k, footers, history=history, scope=scope)
                   for part in parts]
        merged_used = [n for r in results for n in (r.used_row_nos or [])]
        hits = boost_last_page(retrieve(store, question, k=k), chunks, question)
        body = "\n\n".join(f"• {r.answer}" for r in results)
        # **والنوعُ يُدمَج مع الأجزاء (مقعدُ أ-٤ P2 · مُثبت):** كان ينبني بلا `cited_row_ids`
        # ولا `citation_mode` ⇒ فسؤالٌ مركّبٌ جزءُه مُقيَّدٌ يعود `prose` باستشهادٍ فارغ،
        # **فلا تُطبَّق البوّابةُ على المركّب** — وهو نصفُ الأسئلة الحقيقيّة.
        merged_cited = sorted({n for r in results for n in (r.cited_row_ids or [])})
        merged_unsup = sorted({n for r in results for n in (r.unsupported_citations or [])})
        merged_mode = ("typed" if any(r.citation_mode == "typed" for r in results)
                       else "prose")
        return QAResult(
            answer=body,
            sources=[{k2: h[k2] for k2 in
                      ("chunk_id", "page", "row_start", "row_end")} for h in hits],
            used_row_nos=merged_used or None,
            tools_failed=all(r.tools_failed for r in results),
            ungrounded=any(r.ungrounded for r in results),
            cited_row_ids=merged_cited,
            citation_mode=merged_mode,
            unsupported_citations=merged_unsup)

    return _answer_one(store, question, rows, chunks, llm, k, footers, history=history, scope=scope)


def _answer_one(store, question: str, rows, chunks, llm, k: int,
                footers=None, history=None, scope: str = "") -> QAResult:
    """One question, one answer, with its own tool trace and its own honesty.

    `footers` (R77): التذييلاتُ المطبوعةُ لكلّ صفحة — تُمرَّر إلى الأدوات فيُجيب `page_footer` عنها."""
    hits = boost_last_page(retrieve(store, question, k=k), chunks, question)
    context = format_hits(hits)
    answer = ""
    used: list[int] = []
    tools_failed = False
    ungrounded = False
    parsed = None
    mode = "prose"
    refused = False
    if rows:
        try:
            answer, trace, parsed, mode = _answer_with_tools(llm, rows, context, question,
                                                             footers=footers, history=history, scope=scope)
            from statement_qa.qa_tools import used_rows_from_trace

            used = used_rows_from_trace(trace)
            if (not used and not _tool_was_used(trace)
                    and needs_tools(question)):
                # One nudge, aimed: «use a tool» is a directive the agent
                # follows far more often than the softer wording above — and if
                # it still does not, the answer is labelled rather than trusted.
                answer2, trace2, parsed2, mode2 = _answer_with_tools(
                    llm, rows, context,
                    question + "\n\n(استخدم أداة حسابية واحدة على الأقل قبل "
                               "الجواب، ولا تحسب بنفسك.)",
                    footers=footers, history=history, scope=scope)
                used2 = used_rows_from_trace(trace2)
                if used2 or _tool_was_used(trace2):
                    answer, used = answer2, used2
                    trace, parsed, mode = trace2, parsed2, mode2   # الوضعُ يتبع الجوابَ المُعتمَد
                else:
                    # «رفض لا وسم» (المدقّق، جوابه ١): رقم لم يُحسَب لا يُعرض
                    # كجواب أصلاً — الوسم يضيع في ملف يُمرَّر كـPDF.
                    ungrounded = True
                    # **ولا استشهادَ مع امتناع (مقعدُ أ-٤ P3 · مُثبت):** كان الكائنُ يحمل
                    # `citation_mode="typed"` واستشهاداتٍ وهو يقول «لم أستطع» ⇒ تناقضٌ داخليّ
                    # (والواجهةُ آمنةٌ لأنّ `none` تسبق — لكنّ الكائنَ يُقرأ في غير الواجهة أيضًا).
                    parsed, mode = None, "prose"
                    answer = ("لم أستطع حساب هذا الرقم من الكشف: لا استدعاء "
                              "لأي أداة حسابية. ولن أعرض رقماً لم يُحسَب — "
                              "أعد صياغة السؤال بصيغةٍ تُسمّي ما تريده.")
        except Exception:
            # The SILENT part was the problem, not the fallback itself: a
            # provider timeout used to hand back a prose answer with an empty
            # trace and no hint that nothing had been computed, while the
            # evidence panel then filled itself from the model's own citations
            # (audit P2-10).
            answer = ""
            tools_failed = True
            # **والصنفُ لا الموضع (قاسه السؤالُ المدفوع · مُثبت):** أصلحتُ الامتناعَ وتركتُ تعذُّرَ الأدوات
            # ⇒ فجوابٌ **بلا أثرِ أداةٍ** حمل `typed` واستشهادات (قِيس: `tools_failed=True` و`cited=[…6]`
            # في نداءٍ حقيقيّ). والقاعدة: **من لا أثرَ له لا نوعَ له** — فيُصفَّران هنا أيضًا، ويقيسه ضابطٌ.
            parsed, mode = None, "prose"
    if not answer:
        answer = _answer_plain(llm, context, question)
        used = []
    # **والاستشهادُ من النوع يُقابَل بالأثر** (بوّابةُ أ-٤): كلُّ استشهادٍ بلا شاهدٍ يُسمّى باسمه
    from statement_qa.qa_tools import citation_truth

    cited = list(getattr(parsed, "cited_row_ids", []) or []) if parsed is not None else []
    truth = citation_truth(cited, trace if rows and not tools_failed else [])
    if parsed is not None and getattr(parsed, "refused", False):
        refused = True
    return QAResult(answer=answer,
                    cited_row_ids=truth["cited"],
                    citation_mode=mode,
                    unsupported_citations=truth["unsupported"],
                    refused=refused,
                    sources=[{k2: h[k2] for k2 in
                              ("chunk_id", "page", "row_start", "row_end")}
                             for h in hits],
                    used_row_nos=used,
                    tools_failed=tools_failed,
                    ungrounded=ungrounded)