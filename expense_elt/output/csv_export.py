"""
csv_export.py - Generate output CSV files from the database.

Output files (written to expense_elt/output/):
  - business_expenses.csv   : deductible_status in (full, partial)
  - all_transactions.csv    : every transaction
  - review_required.csv     : review_required = True
  - category_summary.csv    : group by category, sum amounts
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from staging.database import get_connection

_OUTPUT_DIR = Path(__file__).parent.parent / "output"

# Full column list for transaction exports
_TXN_COLUMNS = [
    "transaction_id",
    "institution",
    "source_file",
    "transaction_date",
    "posted_date",
    "merchant_raw",
    "merchant_normalized",
    "description_raw",
    "original_amount",
    "currency",
    "is_credit",
    "category",
    "deductible_status",
    "deductible_amount",
    "confidence",
    "review_required",
    "rule_applied",
    "notes",
]

_SUMMARY_COLUMNS = [
    "category",
    "transaction_count",
    "total_original_amount",
    "total_deductible_amount",
]


def _write_csv(file_path: Path, columns: List[str], rows: List[tuple]) -> int:
    """Write rows to a CSV file. Returns number of rows written."""
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)
    return len(rows)


def export_all(verbose: bool = False) -> Dict[str, int]:
    """
    Generate all output CSVs.

    Returns stats dict with counts for each file.
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    con = get_connection()
    stats: Dict[str, int] = {}

    # Base query joining normalized + categorized
    base_query = """
        SELECT
            nt.transaction_id,
            nt.institution,
            nt.source_file,
            nt.transaction_date,
            nt.posted_date,
            nt.merchant_raw,
            nt.merchant_normalized,
            nt.description_raw,
            nt.original_amount,
            nt.currency,
            nt.is_credit,
            ct.category,
            ct.deductible_status,
            ct.deductible_amount,
            ct.confidence,
            ct.review_required,
            ct.rule_applied,
            ct.notes
        FROM normalized_transactions nt
        LEFT JOIN categorized_transactions ct
            ON nt.transaction_id = ct.transaction_id
    """

    try:
        # -----------------------------------------------------------------
        # 1. all_transactions.csv
        # -----------------------------------------------------------------
        all_rows = con.execute(base_query + " ORDER BY nt.transaction_date, nt.merchant_normalized").fetchall()
        all_path = _OUTPUT_DIR / "all_transactions.csv"
        count = _write_csv(all_path, _TXN_COLUMNS, all_rows)
        stats["all_transactions"] = count
        if verbose:
            print(f"  all_transactions.csv: {count} rows -> {all_path}")

        # -----------------------------------------------------------------
        # 2. business_expenses.csv
        # -----------------------------------------------------------------
        biz_rows = con.execute(
            base_query
            + " WHERE ct.deductible_status IN ('full', 'partial') AND ct.review_required = FALSE "
            + " ORDER BY nt.transaction_date, nt.merchant_normalized"
        ).fetchall()
        biz_path = _OUTPUT_DIR / "business_expenses.csv"
        count = _write_csv(biz_path, _TXN_COLUMNS, biz_rows)
        stats["business_expenses"] = count
        if verbose:
            print(f"  business_expenses.csv: {count} rows -> {biz_path}")

        # -----------------------------------------------------------------
        # 3. review_required.csv
        # -----------------------------------------------------------------
        review_rows = con.execute(
            base_query
            + " WHERE ct.review_required = TRUE "
            + " ORDER BY nt.transaction_date, nt.merchant_normalized"
        ).fetchall()
        review_path = _OUTPUT_DIR / "review_required.csv"
        count = _write_csv(review_path, _TXN_COLUMNS, review_rows)
        stats["review_required"] = count
        if verbose:
            print(f"  review_required.csv: {count} rows -> {review_path}")

        # -----------------------------------------------------------------
        # 4. category_summary.csv
        # -----------------------------------------------------------------
        summary_rows = con.execute(
            """
            SELECT
                ct.category,
                COUNT(*) AS transaction_count,
                ROUND(SUM(nt.original_amount), 2) AS total_original_amount,
                ROUND(SUM(COALESCE(ct.deductible_amount, 0)), 2) AS total_deductible_amount
            FROM normalized_transactions nt
            LEFT JOIN categorized_transactions ct ON nt.transaction_id = ct.transaction_id
            WHERE ct.category IS NOT NULL
              AND ct.deductible_status IN ('full', 'partial')
              AND ct.review_required = FALSE
            GROUP BY ct.category
            ORDER BY total_deductible_amount DESC
            """
        ).fetchall()
        summary_path = _OUTPUT_DIR / "category_summary.csv"
        count = _write_csv(summary_path, _SUMMARY_COLUMNS, summary_rows)
        stats["category_summary"] = count
        if verbose:
            print(f"  category_summary.csv: {count} rows -> {summary_path}")

    finally:
        con.close()

    return stats
