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

from statement_qa.extract_text import read_statement
from statement_qa.parser import parse_text
from statement_qa.verifier import verify_statement

__all__ = ["read_statement", "parse_text", "verify_statement"]
__version__ = "0.3.0"
