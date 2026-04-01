from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import require_pipeline_idle
from api.schemas import BatchReviewRequest, ReviewDecisionRequest, ReviewQueueResponse
from services.review_service import batch_apply, load_review_queue, save_single_review

router = APIRouter()


@router.get("/review-queue", response_model=ReviewQueueResponse)
def get_review_queue():
    queue = load_review_queue()
    return ReviewQueueResponse(transactions=queue, total=len(queue))


@router.post("/transactions/{transaction_id}/review")
def review_transaction(transaction_id: str, body: ReviewDecisionRequest, _=Depends(require_pipeline_idle)):
    # Look up the transaction to get merchant info
    from staging.database import get_connection

    con = get_connection()
    try:
        row = con.execute(
            "SELECT merchant_normalized, merchant_raw FROM normalized_transactions WHERE transaction_id = ?",
            [transaction_id],
        ).fetchone()
    finally:
        con.close()

    if not row:
        raise HTTPException(status_code=404, detail="Transaction not found")

    merchant_normalized, merchant_raw = row

    save_single_review(
        transaction_id=transaction_id,
        category=body.category,
        deductible_status=body.deductible_status,
        deductible_amount=body.deductible_amount,
        notes=body.notes,
        merchant_normalized=merchant_normalized,
        merchant_raw=merchant_raw,
    )

    return {"success": True, "transaction_id": transaction_id}


@router.post("/transactions/batch-review")
def batch_review(body: BatchReviewRequest, _=Depends(require_pipeline_idle)):
    count = batch_apply(
        merchant_normalized=body.merchant_normalized,
        category=body.category,
        deductible_status=body.deductible_status,
        notes=body.notes,
    )

    # Also save to merchant memory
    from categorization.merchant_memory import get_memory

    memory = get_memory()
    memory.save_decision(
        merchant_normalized=body.merchant_normalized,
        category=body.category,
        deductible_status=body.deductible_status,
        confidence=1.0,
        decision_source="manual_web_batch",
    )

    # Optionally save a keyword rule for future pipeline runs
    if body.save_rule and body.rule_keyword.strip():
        from config.config_writer import append_keyword_rule

        append_keyword_rule(body.rule_keyword.strip(), body.category, 0.90, source="api_review")

    return {"success": True, "updated_count": count}
