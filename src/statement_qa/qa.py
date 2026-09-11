"""QA layer: LangChain LLM answers ONLY from retrieved chunks.

Contract (from the plan + owner rules):
- The model NEVER computes: balances/sums come from the deterministic table.
- Answers quote retrieved chunks; missing evidence → 'غير موجود في الكشف'.
- Every answer returns its sources (page + row range) verbatim.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from statement_qa.retriever import retrieve

SYSTEM_PROMPT = """أنت محاسب مدقق تعمل على كشف حساب بنكي (الراجحي) حُوّل لنص.
أجب عن السؤال اعتماداً حصرياً على "القطع المرفقة" أدناه.
قواعد صارمة:
1. كل رقم تذكره يجب أن يكون مكتوباً حرفياً في القطع — لا تحسب ولا تجمع بنفسك.
2. إن لم تكفِ القطع للجواب قل حرفياً: "غير موجود في الكشف" — لا تخمّن.
3. ألزم كل رقم بمصدره: (صفحة N، صفوف X–Y).
4. أجب بالعربية بإيجاز مع ذكر أرقام الصفحات والصفوف."""


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


@dataclass
class QAResult:
    answer: str
    sources: list[dict]

    def __str__(self) -> str:
        src = "; ".join(f"صفحة {s['page']} ص{s['row_start']}–{s['row_end']}"
                        for s in self.sources)
        return f"{self.answer}\n[المصادر: {src}]"


def answer_question(store, question: str, llm=None, k: int = 4) -> QAResult:
    """One-shot RAG: retrieve → strict-prompt answer → sources attached."""
    hits = retrieve(store, question, k=k)
    context = format_hits(hits)
    llm = llm or build_llm()
    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", f"القطع المرفقة:\n{context}\n\nالسؤال: {question}"),
    ]
    resp = llm.invoke(messages)
    return QAResult(answer=resp.content.strip(),
                    sources=[{k: h[k] for k in
                              ("chunk_id", "page", "row_start", "row_end")}
                             for h in hits])
