from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import require_auth
from api.dependencies import get_db, pipeline_lock
from api.schemas import InstitutionBreakdown, PipelineStatusResponse

router = APIRouter()


@router.get("/status", response_model=PipelineStatusResponse)
def get_status(con=Depends(get_db), claims: dict = Depends(require_auth)):
    is_accountant = claims.get("role") == "accountant"
    personal_exclude = " AND deductible_status != 'personal'" if is_accountant else ""

    def count(query: str) -> int:
        result = con.execute(query).fetchone()
        return result[0] if result else 0

    raw_count = count("SELECT COUNT(*) FROM raw_transactions")
    normalized_count = count("SELECT COUNT(*) FROM normalized_transactions")
    categorized_count = count(
        f"SELECT COUNT(*) FROM categorized_transactions WHERE 1=1{personal_exclude}"
    )
    review_count = count(
        f"SELECT COUNT(*) FROM categorized_transactions WHERE review_required = TRUE{personal_exclude}"
    )
    reviewed_count = count(
        f"SELECT COUNT(*) FROM categorized_transactions WHERE review_required = FALSE{personal_exclude}"
    )
    business_count = count(
        "SELECT COUNT(*) FROM categorized_transactions WHERE deductible_status IN ('full', 'partial') AND review_required = FALSE"
    )
    personal_count = 0 if is_accountant else count(
        "SELECT COUNT(*) FROM categorized_transactions WHERE deductible_status = 'personal'"
    )
    total_ded = con.execute(
        "SELECT ROUND(SUM(deductible_amount), 2) FROM categorized_transactions "
        "WHERE deductible_status IN ('full', 'partial') AND review_required = FALSE"
    ).fetchone()
    total_deductible = float(total_ded[0]) if total_ded and total_ded[0] else 0.0

    inst_rows = con.execute("""
        SELECT
            r.institution,
            COUNT(DISTINCT r.raw_id) AS raw_count,
            COUNT(DISTINCT n.transaction_id) AS norm_count,
            COUNT(DISTINCT c.transaction_id) AS cat_count,
            COUNT(DISTINCT CASE WHEN c.review_required = TRUE THEN c.transaction_id END) AS review_count,
            COUNT(DISTINCT CASE WHEN c.deductible_status IN ('full','partial') AND c.review_required = FALSE THEN c.transaction_id END) AS biz_count
        FROM raw_transactions r
        LEFT JOIN normalized_transactions n ON r.raw_id = n.raw_id
        LEFT JOIN categorized_transactions c ON n.transaction_id = c.transaction_id
        GROUP BY r.institution
        ORDER BY r.institution
    """).fetchall()

    by_institution = [
        InstitutionBreakdown(
            institution=row[0] or "Unknown",
            raw_count=row[1],
            normalized_count=row[2],
            categorized_count=row[3],
            review_count=row[4],
            business_count=row[5],
        )
        for row in inst_rows
    ]

    return PipelineStatusResponse(
        raw_count=raw_count,
        normalized_count=normalized_count,
        categorized_count=categorized_count,
        review_count=review_count,
        reviewed_count=reviewed_count,
        business_count=business_count,
        personal_count=personal_count,
        total_deductible=total_deductible,
        pipeline_running=pipeline_lock.locked(),
        by_institution=by_institution,
    )
