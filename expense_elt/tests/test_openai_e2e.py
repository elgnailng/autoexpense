"""End-to-end test with real OpenAI API — skipped if OPENAI_API_KEY is not set."""

import os
import sys
from pathlib import Path

import pytest

# Ensure expense_elt is on path
_HERE = Path(__file__).parent.parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from llm.config import load_llm_config

_cfg = load_llm_config()

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping real API test",
)

# Use model from llm_config.yaml when provider is openai, else fallback
_MODEL = _cfg.model if _cfg.provider == "openai" else "gpt-4o-mini"


SAMPLE_TRANSACTIONS = [
    {
        "index": 0,
        "transaction_id": "test-001",
        "transaction_date": "2025-01-15",
        "merchant_normalized": "STARBUCKS #1234",
        "original_amount": 6.50,
        "institution": "RBC_VISA",
    },
    {
        "index": 1,
        "transaction_id": "test-002",
        "transaction_date": "2025-02-10",
        "merchant_normalized": "ADOBE CREATIVE CLOUD",
        "original_amount": 79.99,
        "institution": "BMO",
    },
]


class TestOpenAIE2E:
    def test_evaluate_batch_returns_valid_results(self):
        from llm.config import LLMConfig
        from llm.providers import get_provider
        from llm.evaluator import LLMEvaluator

        config = LLMConfig(
            provider="openai",
            model=_MODEL,
            batch_size=10,
            max_retries=2,
            max_cost_per_run=1.00,
            temperature=0.1,
        )
        provider = get_provider("openai", model=_MODEL)
        evaluator = LLMEvaluator(provider=provider, config=config)

        results = evaluator.evaluate_batch(SAMPLE_TRANSACTIONS)

        assert len(results) >= 1, "Expected at least 1 evaluation result"

        for ev in results:
            assert ev.category, "category should be non-empty"
            assert 0 <= ev.confidence <= 100, f"confidence {ev.confidence} out of range"
            assert 0 <= ev.expensable_pct <= 100, f"expensable_pct {ev.expensable_pct} out of range"
            assert isinstance(ev.reasoning, str)
            assert isinstance(ev.review_flag, bool)

    def test_cost_tracking(self):
        from llm.config import LLMConfig
        from llm.providers import get_provider
        from llm.evaluator import LLMEvaluator

        config = LLMConfig(
            provider="openai",
            model=_MODEL,
            batch_size=10,
            max_retries=2,
            max_cost_per_run=1.00,
            temperature=0.1,
        )
        provider = get_provider("openai", model=_MODEL)
        evaluator = LLMEvaluator(provider=provider, config=config)

        evaluator.evaluate_batch(SAMPLE_TRANSACTIONS)

        assert evaluator._total_input_tokens > 0
        assert evaluator._total_output_tokens > 0
        assert evaluator._total_cost_usd > 0
