from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import require_auth
from api.dependencies import get_db
from api.schemas import CategorySummaryItem, SummaryResponse

router = APIRouter()


@router.get("/summary", response_model=SummaryResponse)
def get_summary(con=Depends(get_db), claims: dict = Depends(require_auth)):
    is_accountant = claims.get("role") == "accountant"
    personal_filter = " AND ct.deductible_status != 'personal'" if is_accountant else ""

    totals_row = con.execute(f"""
        SELECT
            COUNT(*) AS total_transactions,
            COALESCE(SUM(nt.original_amount), 0) AS total_spend,
            COALESCE(SUM(CASE WHEN ct.deductible_status IN ('full','partial') AND ct.review_required = FALSE THEN ct.deductible_amount ELSE 0 END), 0) AS total_deductible,
            COALESCE(SUM(CASE WHEN ct.deductible_status = 'personal' THEN nt.original_amount ELSE 0 END), 0) AS total_personal,
            COUNT(CASE WHEN ct.review_required THEN 1 END) AS review_count
        FROM categorized_transactions ct
        JOIN normalized_transactions nt ON ct.transaction_id = nt.transaction_id
        WHERE nt.is_credit = FALSE{personal_filter}
    """).fetchone()

    totals = {
        "total_transactions": totals_row[0],
        "total_spend": float(totals_row[1]),
        "total_deductible": float(totals_row[2]),
        "total_personal": 0 if is_accountant else float(totals_row[3]),
        "review_count": totals_row[4],
    }

    cat_rows = con.execute("""
        SELECT
            ct.category,
            COUNT(*) AS tx_count,
            SUM(nt.original_amount) AS total_original,
            SUM(ct.deductible_amount) AS total_deductible
        FROM categorized_transactions ct
        JOIN normalized_transactions nt ON ct.transaction_id = nt.transaction_id
        WHERE nt.is_credit = FALSE AND ct.deductible_status IN ('full', 'partial') AND ct.review_required = FALSE
        GROUP BY ct.category
        ORDER BY total_deductible DESC
    """).fetchall()

    by_category = [
        CategorySummaryItem(
            category=row[0] or "Uncategorized",
            transaction_count=row[1],
            total_original=float(row[2]),
            total_deductible=float(row[3]),
        )
        for row in cat_rows
    ]

    return SummaryResponse(totals=totals, by_category=by_category)
