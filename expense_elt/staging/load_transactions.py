"""
load_transactions.py - Scan PDF files, parse them, and load into raw_transactions.

Supports RBC Visa, BMO Mastercard, and American Express PDFs.
Logs parse errors to logs/parse_errors.log.
"""

from __future__ import annotations

import hashlib
import json
import logging
import traceback
from pathlib import Path
from typing import Dict, List

from ingestion.rbc_parser import parse_rbc_pdf
from ingestion.bmo_parser import parse_bmo_pdf
from ingestion.amex_parser import parse_amex_pdf
import ingestion.monopoly_adapter as _monopoly
from staging.database import get_connection, initialize_db

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_MODULE_DIR = Path(__file__).parent
_PROJECT_DIR = _MODULE_DIR.parent

_RBC_DIR = _PROJECT_DIR / "data" / "RBC_Visa"
_BMO_DIR = _PROJECT_DIR / "data" / "BMO_Mastercard"
_AMEX_DIR = _PROJECT_DIR / "data" / "Amex"
_LOG_FILE = _PROJECT_DIR / "logs" / "parse_errors.log"
_SKIPPED_LOG_FILE = _PROJECT_DIR / "logs" / "parse_skipped.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_id(source_file: str, page_number: int, raw_line: str) -> str:
    """Generate a stable MD5 hash as the raw_id."""
    key = f"{source_file}|{page_number}|{raw_line}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def _txn_to_row(txn: Dict) -> Dict:
    """Convert a parser output dict to a raw_transactions row dict."""
    source_file = txn.get("source_file", "")
    page_number = txn.get("page_number", 0)
    raw_line = txn.get("raw_line", "")

    raw_id = _make_raw_id(source_file, page_number, raw_line)

    # Extra data: put any non-standard fields into JSON
    extra: Dict = {}
    for key in ("reference_number", "foreign_currency_info", "cardholder"):
        val = txn.get(key)
        if val is not None and val != "":
            extra[key] = val

    return {
        "raw_id": raw_id,
        "institution": txn.get("institution", ""),
        "source_file": source_file,
        "page_number": page_number,
        "raw_line": raw_line,
        "transaction_date_raw": txn.get("transaction_date_raw", ""),
        "posted_date_raw": txn.get("posted_date_raw", ""),
        "merchant_raw": txn.get("merchant_raw", ""),
        "description_raw": txn.get("description_raw", ""),
        "amount_raw": txn.get("amount_raw", ""),
        "extra_data": json.dumps(extra) if extra else None,
    }


def _insert_rows(rows: List[Dict], con) -> int:
    """
    Insert rows into raw_transactions.
    Returns count of rows actually inserted (skipping duplicates).
    """
    inserted = 0
    for row in rows:
        try:
            con.execute(
                """
                INSERT OR IGNORE INTO raw_transactions
                    (raw_id, institution, source_file, page_number, raw_line,
                     transaction_date_raw, posted_date_raw, merchant_raw,
                     description_raw, amount_raw, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    row["raw_id"],
                    row["institution"],
                    row["source_file"],
                    row["page_number"],
                    row["raw_line"],
                    row["transaction_date_raw"],
                    row["posted_date_raw"],
                    row["merchant_raw"],
                    row["description_raw"],
                    row["amount_raw"],
                    row["extra_data"],
                ],
            )
            inserted += 1
        except Exception as exc:
            _logger.error("Insert failed for raw_id=%s: %s", row.get("raw_id"), exc)
    return inserted


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _write_skipped_log(source_file: str, skipped_rows: List[Dict]) -> None:
    """Append skipped partial-match rows to parse_skipped.log."""
    if not skipped_rows:
        return
    _SKIPPED_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_SKIPPED_LOG_FILE, "a", encoding="utf-8") as f:
        for s in skipped_rows:
            f.write(f"[{source_file}] page {s['page']} | {s['reason']} | {s['row_text']}\n")


def _parse_one_pdf_custom(pdf_path: Path, label: str) -> tuple:
    """
    Parse a single PDF with the custom parser. Returns (transactions, skipped_rows).
    label is 'RBC', 'BMO', or 'AMEX'.
    """
    if label == "RBC":
        return parse_rbc_pdf(pdf_path)      # returns (txns, skipped)
    elif label == "BMO":
        return parse_bmo_pdf(pdf_path), []  # bmo returns list only
    else:
        return parse_amex_pdf(pdf_path), [] # amex returns list only


def _parse_one_pdf_monopoly(pdf_path: Path, label: str) -> tuple:
    """Parse a single PDF with monopoly-core. Returns (transactions, [])."""
    txns = _monopoly.parse_pdf_with_monopoly(pdf_path)
    return txns, []


def load_all_pdfs(verbose: bool = False, parser: str = "monopoly") -> Dict[str, int]:
    """
    Parse all PDFs and load into raw_transactions.

    Args:
        parser: 'custom' (default) — use built-in regex parsers
                'monopoly'          — use monopoly-core package for all PDFs
                'auto'              — try custom first; if 0 results, try monopoly

    Returns dict with keys: rbc_files, bmo_files, amex_files, total_parsed,
    total_inserted, skipped_partial, errors, parser_used.
    """
    initialize_db()
    con = get_connection()

    # Validate monopoly availability when needed
    if parser in ("monopoly", "auto") and not _monopoly.is_available():
        if parser == "monopoly":
            raise ImportError(
                "monopoly-core is not installed. Run: pip install monopoly-core"
            )
        # auto: fall back silently to custom
        parser = "custom"

    stats = {
        "rbc_files": 0,
        "bmo_files": 0,
        "amex_files": 0,
        "total_parsed": 0,
        "total_inserted": 0,
        "skipped_partial": 0,
        "errors": 0,
        "parser_used": parser,
    }

    def _process_pdf(pdf_path: Path, label: str, stat_key: str) -> None:
        """Route one PDF through the selected parser and record stats."""
        try:
            if parser == "monopoly":
                transactions, skipped_rows = _parse_one_pdf_monopoly(pdf_path, label)
            elif parser == "auto":
                transactions, skipped_rows = _parse_one_pdf_custom(pdf_path, label)
                if len(transactions) == 0 and _monopoly.is_available():
                    if verbose:
                        print(f"  [AUTO] {pdf_path.name}: custom returned 0, trying monopoly...")
                    try:
                        transactions, skipped_rows = _parse_one_pdf_monopoly(pdf_path, label)
                        if verbose and transactions:
                            print(f"  [AUTO] {pdf_path.name}: monopoly found {len(transactions)} transactions")
                    except Exception as mono_exc:
                        _logger.warning("monopoly fallback failed for %s: %s", pdf_path.name, mono_exc)
            else:  # custom
                transactions, skipped_rows = _parse_one_pdf_custom(pdf_path, label)

            rows = [_txn_to_row(t) for t in transactions]
            inserted = _insert_rows(rows, con)
            stats[stat_key] += 1
            stats["total_parsed"] += len(transactions)
            stats["total_inserted"] += inserted
            stats["skipped_partial"] += len(skipped_rows)
            _write_skipped_log(pdf_path.name, skipped_rows)
            if verbose:
                skipped_str = f", {len(skipped_rows)} skipped" if skipped_rows else ""
                print(f"  [{label}] {pdf_path.name}: {len(transactions)} parsed, {inserted} inserted{skipped_str}")
        except Exception:
            stats["errors"] += 1
            _logger.error(
                "Failed to parse %s PDF %s:\n%s", label, pdf_path.name, traceback.format_exc()
            )
            if verbose:
                print(f"  [ERROR] {label} {pdf_path.name}: see logs/parse_errors.log")

    try:
        for pdf_path in sorted(_RBC_DIR.glob("*.pdf")):
            _process_pdf(pdf_path, "RBC", "rbc_files")

        for pdf_path in sorted(_BMO_DIR.glob("*.pdf")):
            _process_pdf(pdf_path, "BMO", "bmo_files")

        amex_pdfs = sorted(_AMEX_DIR.glob("*.pdf")) if _AMEX_DIR.exists() else []
        for pdf_path in amex_pdfs:
            _process_pdf(pdf_path, "AMEX", "amex_files")

        con.commit()
    finally:
        con.close()

    return stats
