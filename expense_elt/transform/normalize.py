"""
normalize.py - Normalize raw_transactions into normalized_transactions.

Steps:
- Parse dates from raw strings (e.g. "DEC 09 2024", "Jun. 19 2025")
- Parse amount: strip $, handle - prefix, handle CR suffix
- Normalize merchant name
- Generate transaction_id (UUID) and dedupe_hash
- Write to normalized_transactions table
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date
from typing import Dict, List, Optional, Tuple

from dateutil import parser as dateutil_parser

from staging.database import get_connection

# ---------------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------------

def parse_amount(amount_raw: str) -> Tuple[float, bool]:
    """
    Parse raw amount string to (float_value, is_credit).

    Handles:
      "$23.00"        -> (23.00, False)
      "-$2,000.00"    -> (-2000.00, True)
      "2.15"          -> (2.15, False)
      "-2.15"         -> (-2.15, True)
      "100.00 CR"     -> (-100.00, True)   BMO credit
    """
    s = amount_raw.strip()

    is_credit = False

    # BMO CR suffix
    if s.upper().endswith(" CR"):
        is_credit = True
        s = s[:-3].strip()

    # Strip currency symbol
    s = s.replace("$", "").replace(",", "").strip()

    if s.startswith("-"):
        is_credit = True
        s = s[1:]

    try:
        value = float(s)
    except ValueError:
        value = 0.0

    if is_credit:
        value = -abs(value)

    return value, is_credit


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def parse_date(date_raw: str) -> Optional[date]:
    """
    Parse a raw date string to a Python date.

    Accepts formats like:
      "DEC 09 2024"
      "JAN 01 2025"
      "Jun. 19 2025"
      "Jul. 1 2025"
    """
    if not date_raw or date_raw.strip() == "":
        return None
    # Normalise: remove extra dots but keep month name
    clean = date_raw.strip().replace(".", "")
    try:
        return dateutil_parser.parse(clean, fuzzy=True).date()
    except (ValueError, OverflowError):
        return None


# ---------------------------------------------------------------------------
# Merchant normalization
# ---------------------------------------------------------------------------

# Pattern to strip trailing city/province suffixes like "AMAZON.CA ON" -> "AMAZON.CA"
_PROVINCE_RE = re.compile(
    r'\s+(?:AB|BC|MB|NB|NL|NS|NT|NU|ON|PE|QC|SK|YT)\s*$',
    re.IGNORECASE,
)

# Strip reference codes after * (e.g. AMAZON.CA*ZR3WI9700 -> AMAZON.CA)
_REF_CODE_RE = re.compile(r'\*[A-Z0-9]{6,}', re.IGNORECASE)

# Collapse multiple spaces
_MULTI_SPACE_RE = re.compile(r'\s{2,}')

# Strip trailing ZIP/postal codes
_POSTAL_RE = re.compile(r'\s+[A-Z]\d[A-Z]\s*\d[A-Z]\d\s*$', re.IGNORECASE)

# Strip trailing US zip codes (5 digits)
_ZIP_RE = re.compile(r'\s+\d{5}\s*$')

# Strip city names that commonly appear (heuristic: ALL CAPS word at end after space)
# We'll strip trailing all-caps city/country tokens
_TRAILING_CAPS_CITY_RE = re.compile(r'(?:\s+[A-Z]{2,}){1,3}\s*$')


def normalize_merchant(merchant_raw: str) -> str:
    """
    Normalize a raw merchant name for consistent matching and deduplication.

    Steps:
    1. Strip leading/trailing whitespace
    2. Uppercase
    3. Remove reference codes after * (e.g. *ZR3WI9700)
    4. Strip trailing province codes (ON, BC, etc.)
    5. Strip postal codes
    6. Strip trailing foreign currency info (USD 159@...)
    7. Collapse multiple spaces
    8. Strip repeated punctuation
    """
    if not merchant_raw:
        return ""

    s = merchant_raw.strip().upper()

    # Remove foreign currency prefix pattern (BMO): USD 159@1.401257861
    s = re.sub(r'\b[A-Z]{3}\s+[\d.]+\s*@\s*[\d.]+\s*', '', s).strip()

    # Strip reference codes after *
    s = _REF_CODE_RE.sub("", s)

    # Strip trailing postal code
    s = _POSTAL_RE.sub("", s)

    # Strip trailing ZIP
    s = _ZIP_RE.sub("", s)

    # Strip trailing province code
    s = _PROVINCE_RE.sub("", s)

    # Collapse multiple spaces
    s = _MULTI_SPACE_RE.sub(" ", s).strip()

    # Remove repeated punctuation (e.g. "..." -> ".")
    s = re.sub(r'([^\w\s])\1+', r'\1', s)

    return s.strip()


# ---------------------------------------------------------------------------
# Deduplication hash
# ---------------------------------------------------------------------------

def make_dedupe_hash(
    institution: str,
    transaction_date: Optional[date],
    merchant_normalized: str,
    amount: float,
) -> str:
    """Generate a hash for deduplication."""
    date_str = str(transaction_date) if transaction_date else ""
    key = f"{institution}|{date_str}|{merchant_normalized}|{amount:.2f}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Main normalization function
# ---------------------------------------------------------------------------

def normalize_transactions(verbose: bool = False) -> Dict[str, int]:
    """
    Read all raw_transactions and write normalized records.

    Returns stats dict.
    """
    con = get_connection()
    stats = {"total_raw": 0, "normalized": 0, "skipped": 0, "errors": 0}

    try:
        rows = con.execute(
            """
            SELECT raw_id, institution, source_file, page_number,
                   transaction_date_raw, posted_date_raw,
                   merchant_raw, description_raw, amount_raw
            FROM raw_transactions
            """
        ).fetchall()

        stats["total_raw"] = len(rows)

        for row in rows:
            (
                raw_id, institution, source_file, page_number,
                transaction_date_raw, posted_date_raw,
                merchant_raw, description_raw, amount_raw,
            ) = row

            try:
                # Check if already normalized
                existing = con.execute(
                    "SELECT transaction_id FROM normalized_transactions WHERE raw_id = ?",
                    [raw_id],
                ).fetchone()
                if existing:
                    stats["skipped"] += 1
                    continue

                # Parse dates
                transaction_date = parse_date(transaction_date_raw)
                posted_date = parse_date(posted_date_raw)

                # Parse amount
                original_amount, is_credit = parse_amount(amount_raw)

                # Normalize merchant
                merchant_normalized = normalize_merchant(merchant_raw or "")

                # Generate IDs
                transaction_id = str(uuid.uuid4())
                dedupe_hash = make_dedupe_hash(
                    institution or "",
                    transaction_date,
                    merchant_normalized,
                    original_amount,
                )

                con.execute(
                    """
                    INSERT OR IGNORE INTO normalized_transactions
                        (transaction_id, raw_id, institution, source_file, page_number,
                         transaction_date, posted_date, merchant_raw, merchant_normalized,
                         description_raw, original_amount, currency, is_credit, dedupe_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CAD', ?, ?)
                    """,
                    [
                        transaction_id, raw_id, institution, source_file, page_number,
                        str(transaction_date) if transaction_date else None,
                        str(posted_date) if posted_date else None,
                        merchant_raw, merchant_normalized, description_raw,
                        original_amount, is_credit, dedupe_hash,
                    ],
                )
                stats["normalized"] += 1

                if verbose:
                    print(f"  Normalized: {merchant_normalized} | {original_amount:.2f} | {transaction_date}")

            except Exception as exc:
                stats["errors"] += 1
                if verbose:
                    print(f"  [ERROR] raw_id={raw_id}: {exc}")

        con.commit()
    finally:
        con.close()

    return stats
