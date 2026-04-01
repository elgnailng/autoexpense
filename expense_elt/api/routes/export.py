"""CSV export routes — any authenticated user can download."""

from __future__ import annotations

import csv
import io
from typing import Literal

from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from api.auth import require_auth
from api.dependencies import get_db

router = APIRouter()

_TXN_COLUMNS = [
    "transaction_id", "institution", "source_file", "transaction_date", "posted_date",
    "merchant_raw", "merchant_normalized", "description_raw", "original_amount",
    "currency", "is_credit", "category", "deductible_status", "deductible_amount",
    "confidence", "review_required", "rule_applied", "notes",
]

_SUMMARY_COLUMNS = ["category", "transaction_count", "total_original_amount", "total_deductible_amount"]

_BASE_QUERY = """
    SELECT
        nt.transaction_id, nt.institution, nt.source_file, nt.transaction_date,
        nt.posted_date, nt.merchant_raw, nt.merchant_normalized, nt.description_raw,
        nt.original_amount, nt.currency, nt.is_credit,
        ct.category, ct.deductible_status, ct.deductible_amount,
        ct.confidence, ct.review_required, ct.rule_applied, ct.notes
    FROM normalized_transactions nt
    LEFT JOIN categorized_transactions ct ON nt.transaction_id = ct.transaction_id
"""


def _rows_to_csv(columns: list[str], rows: list) -> io.StringIO:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    buf.seek(0)
    return buf


@router.get("/export/{file_type}")
def download_export(
    file_type: Literal["business_expenses", "all_transactions", "category_summary", "review_required"],
    con=Depends(get_db),
    claims: dict = Depends(require_auth),
):
    """Download a CSV export file."""
    is_accountant = claims.get("role") == "accountant"
    personal_filter = " WHERE (ct.deductible_status IS NULL OR ct.deductible_status != 'personal')" if is_accountant else ""

    if file_type == "all_transactions":
        rows = con.execute(
            _BASE_QUERY + personal_filter + " ORDER BY nt.transaction_date, nt.merchant_normalized"
        ).fetchall()
        buf = _rows_to_csv(_TXN_COLUMNS, rows)
        filename = "all_transactions.csv"

    elif file_type == "business_expenses":
        rows = con.execute(
            _BASE_QUERY
            + " WHERE ct.deductible_status IN ('full', 'partial') AND ct.review_required = FALSE"
            + " ORDER BY nt.transaction_date, nt.merchant_normalized"
        ).fetchall()
        buf = _rows_to_csv(_TXN_COLUMNS, rows)
        filename = "business_expenses.csv"

    elif file_type == "review_required":
        review_personal = " AND ct.deductible_status != 'personal'" if is_accountant else ""
        rows = con.execute(
            _BASE_QUERY
            + " WHERE ct.review_required = TRUE" + review_personal
            + " ORDER BY nt.transaction_date, nt.merchant_normalized"
        ).fetchall()
        buf = _rows_to_csv(_TXN_COLUMNS, rows)
        filename = "review_required.csv"

    else:  # category_summary
        rows = con.execute("""
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
        """).fetchall()
        buf = _rows_to_csv(_SUMMARY_COLUMNS, rows)
        filename = "category_summary.csv"

    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
