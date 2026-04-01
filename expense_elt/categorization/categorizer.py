"""
categorizer.py - Public categorization facade.

Keeps the existing public imports and patch points stable while delegating the
heavier orchestration work to smaller categorization modules.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Dict, List, Optional

from categorization.deduction_rules import apply_deduction_rule
from categorization.merchant_memory import get_memory
from categorization.rules_engine import apply_rules
from categorization.workflow import categorize_with_llm, categorize_with_rules



def categorize_transaction(
    transaction_id: str,
    merchant_normalized: str,
    original_amount: float,
    transaction_date: Optional[date],
    deduction_rules: List[Dict[str, Any]],
    llm_result: Optional[Any] = None,
    llm_model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Categorize a single transaction and compute deductible amounts."""
    memory = get_memory()
    category = "Other expenses"
    confidence = 0.0
    deductible_status = "full"
    deductible_amount = 0.0
    rule_applied: Optional[str] = None
    review_required = True
    notes = ""

    mem_result = memory.lookup(merchant_normalized)
    if mem_result:
        category, deductible_status, confidence, decision_source = mem_result
        rule_applied = f"memory:{decision_source}"
        review_required = confidence < 0.85
    elif llm_result is not None:
        category = llm_result.category
        confidence = llm_result.confidence / 100.0
        rule_applied = f"llm:{llm_model_name or 'unknown'}"
        review_required = llm_result.review_flag or confidence < 0.70
        notes = llm_result.reasoning

        pct = llm_result.expensable_pct
        if pct == 0:
            deductible_status = "personal"
            deductible_amount = 0.0
        elif pct == 100:
            deductible_status = "full"
            deductible_amount = abs(original_amount)
        else:
            deductible_status = "partial"
            deductible_amount = abs(original_amount) * pct / 100.0
    elif merchant_normalized:
        rule_result = apply_rules(merchant_normalized)
        if rule_result:
            category, confidence, rule_applied = rule_result
            review_required = confidence < 0.70
    else:
        category = "Other expenses"
        confidence = 0.0
        review_required = True

    if original_amount < 0:
        deductible_status = "personal"
        deductible_amount = 0.0
        review_required = False
    elif llm_result is None or mem_result:
        ded_status, ded_amount, ded_rule = apply_deduction_rule(
            merchant_normalized,
            original_amount,
            transaction_date,
            deduction_rules,
        )
        deductible_status = ded_status
        deductible_amount = ded_amount
        if ded_rule:
            rule_applied = ded_rule
    else:
        ded_status, ded_amount, ded_rule = apply_deduction_rule(
            merchant_normalized,
            original_amount,
            transaction_date,
            deduction_rules,
        )
        if ded_rule:
            deductible_status = ded_status
            deductible_amount = ded_amount
            rule_applied = ded_rule

    if review_required:
        deductible_status = "needs_review"
        deductible_amount = 0.0

    return {
        "transaction_id": transaction_id,
        "category": category,
        "deductible_status": deductible_status,
        "original_amount": original_amount,
        "deductible_amount": deductible_amount,
        "confidence": round(confidence, 4),
        "review_required": review_required,
        "rule_applied": rule_applied or "",
        "notes": notes,
    }



def categorize_all(
    verbose: bool = False,
    use_llm: bool = False,
    llm_provider: str = "anthropic",
    dry_run: bool = False,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    llm_model: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Categorize normalized transactions and persist results."""
    if use_llm:
        return categorize_with_llm(
            categorize_transaction_fn=categorize_transaction,
            verbose=verbose,
            provider_name=llm_provider,
            dry_run=dry_run,
            progress_callback=progress_callback,
            llm_model=llm_model,
            llm_api_key=llm_api_key,
            force=force,
        )

    return categorize_with_rules(
        categorize_transaction_fn=categorize_transaction,
        verbose=verbose,
        force=force,
    )


__all__ = ["apply_deduction_rule", "categorize_transaction", "categorize_all"]
