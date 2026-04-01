"""
rbc_parser.py - Parse RBC Visa PDF statements.

References:
  - https://github.com/benjamin-awd/monopoly  (patterns, header gating)
  - https://github.com/andrewscwei/rbc-statement-parser  (line merging)
  - https://github.com/Bizzaro/Teller  (text extraction approach)

Strategy:
  1. Extract physical-layout text per page with pdfplumber (layout=True)
  2. Merge continuation lines into transaction lines (andrewscwei technique)
  3. Find the TRANSACTION/POSTING header to gate where transactions begin
  4. Match each line with the unified TXN_RE (monopoly RBC Credit pattern)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber

# ---------------------------------------------------------------------------
# Month lookup
# ---------------------------------------------------------------------------

MONTH_TO_NUM: Dict[str, int] = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

_MONTH_ALT = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"

# Date separator: space, dash, or nothing (RBC PDFs sometimes render "JAN08" with no separator)
_DATE_SEP = r"[-\s]?"

# ---------------------------------------------------------------------------
# Regex patterns  (monopoly rbc.py RBC Credit, adapted)
# ---------------------------------------------------------------------------

# Transaction line: two dates + description + optional polarity + amount
# Handles "Jan 09" (space), "Jan-09" (dash), and "JAN08" (no separator)
# Amount: $? optional dollar sign (some PDFs omit it)
TXN_RE = re.compile(
    rf"(?P<transaction_date>\b{_MONTH_ALT}{_DATE_SEP}\d{{1,2}})\s+"
    rf"(?P<posting_date>\b{_MONTH_ALT}{_DATE_SEP}\d{{1,2}})\s+"
    r"(?P<description>.*?)\s+"
    r"(?P<polarity>-)?\s*"
    r"(?P<amount>\$?[\d,]+\.\d{2})",
    re.IGNORECASE,
)

# Statement period — handles both spaced and squashed formats:
#   "STATEMENT FROM JAN 10 TO FEB 10, 2025"
#   "STATEMENTFROMJAN10TOFEB10,2025"
PERIOD_RE = re.compile(
    rf"STATEMENT\s*FROM\s*(?P<sm>{_MONTH_ALT})\s*\d{{1,2}}"
    rf".*?TO\s*{_MONTH_ALT}\s*\d{{1,2}}\s*,?\s*(?P<ey>\d{{4}})",
    re.IGNORECASE | re.DOTALL,
)
# Fallback: any year after STATEMENT keyword
PERIOD_YEAR_RE = re.compile(r"STATEMENT.*?(\d{4})", re.IGNORECASE)

# Header that marks the start of the transactions section (monopoly)
HEADER_RE = re.compile(r"TRANSACTION\s+POSTING", re.IGNORECASE)

# Lines to unconditionally skip
SKIP_RE = re.compile(
    r"PAYMENT\s*[-–]\s*THANK|PAIEMENT|AUTOMATIC PAYMENT|CASH BACK|"
    r"NEW BALANCE|CREDIT BALANCE|OPENING BALANCE|PREVIOUS.{0,15}BALANCE|"
    r"MINIMUM PAYMENT|CREDIT LIMIT|AVAILABLE CREDIT|ANNUAL INTEREST|"
    r"RBCROYALBANK|RBC ROYAL BANK|P\.O\.\s*BOX|IF PAYING BY MAIL|"
    r"CALCULATING YOUR BALANCE",
    re.IGNORECASE,
)

# Lines starting with a month token — used to detect near-miss rows
MONTH_START_RE = re.compile(rf"^{_MONTH_ALT}{_DATE_SEP}\d", re.IGNORECASE)

# Line-merge guard: keep \n only before lines that start with a transaction date
# Allow optional leading whitespace (layout=True adds column spacing)
_MERGE_KEEP_RE = re.compile(rf"\n(?!\s*{_MONTH_ALT}{_DATE_SEP}\d)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_statement_year(all_text: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Return (start_month_num, start_year, end_year) from statement text."""
    m = PERIOD_RE.search(all_text)
    if m:
        sm = MONTH_TO_NUM.get(m.group("sm").upper())
        ey = int(m.group("ey"))
        # Start year equals end year unless Dec→Jan boundary
        sy = ey - 1 if (sm and sm == 12) else ey
        return sm, sy, ey

    # Fallback: first 4-digit year near "STATEMENT"
    m2 = PERIOD_YEAR_RE.search(all_text)
    if m2:
        y = int(m2.group(1))
        return None, y, y

    return None, None, None


def _resolve_year(
    date_token: str,
    start_month: Optional[int],
    start_year: Optional[int],
    end_year: Optional[int],
) -> int:
    """Determine the correct year for a transaction date token like 'DEC 09'."""
    year = end_year or start_year or 2024
    if start_year and end_year and start_year != end_year:
        # Cross-year statement (e.g. Dec–Jan)
        month_str = re.match(r"([A-Z]{3})", date_token, re.IGNORECASE)
        if month_str:
            m = MONTH_TO_NUM.get(month_str.group(1).upper(), 1)
            if start_month and m >= start_month:
                return start_year
        return end_year
    return year


def _extract_date_parts(date_token: str) -> Tuple[str, str]:
    """Split 'DEC 09', 'DEC-09', or 'DEC09' into ('DEC', '09')."""
    token = date_token.strip()
    # Try splitting on dash or space first
    parts = re.split(r"[-\s]", token, maxsplit=1)
    if len(parts) == 2:
        return parts[0].upper(), parts[1].zfill(2)
    # No separator: split at letter/digit boundary (e.g. "JAN08" → "JAN", "08")
    m = re.match(r"([A-Za-z]+)(\d+)", token)
    if m:
        return m.group(1).upper(), m.group(2).zfill(2)
    return token.upper(), "01"


def _merge_continuation_lines(text: str) -> str:
    """
    Merge lines that are NOT the start of a new transaction into the
    previous line (andrewscwei technique).

    Keeps \\n only when the next line begins with a transaction date token
    (e.g. "DEC 09" or "DEC-09").  All other \\n become spaces so that
    continuation descriptions are joined with their parent transaction.
    """
    return _MERGE_KEEP_RE.sub(" ", text)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_rbc_pdf(pdf_path: str | Path) -> Tuple[List[Dict], List[Dict]]:
    """
    Parse an RBC Visa PDF statement.

    Returns:
        (transactions, skipped_rows) where skipped_rows are dicts with
        {"page": int, "reason": str, "row_text": str} for lines that looked
        like transaction candidates but failed full detection.
    """
    pdf_path = Path(pdf_path)
    transactions: List[Dict] = []
    skipped_rows: List[Dict] = []

    page_texts: List[Tuple[int, str]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # layout=True preserves physical column spacing (monopoly approach)
            text = page.extract_text(layout=True) or ""
            page_texts.append((page_num, text))

    all_text = "\n".join(t for _, t in page_texts)
    start_month, start_year, end_year = _parse_statement_year(all_text)

    if start_year is None:
        year_match = re.search(r"(\d{4})", pdf_path.name)
        start_year = int(year_match.group(1)) if year_match else 2024
        end_year = start_year

    for page_num, raw_text in page_texts:
        # Step 1: merge continuation lines (andrewscwei)
        text = _merge_continuation_lines(raw_text)

        # Step 2: gate — only scan lines after the TRANSACTION/POSTING header
        header_match = HEADER_RE.search(text)
        scan_text = text[header_match.end():] if header_match else text

        for line in scan_text.splitlines():
            line = line.strip()
            if not line:
                continue

            if SKIP_RE.search(line):
                continue

            m = TXN_RE.search(line)
            if m:
                t_token = m.group("transaction_date")
                p_token = m.group("posting_date")
                desc = m.group("description").strip()
                polarity = m.group("polarity") or ""
                amount_raw = polarity + m.group("amount")

                tmon, tday = _extract_date_parts(t_token)
                pmon, pday = _extract_date_parts(p_token)

                if tmon not in MONTH_TO_NUM or pmon not in MONTH_TO_NUM:
                    skipped_rows.append({
                        "page": page_num,
                        "reason": "invalid_month",
                        "row_text": line,
                    })
                    continue

                ty = _resolve_year(t_token, start_month, start_year, end_year)
                py = _resolve_year(p_token, start_month, start_year, end_year)

                transactions.append({
                    "institution": "RBC_VISA",
                    "source_file": pdf_path.name,
                    "page_number": page_num,
                    "raw_line": line,
                    "transaction_date_raw": f"{tmon} {tday} {ty}",
                    "posted_date_raw": f"{pmon} {pday} {py}",
                    "merchant_raw": desc,
                    "description_raw": desc,
                    "amount_raw": amount_raw,
                    "reference_number": "",
                    "foreign_currency_info": None,
                })

            elif MONTH_START_RE.match(line):
                skipped_rows.append({
                    "page": page_num,
                    "reason": "no_amount_match",
                    "row_text": line,
                })

    return transactions, skipped_rows
