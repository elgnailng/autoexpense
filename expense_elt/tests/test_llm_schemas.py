"""Tests for LLM evaluation Pydantic schemas."""

import pytest
from pydantic import ValidationError

from llm.schemas import TransactionEvaluation, EvaluationBatch


class TestTransactionEvaluation:
    def test_valid_evaluation(self):
        ev = TransactionEvaluation(
            index=0,
            category="Office expenses",
            expensable_pct=100,
            confidence=95,
            reasoning="Cloud service for software development.",
            review_flag=False,
        )
        assert ev.index == 0
        assert ev.category == "Office expenses"
        assert ev.expensable_pct == 100
        assert ev.confidence == 95
        assert ev.review_flag is False

    def test_rejects_expensable_pct_over_100(self):
        with pytest.raises(ValidationError):
            TransactionEvaluation(
                index=0, category="Office expenses", expensable_pct=101,
                confidence=90, reasoning="test", review_flag=False,
            )

    def test_rejects_expensable_pct_negative(self):
        with pytest.raises(ValidationError):
            TransactionEvaluation(
                index=0, category="Office expenses", expensable_pct=-1,
                confidence=90, reasoning="test", review_flag=False,
            )

    def test_rejects_confidence_over_100(self):
        with pytest.raises(ValidationError):
            TransactionEvaluation(
                index=0, category="Office expenses", expensable_pct=100,
                confidence=101, reasoning="test", review_flag=False,
            )

    def test_rejects_confidence_negative(self):
        with pytest.raises(ValidationError):
            TransactionEvaluation(
                index=0, category="Office expenses", expensable_pct=100,
                confidence=-5, reasoning="test", review_flag=False,
            )

    def test_rejects_missing_required_fields(self):
        with pytest.raises(ValidationError):
            TransactionEvaluation(index=0, category="Office expenses")  # type: ignore

    def test_boundary_values(self):
        ev = TransactionEvaluation(
            index=0, category="Other expenses", expensable_pct=0,
            confidence=0, reasoning="Unknown", review_flag=True,
        )
        assert ev.expensable_pct == 0
        assert ev.confidence == 0

    def test_boundary_max_values(self):
        ev = TransactionEvaluation(
            index=99, category="Travel", expensable_pct=100,
            confidence=100, reasoning="Definitely business travel.", review_flag=False,
        )
        assert ev.expensable_pct == 100
        assert ev.confidence == 100


class TestEvaluationBatch:
    def test_batch_with_evaluations(self):
        batch = EvaluationBatch(evaluations=[
            TransactionEvaluation(
                index=0, category="Office expenses", expensable_pct=100,
                confidence=95, reasoning="AWS", review_flag=False,
            ),
            TransactionEvaluation(
                index=1, category="Meals & Entertainment", expensable_pct=50,
                confidence=60, reasoning="Coffee", review_flag=True,
            ),
        ])
        assert len(batch.evaluations) == 2

    def test_empty_batch(self):
        batch = EvaluationBatch(evaluations=[])
        assert len(batch.evaluations) == 0
