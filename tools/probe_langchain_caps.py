#!/usr/bin/env python3
"""مسبار قدرات LangChain على مكدّسنا — يُقاس ولا يُنقل عن الوثائق.

سؤالان يُقاسان هنا، وقد قيلا لنا من الوثائق فحسب:

  (١) **مخرَجٌ مقيَّد بنوع بلا وكيل:** هل يُنال بـ`with_structured_output` على
      نداءٍ واحد؟ فإن نُيل، فـ«رفع طبقة السؤال إلى LangChain» ليس ٢–٣ أيام.
  (٢) **سقف الإعادات:** مقدار `recursion_limit` الافتراضي **في نسختنا المثبّتة**،
      وماذا يحدث عملياً حين يُخفق تحقّق المخرج دائماً: أيقف بعد عدٍّ معروف
      (سقفٌ = كلفةٌ معلومة) أم يمضي (كلفةٌ بلا سقف في مشروعٍ كل رقمٍ فيه بدليله)؟

**ولا بيانات حقيقية هنا:** السؤال حسابيّ محايد، والنتيجة تُكتب في `docs/evidence/`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pydantic import BaseModel, Field, model_validator  # noqa: E402

NEUTRAL_QUESTION = "ما ناتج ٢ + ٢؟ أجب بالرقم وحده."


class Answer(BaseModel):
    """شكلٌ شبيه بمخرج تبويب السؤال عندنا — بلا بيانات حقيقية."""
    answer: str = Field(description="الجواب النصّي")
    cited_row_ids: list[int] = Field(default_factory=list,
                                     description="معرّفات الصفوف التي بنت الرقم")


class AlwaysInvalid(BaseModel):
    """مخطَّطٌ يفشل تحقّقه دائماً — لقياس سقف الإعادات لا للاستعمال."""
    value: str = Field(description="أي نصّ")

    @model_validator(mode="after")
    def _never(self):
        raise ValueError("قيمة مرفوضة دائماً — سقف الإعادات يُقاس هنا")


def _installed_recursion_default() -> object:
    """الرقم من الشيفرة المثبّتة — لا من وثيقةٍ قد تكون لنسخةٍ أخرى."""
    try:
        from langgraph._internal._config import DEFAULT_RECURSION_LIMIT
        return DEFAULT_RECURSION_LIMIT
    except Exception as exc:  # pragma: no cover - يعتمد على الإصدار
        return f"غير قابل للقراءة ({type(exc).__name__})"


def probe_structured_output(llm, model: str) -> dict:
    """(١) مخرَجٌ مقيَّد بنوع على نداءٍ واحد — بلا وكيل ولا وسيط."""
    out: dict = {"model": model}
    t0 = time.time()
    try:
        structured = llm.with_structured_output(Answer)
        res = structured.invoke(NEUTRAL_QUESTION)
        out |= {"ok": True, "type": type(res).__name__,
                "fields": sorted(getattr(res, "model_dump", lambda: res)()),
                "answers_the_question": "4" in str(getattr(res, "answer", res))
                                        or "٤" in str(getattr(res, "answer", res))}
    except Exception as exc:
        out |= {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
    out["seconds"] = round(time.time() - t0, 2)
    return out


def probe_retry_ceiling(llm, model: str, limit: int) -> dict:
    """(٢) الإعادات: بمَ تُقفل، وكم محاولة قبض الثمن قبلها."""
    out: dict = {"model": model, "recursion_limit_passed": limit,
                 "installed_default": _installed_recursion_default()}
    t0 = time.time()
    calls = {"n": 0}
    try:
        from langchain.agents import create_agent
        from langchain.agents.structured_output import ToolStrategy

        def counting_llm(messages, **kw):
            calls["n"] += 1
            return llm.invoke(messages, **kw)

        agent = create_agent(model=llm, tools=[],
                             response_format=ToolStrategy(schema=AlwaysInvalid,
                                                          handle_errors=True))
        try:
            agent.invoke({"messages": [{"role": "user", "content": NEUTRAL_QUESTION}]},
                         config={"recursion_limit": limit})
            out["stopped_by"] = "عاد بلا استثناء"
        except Exception as exc:
            msg = str(exc)
            out["stopped_by"] = type(exc).__name__
            m = re.search(r"Recursion limit of (\d+)", msg)
            if m:
                out["limit_seen_in_message"] = int(m.group(1))
            out["message"] = msg[:220]
    except Exception as exc:
        out["stopped_by"] = "بناءُ الوكيل فشل"
        out["message"] = f"{type(exc).__name__}: {exc}"[:220]
    out["seconds"] = round(time.time() - t0, 2)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    ap.add_argument("--retry-limit", type=int, default=6,
                    help="سقفٌ يضعه المسبار على نفسه كي لا يصير القياس كلفةً")
    ap.add_argument("--out", type=Path, default=PROJ / "docs/evidence")
    args = ap.parse_args()

    from statement_qa.qa import build_llm
    llm = build_llm(args.model)
    model = args.model or "افتراضي التطبيق"

    report = {"measured_at": date.today().isoformat(),
              "stack": {"langchain": _ver("langchain"),
                        "langchain-core": _ver("langchain-core"),
                        "langgraph": _ver("langgraph"),
                        "langchain-openai": _ver("langchain-openai")},
              "question": "سؤالٌ حسابيّ محايد — لا بيانات كشف",
              "structured_output": probe_structured_output(llm, model),
              "retry_ceiling": probe_retry_ceiling(llm, model, args.retry_limit)}
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "20260920-langchain-capability-probe.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"\nالملف: {path.relative_to(PROJ)}")


def _ver(pkg: str) -> str:
    try:
        import importlib.metadata as md
        return md.version(pkg)
    except Exception:  # pragma: no cover
        return "غير مثبّت"


if __name__ == "__main__":
    main()
