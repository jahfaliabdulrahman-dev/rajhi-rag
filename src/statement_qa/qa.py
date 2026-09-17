"""QA layer: LangChain agent with DETERMINISTIC tools over the verified table.

Contract (plan + owner rules):
- The model NEVER computes: every number comes from a tool call or a retrieved
  chunk. Answers quote evidence (page/row); missing evidence → refusal string.
- With `rows` supplied, a LangChain agent runs with tools from qa_tools
  (sum/count/extremes/page summary/search) — so "كم مجموع السحوبات؟" gets a
  real computed number, not a refusal.
- The tools record an execution TRACE (which rows each call selected); the
  evidence panel is built from that trace — what BUILT the numbers — not from
  the row refs the answer prose happens to repeat.
- Without rows (or if the agent path fails), falls back to strict one-shot RAG.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
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


def _run_agent(llm, tools, system_prompt: str, user_content: str) -> str:
    """create_agent (langchain 1.x) with a create_react_agent fallback."""
    try:
        from langchain.agents import create_agent

        agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt)
    except ImportError:  # pragma: no cover - depends on installed stack
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, tools, prompt=system_prompt)
    res = agent.invoke({"messages": [{"role": "user", "content": user_content}]})
    msgs = res.get("messages", []) if isinstance(res, dict) else []
    if not msgs:
        return ""
    return _text(msgs[-1].content).strip()


def _answer_with_tools(llm, rows, context: str,
                       question: str) -> tuple[str, list[dict]]:
    from statement_qa.qa_tools import make_qa_tools

    trace: list[dict] = []
    tools = make_qa_tools(rows, trace=trace)
    user = (f"القطع المرفقة:\n{context}\n\n"
            f"إن احتجت حساب أي رقم فاستخدم الأدوات.\n\nالسؤال: {question}")
    return _run_agent(llm, tools, AGENT_SYSTEM_PROMPT, user), trace


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
                    llm=None, k: int = 4) -> QAResult:
    """Agent-with-tools answer when rows exist; strict RAG fallback otherwise.

    `chunks` (optional): the run's chunks — used ONLY to boost the last page
    for closing-balance questions (see boost_last_page)."""
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
        results = [_answer_one(store, part, rows, chunks, llm, k)
                   for part in parts]
        merged_used = [n for r in results for n in (r.used_row_nos or [])]
        hits = boost_last_page(retrieve(store, question, k=k), chunks, question)
        body = "\n\n".join(f"• {r.answer}" for r in results)
        return QAResult(
            answer=body,
            sources=[{k2: h[k2] for k2 in
                      ("chunk_id", "page", "row_start", "row_end")} for h in hits],
            used_row_nos=merged_used or None,
            tools_failed=all(r.tools_failed for r in results),
            ungrounded=any(r.ungrounded for r in results))

    return _answer_one(store, question, rows, chunks, llm, k)


def _answer_one(store, question: str, rows, chunks, llm, k: int) -> QAResult:
    """One question, one answer, with its own tool trace and its own honesty."""
    hits = boost_last_page(retrieve(store, question, k=k), chunks, question)
    context = format_hits(hits)
    answer = ""
    used: list[int] = []
    tools_failed = False
    ungrounded = False
    if rows:
        try:
            answer, trace = _answer_with_tools(llm, rows, context, question)
            from statement_qa.qa_tools import used_rows_from_trace

            used = used_rows_from_trace(trace)
            if not used and needs_tools(question):
                # One nudge, aimed: «use a tool» is a directive the agent
                # follows far more often than the softer wording above — and if
                # it still does not, the answer is labelled rather than trusted.
                answer2, trace2 = _answer_with_tools(
                    llm, rows, context,
                    question + "\n\n(استخدم أداة حسابية واحدة على الأقل قبل "
                               "الجواب، ولا تحسب بنفسك.)")
                used2 = used_rows_from_trace(trace2)
                if used2:
                    answer, used = answer2, used2
                else:
                    ungrounded = True
        except Exception:
            # The SILENT part was the problem, not the fallback itself: a
            # provider timeout used to hand back a prose answer with an empty
            # trace and no hint that nothing had been computed, while the
            # evidence panel then filled itself from the model's own citations
            # (audit P2-10).
            answer = ""
            tools_failed = True
    if not answer:
        answer = _answer_plain(llm, context, question)
        used = []
    return QAResult(answer=answer,
                    sources=[{k2: h[k2] for k2 in
                              ("chunk_id", "page", "row_start", "row_end")}
                             for h in hits],
                    used_row_nos=used,
                    tools_failed=tools_failed,
                    ungrounded=ungrounded)