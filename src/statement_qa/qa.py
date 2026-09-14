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

from statement_qa.retriever import retrieve

# «آخر رصيد»-style questions: the closing row can legitimately rank below
# top-k on a long statement (workshop top-12 #7: «آخر رصيد» لا يجيب). For
# these the LAST page's chunks are appended deterministically — the honest
# retrieval bridge, no scoring tricks.
_CLOSING_RE = re.compile(
    r"آخر\s*رصيد|الرصيد\s*(?:الأخير|الختامي|النهائي|الحالي)"
    r"|رصيد\s*(?:ختامي|نهائي)|الختامي")


def boost_last_page(hits: list[dict], chunks, question: str) -> list[dict]:
    """Append the final page's chunks for closing-balance questions.

    Pure and deterministic: nothing is re-scored; missing last-page chunks
    are appended at the end so the tools/answer/sources can see them."""
    if not chunks or not _CLOSING_RE.search(question or ""):
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

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        from pathlib import Path

        for line in open(Path.home() / ".hermes" / ".env"):
            if line.strip().startswith("OPENROUTER_API_KEY="):
                key = line.strip().split("=", 1)[1].strip("\"'")
                break
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

    def __str__(self) -> str:
        src = "; ".join(f"صفحة {s['page']} ص{s['row_start']}–{s['row_end']}"
                        for s in self.sources)
        return f"{self.answer}\n[المصادر: {src}]"


def answer_question(store, question: str, rows=None, chunks=None,
                    llm=None, k: int = 4) -> QAResult:
    """Agent-with-tools answer when rows exist; strict RAG fallback otherwise.

    `chunks` (optional): the run's chunks — used ONLY to boost the last page
    for closing-balance questions (see boost_last_page)."""
    hits = boost_last_page(retrieve(store, question, k=k), chunks, question)
    context = format_hits(hits)
    llm = llm or build_llm()
    answer = ""
    used: list[int] = []
    if rows:
        try:
            answer, trace = _answer_with_tools(llm, rows, context, question)
            from statement_qa.qa_tools import used_rows_from_trace

            used = used_rows_from_trace(trace)
        except Exception:
            answer = ""
    if not answer:
        answer = _answer_plain(llm, context, question)
        used = []
    return QAResult(answer=answer,
                    sources=[{k2: h[k2] for k2 in
                              ("chunk_id", "page", "row_start", "row_end")}
                             for h in hits],
                    used_row_nos=used)