"""Tests for prompt construction."""

from llm.prompts.system_prompt import build_system_prompt
from llm.prompts.transaction_prompt import build_transaction_prompt


class TestSystemPrompt:
    def test_includes_all_categories(self, sample_categories):
        prompt = build_system_prompt(categories=sample_categories)
        for cat in sample_categories:
            assert cat in prompt, f"Category '{cat}' missing from system prompt"

    def test_includes_keyword_rules_context(self, sample_categories):
        rules_ctx = "Keywords [aws, amazon web services] -> Office expenses"
        prompt = build_system_prompt(
            categories=sample_categories,
            keyword_rules_context=rules_ctx,
        )
        assert "aws, amazon web services" in prompt
        assert "EXISTING KEYWORD RULES" in prompt

    def test_includes_deduction_rules_context(self, sample_categories):
        ded_ctx = "Personal streaming services: percentage"
        prompt = build_system_prompt(
            categories=sample_categories,
            deduction_rules_context=ded_ctx,
        )
        assert "Personal streaming services" in prompt
        assert "EXISTING DEDUCTION RULES" in prompt

    def test_includes_anti_hallucination_rules(self, sample_categories):
        prompt = build_system_prompt(categories=sample_categories)
        assert "NEVER fabricate or guess" in prompt
        assert "review_flag=true" in prompt
        assert "Unrecognized merchant" in prompt

    def test_no_context_sections_when_none(self, sample_categories):
        prompt = build_system_prompt(categories=sample_categories)
        assert "EXISTING KEYWORD RULES" not in prompt
        assert "EXISTING DEDUCTION RULES" not in prompt

    def test_requests_json_output(self, sample_categories):
        prompt = build_system_prompt(categories=sample_categories)
        assert "JSON object" in prompt
        assert "index" in prompt
        assert "expensable_pct" in prompt
        assert "review_flag" in prompt


class TestTransactionPrompt:
    def test_formats_transactions_with_indices(self, sample_transactions):
        for i, t in enumerate(sample_transactions):
            t["index"] = i

        prompt = build_transaction_prompt(sample_transactions)
        assert "[0]" in prompt
        assert "[1]" in prompt
        assert "[2]" in prompt
        assert "AMAZON WEB SERVICES" in prompt
        assert "STARBUCKS COFFEE" in prompt

    def test_handles_negative_amounts(self):
        txns = [{
            "index": 0,
            "transaction_date": "2025-01-01",
            "merchant_normalized": "REFUND CO",
            "original_amount": -50.00,
            "institution": "RBC_VISA",
        }]
        prompt = build_transaction_prompt(txns)
        assert "credit/refund" in prompt
        assert "$50.00" in prompt

    def test_handles_empty_merchant(self):
        txns = [{
            "index": 0,
            "transaction_date": "2025-01-01",
            "merchant_normalized": "",
            "original_amount": 25.00,
            "institution": "BMO",
        }]
        prompt = build_transaction_prompt(txns)
        assert 'merchant=""' in prompt

    def test_handles_special_characters(self):
        txns = [{
            "index": 0,
            "transaction_date": "2025-01-01",
            "merchant_normalized": 'TIM HORTON\'S #1234 "MAIN"',
            "original_amount": 5.00,
            "institution": "RBC_VISA",
        }]
        prompt = build_transaction_prompt(txns)
        assert "TIM HORTON" in prompt

    def test_single_transaction(self):
        txns = [{
            "index": 0,
            "transaction_date": "2025-06-15",
            "merchant_normalized": "GITHUB",
            "original_amount": 4.00,
            "institution": "RBC_VISA",
        }]
        prompt = build_transaction_prompt(txns)
        assert "[0]" in prompt
        assert "GITHUB" in prompt
        assert "JSON object" in prompt
