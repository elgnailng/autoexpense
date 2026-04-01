from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from categorization.core import parse_transaction_date
from categorization.deduction_rules import load_deduction_rules
from categorization.merchant_memory import get_memory
from staging.database import get_connection

logger = logging.getLogger(__name__)



def insert_categorized(con: Any, result: Dict[str, Any]) -> None:
    """Insert a categorization result into the database."""
    con.execute(
        """
        INSERT OR REPLACE INTO categorized_transactions
            (transaction_id, category, deductible_status, original_amount,
             deductible_amount, confidence, review_required, rule_applied, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            result["transaction_id"],
            result["category"],
            result["deductible_status"],
            result["original_amount"],
            result["deductible_amount"],
            result["confidence"],
            result["review_required"],
            result["rule_applied"],
            result["notes"],
        ],
    )



def clear_non_reviewed(con: Any, verbose: bool = False) -> int:
    """Delete categorizations that were not sourced from merchant memory."""
    count = con.execute(
        """
        SELECT COUNT(*) FROM categorized_transactions
        WHERE rule_applied NOT LIKE 'memory:%'
          AND review_required = TRUE
           OR (rule_applied LIKE 'llm:%' OR rule_applied LIKE 'keyword:%' OR rule_applied = ''
               OR rule_applied IS NULL)
        """
    ).fetchone()[0]

    con.execute(
        """
        DELETE FROM categorized_transactions
        WHERE rule_applied NOT LIKE 'memory:%'
        """
    )
    con.commit()

    if verbose:
        logger.info("Recategorize: cleared %d non-memory categorizations", count)
    return count



def categorize_with_llm(
    categorize_transaction_fn: Callable[..., Dict[str, Any]],
    verbose: bool = False,
    provider_name: str = "anthropic",
    dry_run: bool = False,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    llm_model: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    from llm.config import load_llm_config
    from llm.evaluator import LLMEvaluator
    from llm.providers import get_provider

    logger.info(
        "LLM categorization starting (provider=%s, dry_run=%s, force=%s)",
        provider_name,
        dry_run,
        force,
    )

    deduction_rules = load_deduction_rules()
    config = load_llm_config()
    if provider_name:
        config.provider = provider_name
    if llm_model:
        config.model = llm_model

    con = get_connection()

    cleared = 0
    if force and not dry_run:
        cleared = clear_non_reviewed(con, verbose=verbose)

    stats: Dict[str, Any] = {
        "total_normalized": 0,
        "categorized": 0,
        "skipped": 0,
        "cleared": cleared,
        "review_required": 0,
        "errors": 0,
        "error_messages": [],
        "memory_matched": 0,
        "llm_evaluated": 0,
        "total_cost_usd": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "model": "",
    }

    try:
        rows = con.execute(
            """
            SELECT transaction_id, merchant_normalized, original_amount,
                   transaction_date, institution
            FROM normalized_transactions
            """
        ).fetchall()

        stats["total_normalized"] = len(rows)

        memory = get_memory()
        llm_candidates = []

        for transaction_id, merchant_normalized, original_amount, txn_date_str, institution in rows:
            existing = con.execute(
                "SELECT transaction_id FROM categorized_transactions WHERE transaction_id = ?",
                [transaction_id],
            ).fetchone()
            if existing:
                stats["skipped"] += 1
                continue

            txn_date = parse_transaction_date(txn_date_str)
            amount = float(original_amount) if original_amount is not None else 0.0
            merchant = merchant_normalized or ""

            mem = memory.lookup(merchant)
            if mem:
                result = categorize_transaction_fn(
                    transaction_id=transaction_id,
                    merchant_normalized=merchant,
                    original_amount=amount,
                    transaction_date=txn_date,
                    deduction_rules=deduction_rules,
                )
                insert_categorized(con, result)
                stats["categorized"] += 1
                stats["memory_matched"] += 1
                if result["review_required"]:
                    stats["review_required"] += 1
                if verbose:
                    print(
                        f"  [memory] {merchant[:40]:<40} | {result['category']:<35} "
                        f"| conf={result['confidence']:.2f}"
                    )
                continue

            llm_candidates.append(
                {
                    "transaction_id": transaction_id,
                    "transaction_date": str(txn_date) if txn_date else "unknown",
                    "merchant_normalized": merchant,
                    "original_amount": amount,
                    "institution": institution or "unknown",
                    "_txn_date": txn_date,
                }
            )

        con.commit()

        logger.info(
            "Memory phase complete: %d matched, %d skipped, %d candidates for LLM",
            stats["memory_matched"],
            stats["skipped"],
            len(llm_candidates),
        )

        total_batches = (len(llm_candidates) + config.batch_size - 1) // config.batch_size if llm_candidates else 0
        if progress_callback:
            progress_callback(
                {
                    "type": "start",
                    "memory_matched": stats["memory_matched"],
                    "llm_candidates": len(llm_candidates),
                    "total_batches": total_batches,
                    "model": config.model,
                }
            )

        if dry_run:
            estimated_batches = (len(llm_candidates) + config.batch_size - 1) // config.batch_size if llm_candidates else 0
            stats["dry_run"] = True
            stats["llm_candidates"] = len(llm_candidates)
            stats["estimated_batches"] = estimated_batches
            stats["model"] = config.model
            return stats

        if not llm_candidates:
            return stats

        provider_kwargs: Dict[str, Any] = {"model": config.model}
        if llm_api_key:
            provider_kwargs["api_key"] = llm_api_key
        provider = get_provider(config.provider, **provider_kwargs)
        evaluator = LLMEvaluator(provider=provider, config=config)
        model_name = provider.get_model_name()
        stats["model"] = model_name

        batch_counter = [0]

        def persist_batch(batch_evaluations: list[Any], batch_transactions: list[dict[str, Any]]) -> None:
            eval_by_index = {evaluation.index: evaluation for evaluation in batch_evaluations}
            for transaction in batch_transactions:
                evaluation = eval_by_index.get(transaction["index"])
                if evaluation is None:
                    stats["errors"] += 1
                    continue

                result = categorize_transaction_fn(
                    transaction_id=transaction["transaction_id"],
                    merchant_normalized=transaction["merchant_normalized"],
                    original_amount=transaction["original_amount"],
                    transaction_date=transaction["_txn_date"],
                    deduction_rules=deduction_rules,
                    llm_result=evaluation,
                    llm_model_name=model_name,
                )
                insert_categorized(con, result)
                stats["categorized"] += 1
                if result["review_required"]:
                    stats["review_required"] += 1

                if verbose:
                    print(
                        f"  [llm] {transaction['merchant_normalized'][:40]:<40} | "
                        f"{result['category']:<35} | conf={result['confidence']:.2f} | "
                        f"review={result['review_required']}"
                    )

            con.commit()

            batch_counter[0] += 1
            if progress_callback:
                progress_callback(
                    {
                        "type": "progress",
                        "batch_number": batch_counter[0],
                        "total_batches": total_batches,
                        "cumulative_categorized": stats["categorized"],
                        "cumulative_cost_usd": evaluator._total_cost_usd,
                        "cumulative_input_tokens": evaluator._total_input_tokens,
                        "cumulative_output_tokens": evaluator._total_output_tokens,
                    }
                )

        llm_stats = evaluator.evaluate_all(
            llm_candidates,
            verbose=verbose,
            per_batch_callback=persist_batch,
        )

        stats["total_cost_usd"] = llm_stats.get("total_cost_usd", 0.0)
        stats["total_input_tokens"] = llm_stats.get("total_input_tokens", 0)
        stats["total_output_tokens"] = llm_stats.get("total_output_tokens", 0)
        stats["llm_evaluated"] = llm_stats.get("evaluated", 0)
        stats["errors"] += llm_stats.get("errors", 0)
        stats["error_messages"].extend(llm_stats.get("error_messages", []))
    except Exception:
        logger.error("LLM categorization failed", exc_info=True)
        raise
    finally:
        con.close()

    logger.info(
        "LLM categorization complete: %d categorized, %d review, %d errors, cost=$%.4f",
        stats["categorized"],
        stats["review_required"],
        stats["errors"],
        stats.get("total_cost_usd", 0),
    )
    return stats



def categorize_with_rules(
    categorize_transaction_fn: Callable[..., Dict[str, Any]],
    verbose: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    deduction_rules = load_deduction_rules()
    con = get_connection()

    cleared = 0
    if force:
        cleared = clear_non_reviewed(con, verbose=verbose)

    stats: Dict[str, Any] = {
        "total_normalized": 0,
        "categorized": 0,
        "skipped": 0,
        "cleared": cleared,
        "review_required": 0,
        "errors": 0,
    }

    try:
        rows = con.execute(
            """
            SELECT transaction_id, merchant_normalized, original_amount, transaction_date
            FROM normalized_transactions
            """
        ).fetchall()

        stats["total_normalized"] = len(rows)

        for transaction_id, merchant_normalized, original_amount, txn_date_str in rows:
            try:
                existing = con.execute(
                    "SELECT transaction_id FROM categorized_transactions WHERE transaction_id = ?",
                    [transaction_id],
                ).fetchone()
                if existing:
                    stats["skipped"] += 1
                    continue

                txn_date = parse_transaction_date(txn_date_str)
                amount = float(original_amount) if original_amount is not None else 0.0

                result = categorize_transaction_fn(
                    transaction_id=transaction_id,
                    merchant_normalized=merchant_normalized or "",
                    original_amount=amount,
                    transaction_date=txn_date,
                    deduction_rules=deduction_rules,
                )

                insert_categorized(con, result)

                stats["categorized"] += 1
                if result["review_required"]:
                    stats["review_required"] += 1

                if verbose:
                    print(
                        f"  {merchant_normalized[:40]:<40} | {result['category']:<35} "
                        f"| conf={result['confidence']:.2f} | review={result['review_required']}"
                    )
            except Exception as exc:
                stats["errors"] += 1
                if verbose:
                    print(f"  [ERROR] {transaction_id}: {exc}")

        con.commit()
    finally:
        con.close()

    return stats
