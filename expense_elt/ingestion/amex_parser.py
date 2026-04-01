"""
amex_parser.py - Parse American Express PDF statements using text extraction + regex.

Strategy (inspired by https://github.com/Bizzaro/Teller):
  - Use pdfplumber page.extract_text() to get the full text of each page
  - Match transaction lines with regex
  - Amex date format: "Jan 15 Jan 17 MERCHANT 123.45"
  - Amounts: no $ prefix, optional CR suffix for credits

Note: Amex PDF layouts vary by card type. Adjust TXN_RE if needed for your
specific card. The patterns here are based on typical Amex Canada statements.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MONTH_TO_NUM: Dict[str, int] = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# Transaction line: "Jan 15 Jan 17 SOME MERCHANT 123.45" or "Jan 15 Jan 17 SOME MERCHANT 123.45 CR"
# Teller note: Amex lines don't always start at beginning of line (no ^ anchor)
TXN_RE = re.compile(
    r'(?:^|\s)(?P<tmon>[A-Z]{3})\s+(?P<tday>\d{1,2})\s+(?P<pmon>[A-Z]{3})\s+(?P<pday>\d{1,2})\s+'
    r'(?P<desc>.+?)\s+'
    r'(?P<amount>-?[\d,]+\.\d{2})\s*(?P<cr>CR)?$',
    re.IGNORECASE,
)

# Statement period / closing date
PERIOD_RE = re.compile(
    r'(?:Statement period|Closing Date|Payment Due).*?'
    r'(?P<sm>[A-Z]{3})\w*\s+\d+,?\s*(?P<sy>\d{4})\s*[-–to]+\s*'
    r'(?:[A-Z]{3})\w*\s+\d+,?\s*(?P<ey>\d{4})',
    re.IGNORECASE,
)
PERIOD_YEAR_RE = re.compile(
    r'(?:Statement period|Closing Date|statement\s+closing).*?(\d{4})',
    re.IGNORECASE,
)
PERIOD_START_MONTH_RE = re.compile(
    r'(?:Statement period|From)\s+([A-Z]{3})',
    re.IGNORECASE,
)

# Lines to skip
SKIP_RE = re.compile(
    r'PREVIOUS BALANCE|NEW BALANCE|PAYMENT RECEIVED|PAYMENTS.*CREDITS|'
    r'FEES|INTEREST CHARGED|TOTAL FEES|TOTAL INTEREST|'
    r'MINIMUM PAYMENT|CREDIT LIMIT|AVAILABLE CREDIT|'
    r'AMERICAN EXPRESS|CARD MEMBER|ACCOUNT NUMBER|'
    r'OPENING.*BALANCE|CLOSING.*BALANCE|'
    r'^Page\s+\d+|\bPage\s+\d+\s+of\s+\d+',
    re.IGNORECASE,
)

# A line that begins with a month-like token
MONTH_START_RE = re.compile(r'^[A-Z]{3}\s+\d', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Year detection helpers
# ---------------------------------------------------------------------------

def _parse_statement_year(all_text: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Extract (start_month_num, start_year, end_year) from statement text."""
    m = PERIOD_RE.search(all_text)
    if m:
        sy = int(m.group("sy"))
        ey = int(m.group("ey"))
        sm = MONTH_TO_NUM.get(m.group("sm").upper())
        return sm, sy, ey

    m2 = PERIOD_YEAR_RE.search(all_text)
    if m2:
        y = int(m2.group(1))
        sm_match = PERIOD_START_MONTH_RE.search(all_text)
        sm = MONTH_TO_NUM.get(sm_match.group(1).upper()) if sm_match else None
        return sm, y, y

    return None, None, None


def _resolve_year(
    month_str: str,
    start_month: Optional[int],
    start_year: Optional[int],
    end_year: Optional[int],
) -> int:
    """Determine the correct year for a transaction month."""
    year = end_year or start_year or 2024
    if start_year and end_year and start_year != end_year:
        m = MONTH_TO_NUM.get(month_str.upper(), 1)
        if start_month and m >= start_month:
            return start_year
        return end_year
    return year


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_amex_pdf(pdf_path: str | Path) -> List[Dict]:
    """
    Parse an American Express PDF statement and return a list of transaction dicts.
    """
    pdf_path = Path(pdf_path)
    transactions: List[Dict] = []

    page_texts: List[Tuple[int, str]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            page_texts.append((page_num, text))

    all_text = "\n".join(t for _, t in page_texts)
    start_month, start_year, end_year = _parse_statement_year(all_text)

    # Fallback year from filename
    if start_year is None:
        year_match = re.search(r'(\d{4})', pdf_path.name)
        start_year = int(year_match.group(1)) if year_match else 2024
        end_year = start_year

    for page_num, text in page_texts:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            if SKIP_RE.search(line):
                continue

            m = TXN_RE.match(line)
            if not m:
                continue

            tmon = m.group("tmon").upper()
            tday = m.group("tday").zfill(2)
            pmon = m.group("pmon").upper()
            pday = m.group("pday").zfill(2)
            desc = m.group("desc").strip()
            amount_str = m.group("amount")
            is_cr = bool(m.group("cr"))

            # Validate months
            if tmon not in MONTH_TO_NUM or pmon not in MONTH_TO_NUM:
                continue

            ty = _resolve_year(tmon, start_month, start_year, end_year)
            py = _resolve_year(pmon, start_month, start_year, end_year)

            # Credits are negative
            amount_raw = f"-{amount_str}" if is_cr else amount_str

            transactions.append({
                "institution": "AMEX",
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

    return transactions
