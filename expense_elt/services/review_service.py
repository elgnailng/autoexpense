"""
review_service.py - Data helpers for manual review (no Streamlit dependency).

Functions extracted from pages/2_Review.py so they can be reused by
the Streamlit UI, CLI review, or tests.
"""

from __future__ import annotations

import re

from categorization.merchant_memory import get_memory
from staging.database import get_connection


def load_review_queue():
    """Return a list of dicts with all review-pending transactions."""
    con = get_connection()
    try:
        rows = con.execute("""
            SELECT
                ct.transaction_id,
                ct.category,
                ct.confidence,
                ct.rule_applied,
                ct.deductible_status,
                ct.original_amount,
                ct.notes,
                nt.transaction_date,
                nt.merchant_raw,
                nt.merchant_normalized,
                nt.description_raw,
                nt.institution
            FROM categorized_transactions ct
            JOIN normalized_transactions nt ON ct.transaction_id = nt.transaction_id
            WHERE ct.review_required = TRUE
            ORDER BY nt.transaction_date ASC
        """).fetchall()
        columns = [
            "transaction_id", "category", "confidence", "rule_applied",
            "deductible_status", "original_amount", "notes",
            "transaction_date", "merchant_raw", "merchant_normalized",
            "description_raw", "institution",
        ]
        return [dict(zip(columns, row)) for row in rows]
    finally:
        con.close()


def save_single_review(transaction_id, category, deductible_status, deductible_amount, notes, merchant_normalized, merchant_raw):
    """Save one reviewed transaction to DB + merchant memory."""
    con = get_connection()
    try:
        con.execute(
            """
            UPDATE categorized_transactions
            SET category = ?,
                deductible_status = ?,
                deductible_amount = ?,
                confidence = 1.0,
                review_required = FALSE,
                notes = ?
            WHERE transaction_id = ?
            """,
            [category, deductible_status, deductible_amount, notes or "", transaction_id],
        )
        con.commit()
    finally:
        con.close()

    memory = get_memory()
    memory.save_decision(
        merchant_normalized=merchant_normalized or merchant_raw or "",
        category=category,
        deductible_status=deductible_status,
        confidence=1.0,
        decision_source="manual_web",
    )


def batch_apply(merchant_normalized, category, deductible_status, notes):
    """Apply the same decision to ALL review-pending transactions with the same merchant.

    Computes deductible_amount per transaction based on each transaction's own
    original_amount and the chosen deductible_status.
    """
    con = get_connection()
    try:
        rows = con.execute(
            """
            SELECT ct.transaction_id, ct.original_amount
            FROM categorized_transactions ct
            JOIN normalized_transactions nt ON ct.transaction_id = nt.transaction_id
            WHERE ct.review_required = TRUE
              AND nt.merchant_normalized = ?
            """,
            [merchant_normalized],
        ).fetchall()

        for tid, orig_amount in rows:
            amount = float(orig_amount) if orig_amount is not None else 0.0
            if deductible_status == "full":
                ded_amount = abs(amount)
            elif deductible_status == "personal":
                ded_amount = 0.0
            else:
                # partial — use original amount as default; deduction rules
                # will override on next categorize run if configured
                ded_amount = abs(amount)

            con.execute(
                """
                UPDATE categorized_transactions
                SET category = ?,
                    deductible_status = ?,
                    deductible_amount = ?,
                    confidence = 1.0,
                    review_required = FALSE,
                    notes = ?
                WHERE transaction_id = ?
                """,
                [category, deductible_status, ded_amount, notes or "", tid],
            )
        con.commit()
        return len(rows)
    finally:
        con.close()


def batch_update_by_ids(transaction_ids, category, deductible_status, notes):
    """Apply the same decision to specific transactions by ID.

    Computes deductible_amount per transaction based on each transaction's own
    original_amount and the chosen deductible_status. Saves each unique merchant
    to merchant memory.
    """
    con = get_connection()
    try:
        placeholders = ", ".join(["?"] * len(transaction_ids))
        rows = con.execute(
            f"""
            SELECT ct.transaction_id, ct.original_amount, nt.merchant_normalized, nt.merchant_raw
            FROM categorized_transactions ct
            JOIN normalized_transactions nt ON ct.transaction_id = nt.transaction_id
            WHERE ct.transaction_id IN ({placeholders})
            """,
            transaction_ids,
        ).fetchall()

        merchants_saved = set()
        for tid, orig_amount, merchant_norm, merchant_raw in rows:
            amount = float(orig_amount) if orig_amount is not None else 0.0
            if deductible_status == "full":
                ded_amount = abs(amount)
            elif deductible_status == "personal":
                ded_amount = 0.0
            else:
                ded_amount = abs(amount)

            con.execute(
                """
                UPDATE categorized_transactions
                SET category = ?,
                    deductible_status = ?,
                    deductible_amount = ?,
                    confidence = 1.0,
                    review_required = FALSE,
                    notes = ?
                WHERE transaction_id = ?
                """,
                [category, deductible_status, ded_amount, notes or "", tid],
            )

            merchant_key = merchant_norm or merchant_raw or ""
            if merchant_key and merchant_key not in merchants_saved:
                merchants_saved.add(merchant_key)

        con.commit()
        updated = len(rows)
    finally:
        con.close()

    # Save unique merchants to memory outside DB connection
    if merchants_saved:
        memory = get_memory()
        for merchant in merchants_saved:
            memory.save_decision(
                merchant_normalized=merchant,
                category=category,
                deductible_status=deductible_status,
                confidence=1.0,
                decision_source="manual_web_batch",
            )

    return updated


def count_similar(merchant_normalized: str, queue: list) -> int:
    """Count how many other items in the queue share this merchant_normalized."""
    if not merchant_normalized:
        return 0
    return sum(
        1 for t in queue
        if t.get("merchant_normalized") == merchant_normalized
    ) - 1  # exclude the current one


def suggest_keyword(merchant_normalized: str) -> str:
    """Extract a plausible keyword from the merchant name."""
    if not merchant_normalized:
        return ""
    # Take the first meaningful word (skip very short tokens)
    clean = re.sub(r"[^a-zA-Z0-9\s\-]", " ", merchant_normalized)
    tokens = [t for t in clean.split() if len(t) >= 3]
    return tokens[0].lower() if tokens else merchant_normalized.lower().strip()[:20]
