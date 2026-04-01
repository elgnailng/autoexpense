"""Batch LLM evaluator with retry, cost tracking, and hot-reload."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

import yaml

from llm.config import LLMConfig
from llm.providers.base import LLMProvider, LLMResponse
from llm.schemas import TransactionEvaluation
from llm.prompts.system_prompt import build_system_prompt
from llm.prompts.transaction_prompt import build_transaction_prompt

_CONFIG_DIR = Path(__file__).parent.parent / "config"
_CATEGORIES_FILE = _CONFIG_DIR / "categories.yaml"
_RULES_FILE = _CONFIG_DIR / "rules.yaml"
_DEDUCTION_RULES_FILE = _CONFIG_DIR / "deduction_rules.yaml"


class LLMEvaluator:
    """Orchestrates LLM evaluation of transactions in batches."""

    def __init__(self, provider: LLMProvider, config: LLMConfig):
        self._provider = provider
        self._config = config
        self._categories = self._load_categories()
        self._rules_context = self._build_rules_context()
        self._deduction_context = self._build_deduction_context()
        self._rules_mtime = self._get_mtime(_RULES_FILE)
        self._deduction_mtime = self._get_mtime(_DEDUCTION_RULES_FILE)

        # Cumulative stats
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost_usd = 0.0

    # ------------------------------------------------------------------
    # Config loaders
    # ------------------------------------------------------------------

    @staticmethod
    def _load_categories() -> List[str]:
        if not _CATEGORIES_FILE.exists():
            return ["Other expenses"]
        with open(_CATEGORIES_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("categories", []) if data else ["Other expenses"]

    @staticmethod
    def _build_rules_context() -> str:
        if not _RULES_FILE.exists():
            return ""
        with open(_RULES_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        rules = data.get("rules", []) if data else []
        lines = []
        for r in rules:
            kws = ", ".join(r.get("keywords", []))
            cat = r.get("category", "?")
            lines.append(f"  Keywords [{kws}] -> {cat}")
        return "\n".join(lines)

    @staticmethod
    def _build_deduction_context() -> str:
        if not _DEDUCTION_RULES_FILE.exists():
            return ""
        with open(_DEDUCTION_RULES_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        rules = data.get("deduction_rules", []) if data else []
        lines = []
        for r in rules:
            name = r.get("name", "?")
            method = r.get("method", "?")
            lines.append(f"  {name}: {method}")
        return "\n".join(lines)

    @staticmethod
    def _get_mtime(path: Path) -> float:
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0.0

    def _check_hot_reload(self) -> None:
        """Reload rules/deduction context if files changed on disk."""
        new_rules_mt = self._get_mtime(_RULES_FILE)
        new_ded_mt = self._get_mtime(_DEDUCTION_RULES_FILE)

        if new_rules_mt != self._rules_mtime:
            self._rules_context = self._build_rules_context()
            self._rules_mtime = new_rules_mt

        if new_ded_mt != self._deduction_mtime:
            self._deduction_context = self._build_deduction_context()
            self._deduction_mtime = new_ded_mt

    # ------------------------------------------------------------------
    # Cost tracking
    # ------------------------------------------------------------------

    def _compute_cost(self, response: LLMResponse) -> float:
        input_cost = (response.input_tokens / 1000) * self._provider.get_cost_per_1k_input_tokens()
        output_cost = (response.output_tokens / 1000) * self._provider.get_cost_per_1k_output_tokens()
        return input_cost + output_cost

    # ------------------------------------------------------------------
    # Batch evaluation
    # ------------------------------------------------------------------

    def evaluate_batch(
        self, transactions: List[Dict]
    ) -> List[TransactionEvaluation]:
        """
        Evaluate a single batch of transactions via the LLM.

        Retries on rate limit / timeout with exponential backoff.
        Validates categories against categories.yaml.
        """
        system_prompt = build_system_prompt(
            categories=self._categories,
            keyword_rules_context=self._rules_context or None,
            deduction_rules_context=self._deduction_context or None,
        )
        user_prompt = build_transaction_prompt(transactions)

        response: Optional[LLMResponse] = None
        last_error: Optional[Exception] = None
        backoff = self._config.initial_backoff_seconds

        for attempt in range(self._config.max_retries):
            try:
                response = self._provider.evaluate_transactions(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self._config.temperature,
                )
                break
            except Exception as exc:
                last_error = exc
                exc_name = type(exc).__name__
                if "ratelimit" in exc_name.lower() or "timeout" in exc_name.lower() or "rate_limit" in exc_name.lower():
                    logger.warning(
                        "LLM rate limit/timeout (attempt %d/%d): %s",
                        attempt + 1, self._config.max_retries, exc,
                    )
                    if attempt < self._config.max_retries - 1:
                        time.sleep(backoff)
                        backoff *= 2
                        continue
                logger.error("LLM API error (attempt %d/%d): %s", attempt + 1, self._config.max_retries, exc)
                raise

        if response is None:
            logger.error("LLM evaluation failed after %d retries: %s", self._config.max_retries, last_error)
            raise last_error or RuntimeError("LLM evaluation failed with no response")

        # Track tokens/cost
        cost = self._compute_cost(response)
        self._total_input_tokens += response.input_tokens
        self._total_output_tokens += response.output_tokens
        self._total_cost_usd += cost

        logger.debug(
            "Batch complete: %d tokens in, %d tokens out, cost=$%.4f",
            response.input_tokens, response.output_tokens, cost,
        )

        # Parse and validate evaluations
        evaluations: List[TransactionEvaluation] = []
        category_set = set(self._categories)

        for raw in response.parsed_evaluations:
            try:
                ev = TransactionEvaluation(**raw)
            except Exception as exc:
                logger.warning("Failed to parse LLM evaluation: %s — raw=%s", exc, raw)
                continue

            # Validate category
            if ev.category not in category_set:
                logger.warning(
                    "Invalid category '%s' from LLM for index %d, correcting to 'Other expenses'",
                    ev.category, ev.index,
                )
                ev.category = "Other expenses"
                ev.review_flag = True
                ev.confidence = min(ev.confidence, 30)
                ev.reasoning += " [category corrected to 'Other expenses' — original was invalid]"

            evaluations.append(ev)

        return evaluations

    def _retry_missing(
        self, batch: List[Dict], evaluations: List[TransactionEvaluation]
    ) -> List[TransactionEvaluation]:
        """
        Retry evaluation for transactions missing from a partial batch result.

        When the LLM returns fewer evaluations than transactions sent,
        re-evaluate the missing ones individually (batch_size=1).
        """
        got_indices = {ev.index for ev in evaluations}
        missing = [txn for txn in batch if txn["index"] not in got_indices]

        if not missing:
            return evaluations

        logger.warning(
            "Batch returned %d/%d evaluations — retrying %d missing individually",
            len(evaluations), len(batch), len(missing),
        )

        for txn in missing:
            try:
                single_result = self.evaluate_batch([txn])
                evaluations.extend(single_result)
            except Exception as exc:
                logger.error(
                    "Individual retry failed for index %d (%s): %s",
                    txn["index"], txn.get("merchant_normalized", "?"), exc,
                )

        return evaluations

    # ------------------------------------------------------------------
    # Full run
    # ------------------------------------------------------------------

    def evaluate_all(
        self,
        transactions: List[Dict],
        verbose: bool = False,
        per_batch_callback: Optional[Callable[[List[TransactionEvaluation], List[Dict]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate all transactions in batches.

        Args:
            transactions: List of transaction dicts to evaluate.
            verbose: Print progress to stdout.
            per_batch_callback: If provided, called after each successful batch
                with (batch_evaluations, batch_transactions). Use this to persist
                results incrementally (e.g. DB insert + commit per batch).

        Returns stats dict with evaluated, review_required, errors,
        total_cost_usd, total_input_tokens, total_output_tokens.
        """
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost_usd = 0.0

        total_batches = (len(transactions) + self._config.batch_size - 1) // self._config.batch_size
        logger.info(
            "LLM evaluate_all starting: %d transactions, %d batches, model=%s, max_cost=$%.2f",
            len(transactions), total_batches, self._provider.get_model_name(), self._config.max_cost_per_run,
        )

        results: List[TransactionEvaluation] = []
        errors = 0
        error_messages: List[str] = []
        batch_size = self._config.batch_size

        # Assign indices
        for i, txn in enumerate(transactions):
            txn["index"] = i

        batch_num = 0
        # Process in batches
        for batch_start in range(0, len(transactions), batch_size):
            batch = transactions[batch_start : batch_start + batch_size]
            batch_num += 1

            # Hot-reload rules if files changed
            self._check_hot_reload()

            # Cost guard
            if self._total_cost_usd >= self._config.max_cost_per_run:
                logger.warning(
                    "Cost limit reached: $%.4f >= $%.2f — stopping after batch %d/%d",
                    self._total_cost_usd, self._config.max_cost_per_run, batch_num - 1, total_batches,
                )
                if verbose:
                    print(
                        f"  [COST LIMIT] Stopping at ${self._total_cost_usd:.4f} "
                        f"(limit: ${self._config.max_cost_per_run:.2f})"
                    )
                break

            try:
                batch_results = self.evaluate_batch(batch)

                # Retry missing evaluations individually if batch returned partial results
                if len(batch_results) < len(batch):
                    batch_results = self._retry_missing(batch, batch_results)

                results.extend(batch_results)

                flagged = sum(1 for r in batch_results if r.review_flag)
                logger.info(
                    "Batch %d/%d: %d evaluated, %d flagged, cost=$%.4f",
                    batch_num, total_batches, len(batch_results), flagged, self._total_cost_usd,
                )

                if verbose:
                    batch_end = min(batch_start + batch_size, len(transactions))
                    print(
                        f"  Batch [{batch_start+1}-{batch_end}]: "
                        f"{len(batch_results)} evaluated, {flagged} flagged, "
                        f"cost so far: ${self._total_cost_usd:.4f}"
                    )

                if per_batch_callback is not None:
                    per_batch_callback(batch_results, batch)

            except Exception as exc:
                errors += len(batch)
                error_msg = f"Batch {batch_start+1}-{min(batch_start+batch_size, len(transactions))}: {exc}"
                error_messages.append(error_msg)
                logger.error("LLM batch %d/%d failed: %s", batch_num, total_batches, exc, exc_info=True)
                if verbose:
                    print(f"  [ERROR] Batch starting at {batch_start}: {exc}")

        review_required = sum(1 for r in results if r.review_flag)

        logger.info(
            "LLM evaluate_all complete: %d evaluated, %d review, %d errors, cost=$%.4f, tokens=%d/%d",
            len(results), review_required, errors, self._total_cost_usd,
            self._total_input_tokens, self._total_output_tokens,
        )

        return {
            "evaluated": len(results),
            "review_required": review_required,
            "errors": errors,
            "error_messages": error_messages,
            "total_cost_usd": round(self._total_cost_usd, 4),
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "model": self._provider.get_model_name(),
            "evaluations": results,
        }
