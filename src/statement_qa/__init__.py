"""statement_qa — Arabic bank statement Q&A (RAG + deterministic verification).

Architecture (3 layers):
  1. read:    PDF -> text (pdfplumber for text-layer, tesseract-OCR for scans)
              OCR uses TSV word-boxes; rows are rebuilt by geographic
              clustering (y-position), amounts classified by column
              position — robust against broken/alternating OCR lines.
  2. verify:  Polars table + balance-chain check (doubles as OCR-error
              detector and debit/credit side arbiter)
  3. understand: LangChain RAG answers ONLY from retrieved statement chunks
"""

from __future__ import annotations

import importlib
from typing import Any

# **الأسماء العامة تُستورد عند الطلب لا عند استيراد الحزمة.**
# كان الاستيراد المتلهّف يُلزم **كل** مستهلك للحزمة بـ`pdfplumber` (عبر
# `extract_text`) و`polars` — حتى من يريد `gap_ledger` وحده. والثمن ظهر عملياً:
# مجموعة CI الخفيفة سقطت عند جمع `tests/test_gate_bites.py` بـ
# `ModuleNotFoundError: pdfplumber`، وهو فحص لا يقرأ PDF ولا يستحقّ تبعيةً ثقيلة.
_LAZY: dict[str, str] = {
    "read_statement": "statement_qa.extract_text",
    "parse_text": "statement_qa.parser",
    "verify_statement": "statement_qa.verifier",
}

__all__ = list(_LAZY)
__version__ = "0.3.0"


def __getattr__(name: str) -> Any:
    """يستورد الاسم عند أول طلب (PEP 562) ثم يخزّنه في مساحة الحزمة."""
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(module), name)
    globals()[name] = value
    return value
