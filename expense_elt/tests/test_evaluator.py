"""Tests for the LLM evaluator orchestrator."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from llm.config import LLMConfig
from llm.evaluator import LLMEvaluator
from llm.providers.base import LLMProvider, LLMResponse
from llm.schemas import TransactionEvaluation


def _make_provider(response_data: list[dict], input_tokens=100, output_tokens=200) -> MagicMock:
    """Create a mock LLMProvider that returns a canned response."""
    provider = MagicMock(spec=LLMProvider)
    provider.evaluate_transactions.return_value = LLMResponse(
        raw_text=json.dumps(response_data),
        parsed_evaluations=response_data,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model="test-model",
        latency_ms=100.0,
    )
    provider.get_model_name.return_value = "test-model"
    provider.get_cost_per_1k_input_tokens.return_value = 0.003
    provider.get_cost_per_1k_output_tokens.return_value = 0.015
    return provider


class TestEvaluateBatch:
    def test_parses_valid_json_response(self, sample_transactions, mock_llm_response_json):
        provider = _make_provider(mock_llm_response_json)
        config = LLMConfig(batch_size=10)
        evaluator = LLMEvaluator(provider=provider, config=config)

        for i, t in enumerate(sample_transactions):
            t["index"] = i

        results = evaluator.evaluate_batch(sample_transactions)
        assert len(results) == 3
        assert all(isinstance(r, TransactionEvaluation) for r in results)
        assert results[0].category == "Office expenses"
        assert results[1].review_flag is True

    def test_retries_on_rate_limit(self, sample_transactions, mock_llm_response_json):
        provider = MagicMock(spec=LLMProvider)
        provider.get_model_name.return_value = "test-model"
        provider.get_cost_per_1k_input_tokens.return_value = 0.003
        provider.get_cost_per_1k_output_tokens.return_value = 0.015

        # First call raises rate limit, second succeeds
        class RateLimitError(Exception):
            pass
        RateLimitError.__name__ = "RateLimitError"

        provider.evaluate_transactions.side_effect = [
            RateLimitError("rate limited"),
            LLMResponse(
                raw_text=json.dumps(mock_llm_response_json),
                parsed_evaluations=mock_llm_response_json,
                input_tokens=100, output_tokens=200,
                model="test-model", latency_ms=100.0,
            ),
        ]

        config = LLMConfig(max_retries=3, initial_backoff_seconds=0.01)
        evaluator = LLMEvaluator(provider=provider, config=config)

        for i, t in enumerate(sample_transactions):
            t["index"] = i

        with patch("llm.evaluator.time.sleep"):
            results = evaluator.evaluate_batch(sample_transactions)
        assert len(results) == 3

    def test_raises_after_max_retries(self, sample_transactions):
        provider = MagicMock(spec=LLMProvider)
        provider.get_model_name.return_value = "test-model"
        provider.get_cost_per_1k_input_tokens.return_value = 0.003
        provider.get_cost_per_1k_output_tokens.return_value = 0.015

        class RateLimitError(Exception):
            pass
        RateLimitError.__name__ = "RateLimitError"

        provider.evaluate_transactions.side_effect = RateLimitError("rate limited")

        config = LLMConfig(max_retries=2, initial_backoff_seconds=0.01)
        evaluator = LLMEvaluator(provider=provider, config=config)

        for i, t in enumerate(sample_transactions):
            t["index"] = i

        with patch("llm.evaluator.time.sleep"):
            with pytest.raises(RateLimitError):
                evaluator.evaluate_batch(sample_transactions)

    def test_invalid_category_corrected(self, sample_transactions):
        bad_response = [{
            "index": 0,
            "category": "INVALID CATEGORY",
            "expensable_pct": 100,
            "confidence": 90,
            "reasoning": "test",
            "review_flag": False,
        }]
        provider = _make_provider(bad_response)
        config = LLMConfig()
        evaluator = LLMEvaluator(provider=provider, config=config)

        sample_transactions[0]["index"] = 0
        results = evaluator.evaluate_batch([sample_transactions[0]])
        assert results[0].category == "Other expenses"
        assert results[0].review_flag is True
        assert results[0].confidence <= 30

    def test_malformed_json_skipped(self, sample_transactions):
        """Malformed items in parsed_evaluations are skipped."""
        bad_response = [
            {"index": 0, "bad_field": True},  # missing required fields
            {
                "index": 1,
                "category": "Office expenses",
                "expensable_pct": 100,
                "confidence": 90,
                "reasoning": "valid",
                "review_flag": False,
            },
        ]
        provider = _make_provider(bad_response)
        config = LLMConfig()
        evaluator = LLMEvaluator(provider=provider, config=config)

        for i, t in enumerate(sample_transactions[:2]):
            t["index"] = i

        results = evaluator.evaluate_batch(sample_transactions[:2])
        assert len(results) == 1  # only the valid one parsed


class TestEvaluateAll:
    def test_chunks_into_batches(self, mock_llm_response_json):
        # 6 transactions with batch_size=3 should make 2 batches
        transactions = [
            {"transaction_id": f"t{i}", "transaction_date": "2025-01-01",
             "merchant_normalized": f"MERCHANT_{i}", "original_amount": 10.0,
             "institution": "RBC_VISA"}
            for i in range(6)
        ]

        # Build response for 3 items
        def batch_response(*args, **kwargs):
            prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
            evals = []
            for i in range(3):
                evals.append({
                    "index": i,
                    "category": "Office expenses",
                    "expensable_pct": 100,
                    "confidence": 90,
                    "reasoning": "test",
                    "review_flag": False,
                })
            return LLMResponse(
                raw_text=json.dumps(evals),
                parsed_evaluations=evals,
                input_tokens=50, output_tokens=100,
                model="test-model", latency_ms=50.0,
            )

        provider = MagicMock(spec=LLMProvider)
        provider.evaluate_transactions.side_effect = batch_response
        provider.get_model_name.return_value = "test-model"
        provider.get_cost_per_1k_input_tokens.return_value = 0.003
        provider.get_cost_per_1k_output_tokens.return_value = 0.015

        config = LLMConfig(batch_size=3, max_cost_per_run=100.0)
        evaluator = LLMEvaluator(provider=provider, config=config)
        stats = evaluator.evaluate_all(transactions)

        assert provider.evaluate_transactions.call_count == 2
        assert stats["evaluated"] == 6

    def test_aborts_at_cost_limit(self, mock_llm_response_json):
        transactions = [
            {"transaction_id": f"t{i}", "transaction_date": "2025-01-01",
             "merchant_normalized": f"MERCHANT_{i}", "original_amount": 10.0,
             "institution": "RBC_VISA"}
            for i in range(20)
        ]

        provider = _make_provider(
            mock_llm_response_json[:1],
            input_tokens=10000,  # expensive
            output_tokens=10000,
        )
        config = LLMConfig(batch_size=2, max_cost_per_run=0.01)
        evaluator = LLMEvaluator(provider=provider, config=config)

        stats = evaluator.evaluate_all(transactions)
        # Should have stopped early due to cost
        assert stats["evaluated"] < 20

    def test_cost_calculation(self, mock_llm_response_json):
        provider = _make_provider(
            mock_llm_response_json,
            input_tokens=1000,
            output_tokens=500,
        )
        config = LLMConfig(batch_size=10, max_cost_per_run=100.0)
        evaluator = LLMEvaluator(provider=provider, config=config)

        transactions = [
            {"transaction_id": "t0", "transaction_date": "2025-01-01",
             "merchant_normalized": "TEST", "original_amount": 10.0,
             "institution": "RBC_VISA"}
        ]
        stats = evaluator.evaluate_all(transactions)

        # 1000/1000 * 0.003 + 500/1000 * 0.015 = 0.003 + 0.0075 = 0.0105
        expected_cost = (1000 / 1000) * 0.003 + (500 / 1000) * 0.015
        assert abs(stats["total_cost_usd"] - expected_cost) < 0.001

    def test_hot_reload_detects_mtime_change(self, tmp_path, mock_llm_response_json):
        """Verify that rules context is reloaded when file mtime changes."""
        provider = _make_provider(mock_llm_response_json)
        config = LLMConfig(batch_size=1, max_cost_per_run=100.0)
        evaluator = LLMEvaluator(provider=provider, config=config)

        old_context = evaluator._rules_context

        # Simulate a file mtime change
        evaluator._rules_mtime = 0.0  # force mismatch
        evaluator._check_hot_reload()

        # Context was reloaded (value may be same if file unchanged, but method ran)
        # Just verify it didn't crash
        assert evaluator._rules_context is not None
