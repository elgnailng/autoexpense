"""
pdf_reader.py - Simple pdfplumber wrapper.

Returns pages as list of (page_number, text) tuples (1-indexed page numbers).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import pdfplumber


def read_pdf(pdf_path: str | Path) -> List[Tuple[int, str]]:
    """
    Open a PDF and return a list of (page_number, text) tuples.

    Page numbers are 1-indexed.
    Text is extracted using pdfplumber's default layout analysis.
    Returns an empty list if the file cannot be opened.
    """
    pdf_path = Path(pdf_path)
    pages: List[Tuple[int, str]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append((i, text))

    return pages
