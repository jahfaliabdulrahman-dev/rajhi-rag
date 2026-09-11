"""Text extraction from statement PDFs — dual path with geographic rows.

Each page is classified: text-layer (digital export) or scanned (image).
Scanned pages are OCR'd at 300dpi and ALSO saved as TSV word-boxes so the
parser can rebuild movement rows by y-clustering + x-column classification
(instead of fragile per-line regex on mixed bidi text).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from pypdf import PdfReader

OCR_DPI = 300
TEXT_CHAR_THRESHOLD = 100


@dataclass
class PageText:
    page_no: int          # 1-based
    kind: str             # "text" | "scanned"
    text: str
    tsv: str | None = None   # raw tesseract TSV (word boxes) when OCR'd


def _ocr_page(pdf_path: str, page_no: int, dpi: int = OCR_DPI) -> tuple[str, str]:
    """Render one page to image; return (plain text, tesseract TSV)."""
    images = convert_from_path(
        pdf_path, dpi=dpi, first_page=page_no, last_page=page_no)
    if not images:
        return "", ""
    img = images[0]
    txt = pytesseract.image_to_string(img, lang="ara+eng", config="--psm 6")
    tsv = pytesseract.image_to_data(
        img, lang="ara+eng", config="--psm 6", output_type=pytesseract.Output.STRING)
    cleaned = (txt.replace("\u200e", "").replace("\u200f", "")
                  .replace("\u202a", "").replace("\u202b", "").replace("\u202c", ""))
    return cleaned, tsv


def extract_pages(pdf_path: str, with_tsv: bool = False) -> list[PageText]:
    """Classify each page (text vs scanned) and extract accordingly."""
    reader = PdfReader(pdf_path)
    kinds: list[str] = []
    for page in reader.pages:
        try:
            n = len((page.extract_text() or "").strip())
        except Exception:
            n = 0
        kinds.append("text" if n >= TEXT_CHAR_THRESHOLD else "scanned")

    pages: list[PageText] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, kind in enumerate(kinds, start=1):
            if kind == "text":
                txt = (pdf.pages[i - 1].extract_text() or "").strip()
                tsv = ""
            else:
                txt, tsv = _ocr_page(pdf_path, i)
            pages.append(PageText(page_no=i, kind=kind, text=txt, tsv=tsv))
    return pages


def read_statement(pdf_path: str) -> str:
    """Full statement text with [PAGE n] markers (for RAG chunking)."""
    return "\n\n".join(
        f"[PAGE {p.page_no}]\n{p.text}" for p in extract_pages(pdf_path) if p.text
    )


if __name__ == "__main__":
    import sys

    for line in read_statement(sys.argv[1]).splitlines():
        print(line)
