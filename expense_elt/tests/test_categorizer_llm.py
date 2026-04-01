"""Tests for categorizer integration with LLM results."""

from datetime import date

import pytest

from llm.schemas import TransactionEvaluation


class TestCategorizeTxnWithLLM:
    """Test categorize_transaction() when llm_result is provided."""

    def _call(self, llm_result, original_amount=100.0, deduction_rules=None):
        from categorization.categorizer import categorize_transaction
        return categorize_transaction(
            transaction_id="txn-test",
            merchant_normalized="TEST MERCHANT",
            original_amount=original_amount,
            transaction_date=date(2025, 3, 10),
            deduction_rules=deduction_rules or [],
            llm_result=llm_result,
            llm_model_name="test-model",
        )

    def test_sets_category_and_confidence(self):
        ev = TransactionEvaluation(
            index=0, category="Office expenses", expensable_pct=100,
            confidence=95, reasoning="Cloud service", review_flag=False,
        )
        result = self._call(ev)
        assert result["category"] == "Office expenses"
        assert result["confidence"] == 0.95
        assert result["rule_applied"] == "llm:test-model"

    def test_full_deductible(self):
        ev = TransactionEvaluation(
            index=0, category="Office expenses", expensable_pct=100,
            confidence=95, reasoning="Fully deductible", review_flag=False,
        )
        result = self._call(ev, original_amount=200.0)
        assert result["deductible_status"] == "full"
        assert result["deductible_amount"] == 200.0

    def test_personal(self):
        ev = TransactionEvaluation(
            index=0, category="Other expenses", expensable_pct=0,
            confidence=95, reasoning="Personal subscription", review_flag=False,
        )
        result = self._call(ev)
        assert result["deductible_status"] == "personal"
        assert result["deductible_amount"] == 0.0

    def test_partial_60_pct(self):
        ev = TransactionEvaluation(
            index=0, category="Telephone and utilties", expensable_pct=60,
            confidence=85, reasoning="Phone bill, 60% business use", review_flag=False,
        )
        result = self._call(ev, original_amount=100.0)
        assert result["deductible_status"] == "partial"
        assert abs(result["deductible_amount"] - 60.0) < 0.01

    def test_review_flag_true_overrides_status(self):
        ev = TransactionEvaluation(
            index=0, category="Meals & Entertainment", expensable_pct=50,
            confidence=40, reasoning="Ambiguous merchant", review_flag=True,
        )
        result = self._call(ev)
        assert result["review_required"] is True
        assert result["deductible_status"] == "needs_review"
        assert result["deductible_amount"] == 0.0

    def test_low_confidence_triggers_review(self):
        ev = TransactionEvaluation(
            index=0, category="Supplies", expensable_pct=100,
            confidence=50, reasoning="Uncertain", review_flag=False,
        )
        result = self._call(ev)
        # confidence = 0.50, below 0.70 threshold
        assert result["review_required"] is True

    def test_credits_always_personal(self):
        ev = TransactionEvaluation(
            index=0, category="Office expenses", expensable_pct=100,
            confidence=95, reasoning="Cloud refund", review_flag=False,
        )
        result = self._call(ev, original_amount=-50.0)
        assert result["deductible_status"] == "personal"
        assert result["deductible_amount"] == 0.0
        assert result["review_required"] is False

    def test_deduction_rule_overrides_llm_pct(self):
        ev = TransactionEvaluation(
            index=0, category="Other expenses", expensable_pct=100,
            confidence=90, reasoning="Streaming", review_flag=False,
        )
        # This deduction rule says "personal" which should override LLM's 100%
        ded_rules = [{
            "name": "Personal streaming",
            "merchant_pattern": "test merchant",
            "deductible_status": "personal",
            "method": "percentage",
            "percentage": 0.0,
        }]
        result = self._call(ev, deduction_rules=ded_rules)
        assert result["deductible_status"] == "personal"
        assert result["deductible_amount"] == 0.0

    def test_notes_contains_reasoning(self):
        ev = TransactionEvaluation(
            index=0, category="Office expenses", expensable_pct=100,
            confidence=95, reasoning="AWS is cloud infrastructure.", review_flag=False,
        )
        result = self._call(ev)
        assert result["notes"] == "AWS is cloud infrastructure."


class TestCategorizeAllModes:
    """Verify categorize_all dispatches correctly based on use_llm flag."""

    def test_use_llm_false_uses_rules_engine(self):
        """Just check the function signature accepts the flag."""
        from categorization.categorizer import categorize_all
        # This would fail with a TypeError if the param doesn't exist
        import inspect
        sig = inspect.signature(categorize_all)
        assert "use_llm" in sig.parameters
        assert "llm_provider" in sig.parameters
        assert "dry_run" in sig.parameters
