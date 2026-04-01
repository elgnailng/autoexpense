from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth import require_auth, require_flag_permission
from api.dependencies import get_db, require_pipeline_idle
from api.schemas import (
    BatchFlagRequest,
    BatchUpdateRequest,
    CreateTransactionRequest,
    FlagTransactionRequest,
    TransactionResponse,
    TransactionsListResponse,
)
from services.review_service import batch_update_by_ids
from transform.normalize import make_dedupe_hash, normalize_merchant

router = APIRouter()


def _row_to_transaction(row, columns) -> TransactionResponse:
    d = dict(zip(columns, row))
    # Convert date/timestamp fields to strings for JSON serialization
    for key in ("transaction_date", "posted_date", "normalized_at"):
        if d.get(key) is not None:
            d[key] = str(d[key])
    # Convert Decimal fields to float
    for key in ("original_amount", "deductible_amount", "confidence"):
        if d.get(key) is not None:
            d[key] = float(d[key])
    return TransactionResponse(**d)


def _is_accountant(claims: dict) -> bool:
    return claims.get("role") == "accountant"


@router.get("/transactions", response_model=TransactionsListResponse)
def list_transactions(
    institution: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    rule_source: Optional[str] = Query(None),
    sort: str = Query("date"),
    sort_dir: str = Query("desc"),
    limit: int = Query(50, ge=0),
    offset: int = Query(0, ge=0),
    con=Depends(get_db),
    claims: dict = Depends(require_auth),
):
    conditions: list[str] = []
    params: list = []

    # Accountants cannot see personal transactions
    if _is_accountant(claims):
        conditions.append("(c.deductible_status IS NULL OR c.deductible_status != 'personal')")

    if institution:
        conditions.append("n.institution = ?")
        params.append(institution.upper())

    if category:
        conditions.append("c.category = ?")
        params.append(category)

    if status:
        s = status.lower()
        if s == "review":
            conditions.append("c.review_required = TRUE")
        elif s == "reviewed":
            conditions.append("c.review_required = FALSE")
        elif s == "business":
            conditions.append("c.deductible_status IN ('full', 'partial')")
        elif s == "personal" and not _is_accountant(claims):
            conditions.append("c.deductible_status = 'personal'")

    if rule_source:
        conditions.append("c.rule_applied LIKE ?")
        params.append(f"{rule_source}%")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    direction = "ASC" if sort_dir.lower() == "asc" else "DESC"
    sort_map = {
        "date": f"n.transaction_date {direction}, n.merchant_normalized",
        "amount": f"n.original_amount {direction}",
        "merchant": f"n.merchant_normalized {direction}",
        "category": f"c.category {direction}",
        "status": f"c.deductible_status {direction}",
    }
    order_by = sort_map.get(sort.lower(), f"n.transaction_date {direction}, n.merchant_normalized")

    limit_clause = f"LIMIT {limit} OFFSET {offset}" if limit > 0 else ""

    query = f"""
        SELECT
            n.transaction_id,
            n.raw_id,
            n.institution,
            n.source_file,
            n.page_number,
            n.transaction_date,
            n.posted_date,
            n.merchant_raw,
            n.merchant_normalized,
            n.description_raw,
            n.original_amount,
            n.currency,
            n.is_credit,
            n.dedupe_hash,
            n.normalized_at,
            c.category,
            c.deductible_status,
            c.deductible_amount,
            c.confidence,
            c.review_required,
            c.rule_applied,
            c.notes
        FROM normalized_transactions n
        LEFT JOIN categorized_transactions c ON n.transaction_id = c.transaction_id
        {where_clause}
        ORDER BY {order_by}
        {limit_clause}
    """

    columns = [
        "transaction_id", "raw_id", "institution", "source_file", "page_number",
        "transaction_date", "posted_date", "merchant_raw", "merchant_normalized",
        "description_raw", "original_amount", "currency", "is_credit", "dedupe_hash",
        "normalized_at", "category", "deductible_status", "deductible_amount",
        "confidence", "review_required", "rule_applied", "notes",
    ]

    rows = con.execute(query, params).fetchall()

    agg_query = f"""
        SELECT COUNT(*), COALESCE(SUM(n.original_amount), 0)
        FROM normalized_transactions n
        LEFT JOIN categorized_transactions c ON n.transaction_id = c.transaction_id
        {where_clause}
    """
    agg_row = con.execute(agg_query, params).fetchone()
    total = agg_row[0]
    total_amount = float(agg_row[1])

    transactions = [_row_to_transaction(row, columns) for row in rows]

    return TransactionsListResponse(
        transactions=transactions, total=total, total_amount=total_amount
    )


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: str, con=Depends(get_db), claims: dict = Depends(require_auth)):
    columns = [
        "transaction_id", "raw_id", "institution", "source_file", "page_number",
        "transaction_date", "posted_date", "merchant_raw", "merchant_normalized",
        "description_raw", "original_amount", "currency", "is_credit", "dedupe_hash",
        "normalized_at", "category", "deductible_status", "deductible_amount",
        "confidence", "review_required", "rule_applied", "notes",
    ]

    row = con.execute(
        """
        SELECT
            nt.transaction_id,
            nt.raw_id,
            nt.institution,
            nt.source_file,
            nt.page_number,
            nt.transaction_date,
            nt.posted_date,
            nt.merchant_raw,
            nt.merchant_normalized,
            nt.description_raw,
            nt.original_amount,
            nt.currency,
            nt.is_credit,
            nt.dedupe_hash,
            nt.normalized_at,
            ct.category,
            ct.deductible_status,
            ct.deductible_amount,
            ct.confidence,
            ct.review_required,
            ct.rule_applied,
            ct.notes
        FROM normalized_transactions nt
        LEFT JOIN categorized_transactions ct ON nt.transaction_id = ct.transaction_id
        WHERE nt.transaction_id = ?
        """,
        [transaction_id],
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Transaction not found")

    txn = _row_to_transaction(row, columns)

    # Hide personal transactions from accountants
    if _is_accountant(claims) and txn.deductible_status == "personal":
        raise HTTPException(status_code=404, detail="Transaction not found")

    return txn


@router.post("/transactions", response_model=TransactionResponse)
def create_transaction(
    body: CreateTransactionRequest,
    con=Depends(get_db),
    claims: dict = Depends(require_auth),
    _=Depends(require_pipeline_idle),
):
    """Manually add a transaction (cash payments, transfers, etc.)."""
    # Parse and validate date
    try:
        txn_date = date.fromisoformat(body.transaction_date)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")

    merchant_normalized = normalize_merchant(body.merchant_name)
    if not merchant_normalized:
        raise HTTPException(400, "Merchant name is invalid after normalization.")

    amount = -abs(body.original_amount) if body.is_credit else abs(body.original_amount)

    dedupe_hash = make_dedupe_hash(
        institution=body.institution,
        transaction_date=txn_date,
        merchant_normalized=merchant_normalized,
        amount=amount,
    )

    # Check for duplicate
    existing = con.execute(
        "SELECT transaction_id FROM normalized_transactions WHERE dedupe_hash = ?",
        [dedupe_hash],
    ).fetchone()
    if existing:
        raise HTTPException(409, "A transaction with the same merchant, date, amount, and institution already exists.")

    transaction_id = str(uuid.uuid4())

    # Compute deductible amount
    if body.deductible_status == "full":
        deductible_amount = abs(amount)
    elif body.deductible_status == "personal":
        deductible_amount = 0.0
    elif body.deductible_status == "partial":
        if body.deductible_amount is None:
            raise HTTPException(400, "Deductible amount is required for partial status.")
        if body.deductible_amount > abs(amount):
            raise HTTPException(400, "Deductible amount cannot exceed the transaction amount.")
        deductible_amount = body.deductible_amount
    else:
        deductible_amount = 0.0

    # Insert into normalized_transactions
    con.execute(
        """
        INSERT INTO normalized_transactions (
            transaction_id, raw_id, institution, source_file, page_number,
            transaction_date, merchant_raw, merchant_normalized,
            original_amount, is_credit, dedupe_hash, currency
        ) VALUES (?, NULL, ?, 'manual_entry', NULL, ?, ?, ?, ?, ?, ?, 'CAD')
        """,
        [
            transaction_id, body.institution, txn_date,
            body.merchant_name, merchant_normalized,
            amount, body.is_credit, dedupe_hash,
        ],
    )

    # Insert into categorized_transactions
    con.execute(
        """
        INSERT INTO categorized_transactions (
            transaction_id, category, deductible_status, deductible_amount,
            confidence, review_required, rule_applied, notes
        ) VALUES (?, ?, ?, ?, 1.0, FALSE, 'manual', ?)
        """,
        [
            transaction_id, body.category, body.deductible_status,
            deductible_amount, body.notes,
        ],
    )

    con.commit()

    # Return the created transaction
    columns = [
        "transaction_id", "raw_id", "institution", "source_file", "page_number",
        "transaction_date", "posted_date", "merchant_raw", "merchant_normalized",
        "description_raw", "original_amount", "currency", "is_credit", "dedupe_hash",
        "normalized_at", "category", "deductible_status", "deductible_amount",
        "confidence", "review_required", "rule_applied", "notes",
    ]
    row = con.execute(
        """
        SELECT
            n.transaction_id, n.raw_id, n.institution, n.source_file, n.page_number,
            n.transaction_date, n.posted_date, n.merchant_raw, n.merchant_normalized,
            n.description_raw, n.original_amount, n.currency, n.is_credit, n.dedupe_hash,
            n.normalized_at, c.category, c.deductible_status, c.deductible_amount,
            c.confidence, c.review_required, c.rule_applied, c.notes
        FROM normalized_transactions n
        LEFT JOIN categorized_transactions c ON n.transaction_id = c.transaction_id
        WHERE n.transaction_id = ?
        """,
        [transaction_id],
    ).fetchone()

    return _row_to_transaction(row, columns)


@router.post("/transactions/{transaction_id}/flag")
def flag_transaction(
    transaction_id: str,
    body: FlagTransactionRequest,
    con=Depends(get_db),
    claims: dict = Depends(require_flag_permission),
):
    """Flag a transaction for owner review (accountant with view_flag permission)."""
    # Verify transaction exists
    row = con.execute(
        "SELECT transaction_id FROM categorized_transactions WHERE transaction_id = ?",
        [transaction_id],
    ).fetchone()
    if not row:
        raise HTTPException(404, "Transaction not found or not yet categorized.")

    email = claims.get("email", "unknown")
    flag_note = f"[Accountant flag - {email}]: {body.reason}"

    # Prepend flag note to existing notes
    existing = con.execute(
        "SELECT notes FROM categorized_transactions WHERE transaction_id = ?",
        [transaction_id],
    ).fetchone()
    current_notes = existing[0] or "" if existing else ""
    new_notes = f"{flag_note}\n{current_notes}".strip() if current_notes else flag_note

    con.execute(
        "UPDATE categorized_transactions SET review_required = TRUE, notes = ? WHERE transaction_id = ?",
        [new_notes, transaction_id],
    )
    con.commit()
    return {"success": True, "message": "Transaction flagged for review."}


@router.post("/transactions/batch-update")
def batch_update_transactions(body: BatchUpdateRequest, _=Depends(require_pipeline_idle)):
    """Batch-update category and status for multiple transactions."""
    count = batch_update_by_ids(
        transaction_ids=body.transaction_ids,
        category=body.category,
        deductible_status=body.deductible_status,
        notes=body.notes,
    )
    return {"success": True, "updated_count": count}


@router.post("/transactions/batch-flag")
def batch_flag_transactions(
    body: BatchFlagRequest,
    con=Depends(get_db),
    claims: dict = Depends(require_flag_permission),
    _=Depends(require_pipeline_idle),
):
    """Batch-flag multiple transactions for owner review."""
    email = claims.get("email", "unknown")
    flag_note = f"[Accountant flag - {email}]: {body.reason}"
    flagged_count = 0

    for tid in body.transaction_ids:
        row = con.execute(
            "SELECT transaction_id, deductible_status, notes FROM categorized_transactions WHERE transaction_id = ?",
            [tid],
        ).fetchone()
        if not row:
            continue
        # Skip personal transactions (defense-in-depth)
        if row[1] == "personal":
            continue

        current_notes = row[2] or ""
        new_notes = f"{flag_note}\n{current_notes}".strip() if current_notes else flag_note

        con.execute(
            "UPDATE categorized_transactions SET review_required = TRUE, notes = ? WHERE transaction_id = ?",
            [new_notes, tid],
        )
        flagged_count += 1

    con.commit()
    return {"success": True, "flagged_count": flagged_count}
