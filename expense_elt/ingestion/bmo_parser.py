"""
bmo_parser.py - Parse BMO Mastercard PDF statements.

References:
  - https://github.com/benjamin-awd/monopoly  (patterns, header gating)
  - https://github.com/andrewscwei/rbc-statement-parser  (line merging)

Strategy:
  1. Extract physical-layout text per page with pdfplumber (layout=True)
  2. Merge continuation lines into transaction lines
  3. Find the DATE/DATE/DESCRIPTION header to gate where transactions begin
  4. Match each line with TXN_RE (monopoly BMO Credit pattern)
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

# BMO abbreviated month with optional period: "Nov." or "Nov"
_BMO_MONTH = r"[A-Z][a-z]{2,3}\.?"

# ---------------------------------------------------------------------------
# Regex patterns  (monopoly bmo.py BMO Credit, adapted)
# ---------------------------------------------------------------------------

# Transaction line: two dot-month dates + description + amount + optional CR
# BMO format: "Nov. 15 Nov. 17 MERCHANT 23.45 CR"
TXN_RE = re.compile(
    r"(?P<transaction_date>[A-Z][a-z]{2,3}\.?\s+\d{1,2})\s+"
    r"(?P<posting_date>[A-Z][a-z]{2,3}\.?\s+\d{1,2})\s+"
    r"(?P<description>.+?)\s+"
    r"(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})\s*"
    r"(?P<cr>CR)?$",
    re.IGNORECASE,
)

# Statement date (monopoly bmo.py): "Statement date Nov. 15, 2025"
PERIOD_DATE_RE = re.compile(
    r"Statement\s+date\s+(?P<sm>[A-Z][a-z]{2,3})\.\s+\d{1,2},\s+(?P<ey>\d{4})",
    re.IGNORECASE,
)
# Fallback: "Statement period Jun. 10, 2025 - Jul. 9, 2025" (older BMO format)
PERIOD_RANGE_RE = re.compile(
    r"Statement\s+period\s+[A-Z][a-z]{2,3}\.?\s+\d+,?\s+(?P<sy>\d{4})"
    r"\s*[-–to]+\s*[A-Z][a-z]{2,3}\.?\s+\d+,?\s+(?P<ey>\d{4})",
    re.IGNORECASE,
)
PERIOD_START_MONTH_RE = re.compile(r"Statement\s+(?:period|date)\s+([A-Z][a-z]{2,3})", re.IGNORECASE)
PERIOD_YEAR_RE = re.compile(r"Statement\s+(?:period|date).*?(\d{4})", re.IGNORECASE)

# Header that marks start of transactions section (monopoly)
HEADER_RE = re.compile(r"DATE\s+DATE\s+DESCRIPTION", re.IGNORECASE)

# Cardholder line: "XXXX XXXX XXXX 1234 JANE A DOE"
CARDHOLDER_RE = re.compile(r"(?:XXXX\s+){3}[\dX]+\s+([A-Z][A-Z\s]+)", re.IGNORECASE)

# Lines to unconditionally skip
SKIP_RE = re.compile(
    r"PAYMENT RECEIVED|PAYMENT-THANK|PAIEMENT|"
    r"SUBTOTAL FOR|TOTAL FOR CARD|CONTINUED ON NEXT PAGE|"
    r"NEW BALANCE|PREVIOUS BALANCE|TOTAL BALANCE|"
    r"MINIMUM PAYMENT|CREDIT LIMIT|AVAILABLE CREDIT|"
    r"CARD NUMBER|ANNUAL FEE",
    re.IGNORECASE,
)

# Line-merge guard: keep \n only before lines that start with a BMO date token
# Allow optional leading whitespace (layout=True adds column spacing)
_MERGE_KEEP_RE = re.compile(r"\n(?!\s*[A-Z][a-z]{2,3}\.?\s+\d)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_statement_year(all_text: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Return (start_month_num, start_year, end_year) from statement text."""
    # Try "Statement date Nov. 15, 2025" (monopoly pattern)
    m = PERIOD_DATE_RE.search(all_text)
    if m:
        sm = MONTH_TO_NUM.get(m.group("sm").upper())
        ey = int(m.group("ey"))
        return sm, ey, ey

    # Try "Statement period Jun. 10, 2025 - Jul. 9, 2025" (older format)
    m2 = PERIOD_RANGE_RE.search(all_text)
    if m2:
        sm_match = PERIOD_START_MONTH_RE.search(all_text)
        sm = MONTH_TO_NUM.get(sm_match.group(1).upper()) if sm_match else None
        sy = int(m2.group("sy"))
        ey = int(m2.group("ey"))
        return sm, sy, ey

    # Fallback: first year near "Statement period/date"
    m3 = PERIOD_YEAR_RE.search(all_text)
    if m3:
        y = int(m3.group(1))
        sm_match = PERIOD_START_MONTH_RE.search(all_text)
        sm = MONTH_TO_NUM.get(sm_match.group(1).upper()) if sm_match else None
        return sm, y, y

    return None, None, None


def _resolve_year(
    date_token: str,
    start_month: Optional[int],
    start_year: Optional[int],
    end_year: Optional[int],
) -> int:
    """Determine year for a date token like 'Nov. 15'."""
    year = end_year or start_year or 2024
    if start_year and end_year and start_year != end_year:
        month_str = re.match(r"([A-Za-z]{3})", date_token.strip())
        if month_str:
            m = MONTH_TO_NUM.get(month_str.group(1).upper(), 1)
            if start_month and m >= start_month:
                return start_year
        return end_year
    return year


def _extract_date_parts(date_token: str) -> Tuple[str, str]:
    """Split 'Nov. 15' or 'Nov 15' into ('NOV', '15')."""
    parts = re.split(r"[.\s]+", date_token.strip())
    mon = parts[0].upper()
    day = parts[-1].zfill(2) if len(parts) > 1 else "01"
    return mon, day


def _merge_continuation_lines(text: str) -> str:
    """
    Merge lines that are not the start of a new BMO transaction into the
    previous line.  Keeps \\n only before BMO date tokens like "Nov. 15".
    """
    return _MERGE_KEEP_RE.sub(" ", text)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_bmo_pdf(pdf_path: str | Path) -> List[Dict]:
    """
    Parse a BMO Mastercard PDF statement and return a list of transaction dicts.
    """
    pdf_path = Path(pdf_path)
    transactions: List[Dict] = []

    page_texts: List[Tuple[int, str]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(layout=True) or ""
            page_texts.append((page_num, text))

    all_text = "\n".join(t for _, t in page_texts)
    start_month, start_year, end_year = _parse_statement_year(all_text)

    if start_year is None:
        year_match = re.search(r"(\d{4})", pdf_path.name)
        start_year = int(year_match.group(1)) if year_match else 2025
        end_year = start_year

    current_cardholder = "UNKNOWN"

    for page_num, raw_text in page_texts:
        # Detect cardholder from raw text before merging
        ch = CARDHOLDER_RE.search(raw_text)
        if ch:
            current_cardholder = ch.group(1).strip().upper()

        # Step 1: merge continuation lines
        text = _merge_continuation_lines(raw_text)

        # Step 2: gate — only scan lines after DATE/DATE/DESCRIPTION header
        header_match = HEADER_RE.search(text)
        scan_text = text[header_match.end():] if header_match else text

        for line in scan_text.splitlines():
            line = line.strip()
            if not line:
                continue

            if SKIP_RE.search(line):
                continue

            m = TXN_RE.search(line)
            if not m:
                continue

            t_token = m.group("transaction_date")
            p_token = m.group("posting_date")
            desc = m.group("description").strip()
            amount_str = m.group("amount")
            is_cr = bool(m.group("cr"))

            tmon, tday = _extract_date_parts(t_token)
            pmon, pday = _extract_date_parts(p_token)

            if tmon not in MONTH_TO_NUM or pmon not in MONTH_TO_NUM:
                continue

            ty = _resolve_year(t_token, start_month, start_year, end_year)
            py = _resolve_year(p_token, start_month, start_year, end_year)

            # Credits are negative (payment/refund)
            amount_raw = f"-{amount_str}" if is_cr else amount_str

            # Detect foreign currency in description
            foreign_currency_info: Optional[str] = None
            fc_match = re.search(r"\b([A-Z]{3})\s+([\d.]+@[\d.]+)", desc)
            if fc_match:
                foreign_currency_info = fc_match.group(0)

            transactions.append({
                "institution": "BMO_MASTERCARD",
                "source_file": pdf_path.name,
                "page_number": page_num,
                "raw_line": line,
                "transaction_date_raw": f"{tmon} {tday} {ty}",
                "posted_date_raw": f"{pmon} {pday} {py}",
                "merchant_raw": desc,
                "description_raw": desc,
                "amount_raw": amount_raw,
                "reference_number": "",
                "foreign_currency_info": foreign_currency_info,
                "cardholder": current_cardholder,
            })

    return transactions
