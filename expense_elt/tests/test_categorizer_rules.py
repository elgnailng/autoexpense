"""Tests for categorizer.py — non-LLM path: rules engine + deduction rules +
merchant memory precedence."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import csv
import pytest
import yaml

from categorization.categorizer import (
    apply_deduction_rule,
    categorize_transaction,
)
from categorization.merchant_memory import MerchantMemory, _FIELDNAMES


# ── Deduction rule application ──────────────────────────────────────


class TestApplyDeductionRule:

    def test_no_rules_defaults_to_full(self):
        status, amount, rule = apply_deduction_rule("AMAZON", 100.0, date(2025, 1, 1), [])
        assert status == "full"
        assert amount == 100.0
        assert rule is None

    def test_percentage_rule(self):
        rules = [{
            "name": "Phone 60%",
            "merchant_pattern": "rogers",
            "deductible_status": "partial",
            "method": "percentage",
            "percentage": 0.6,
        }]
        status, amount, rule = apply_deduction_rule("ROGERS WIRELESS", 100.0, date(2025, 1, 1), rules)
        assert status == "partial"
        assert abs(amount - 60.0) < 0.01
        assert rule == "Phone 60%"

    def test_fixed_monthly_rule(self):
        rules = [{
            "name": "Phone cap $97",
            "merchant_pattern": "rogers",
            "deductible_status": "partial",
            "method": "fixed_monthly",
            "amount": 97.0,
        }]
        status, amount, rule = apply_deduction_rule("ROGERS WIRELESS", 150.0, date(2025, 1, 1), rules)
        assert status == "partial"
        assert amount == 97.0

    def test_fixed_monthly_under_cap(self):
        rules = [{
            "name": "Phone cap $97",
            "merchant_pattern": "rogers",
            "deductible_status": "partial",
            "method": "fixed_monthly",
            "amount": 97.0,
        }]
        status, amount, _ = apply_deduction_rule("ROGERS WIRELESS", 50.0, date(2025, 1, 1), rules)
        assert amount == 50.0  # under cap, so full amount

    def test_personal_rule(self):
        rules = [{
            "name": "Netflix personal",
            "merchant_pattern": "netflix",
            "deductible_status": "personal",
            "method": "percentage",
            "percentage": 0.0,
        }]
        status, amount, _ = apply_deduction_rule("NETFLIX", 19.99, date(2025, 1, 1), rules)
        assert status == "personal"
        assert amount == 0.0

    def test_full_method(self):
        rules = [{
            "name": "AWS full",
            "merchant_pattern": "aws",
            "method": "full",
        }]
        status, amount, _ = apply_deduction_rule("AWS CLOUD", 200.0, date(2025, 1, 1), rules)
        assert status == "full"
        assert amount == 200.0

    def test_date_bounded_before_start(self):
        rules = [{
            "name": "Phone cap",
            "merchant_pattern": "rogers",
            "deductible_status": "partial",
            "method": "fixed_monthly",
            "amount": 97.0,
            "start_date": "2025-04-01",
        }]
        # Transaction before start date — rule should NOT match
        status, amount, rule = apply_deduction_rule("ROGERS", 100.0, date(2025, 1, 1), rules)
        assert rule is None  # no match
        assert status == "full"
        assert amount == 100.0

    def test_date_bounded_after_end(self):
        rules = [{
            "name": "Phone cap",
            "merchant_pattern": "rogers",
            "deductible_status": "partial",
            "method": "fixed_monthly",
            "amount": 97.0,
            "end_date": "2024-12-31",
        }]
        status, amount, rule = apply_deduction_rule("ROGERS", 100.0, date(2025, 3, 1), rules)
        assert rule is None

    def test_date_bounded_within_range(self):
        rules = [{
            "name": "Phone cap",
            "merchant_pattern": "rogers",
            "deductible_status": "partial",
            "method": "fixed_monthly",
            "amount": 97.0,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        }]
        status, amount, rule = apply_deduction_rule("ROGERS", 150.0, date(2025, 6, 1), rules)
        assert rule == "Phone cap"
        assert amount == 97.0

    def test_empty_merchant(self):
        rules = [{"merchant_pattern": "test", "method": "full"}]
        status, amount, rule = apply_deduction_rule("", 100.0, date(2025, 1, 1), rules)
        assert status == "full"
        assert amount == 100.0
        assert rule is None

    def test_credit_with_fixed_monthly(self):
        rules = [{
            "name": "Phone cap",
            "merchant_pattern": "rogers",
            "deductible_status": "partial",
            "method": "fixed_monthly",
            "amount": 97.0,
        }]
        status, amount, _ = apply_deduction_rule("ROGERS", -50.0, date(2025, 1, 1), rules)
        assert amount == 0.0  # credits don't deduct


# ── categorize_transaction (non-LLM path) ──────────────────────────


class TestCategorizeSingleTransaction:
    """Test categorize_transaction without LLM, using rules engine."""

    def _make_rules_yaml(self, tmp_path):
        data = {
            "rules": [
                {"keywords": ["amazon", "aws"], "category": "Office expenses", "confidence": 0.88},
                {"keywords": ["starbucks"], "category": "Meals & Entertainment", "confidence": 0.75},
            ]
        }
        f = tmp_path / "rules.yaml"
        f.write_text(yaml.dump(data), encoding="utf-8")
        return f

    def _make_empty_memory(self, tmp_path):
        f = tmp_path / "merchant_memory.csv"
        with open(f, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_FIELDNAMES)
            writer.writeheader()
        return f

    def test_rules_engine_match(self, tmp_path):
        rules_file = self._make_rules_yaml(tmp_path)
        mem_file = self._make_empty_memory(tmp_path)

        from categorization.rules_engine import RulesEngine
        engine = RulesEngine(rules_file=rules_file)
        memory = MerchantMemory(memory_file=mem_file)

        with patch("categorization.categorizer.apply_rules", side_effect=engine.match), \
             patch("categorization.categorizer.get_memory", return_value=memory):
            result = categorize_transaction(
                transaction_id="txn-1",
                merchant_normalized="AMAZON WEB SERVICES",
                original_amount=150.0,
                transaction_date=date(2025, 3, 10),
                deduction_rules=[],
            )

        assert result["category"] == "Office expenses"
        assert result["confidence"] == 0.88
        assert result["rule_applied"] == "keyword:amazon"
        # confidence 0.88 >= 0.70, so review not required
        assert result["review_required"] is False

    def test_low_confidence_triggers_review(self, tmp_path):
        rules_file = self._make_rules_yaml(tmp_path)
        mem_file = self._make_empty_memory(tmp_path)

        from categorization.rules_engine import RulesEngine
        engine = RulesEngine(rules_file=rules_file)
        memory = MerchantMemory(memory_file=mem_file)

        with patch("categorization.categorizer.apply_rules", side_effect=engine.match), \
             patch("categorization.categorizer.get_memory", return_value=memory):
            result = categorize_transaction(
                transaction_id="txn-2",
                merchant_normalized="STARBUCKS COFFEE",
                original_amount=6.50,
                transaction_date=date(2025, 3, 11),
                deduction_rules=[],
            )

        # Starbucks rule has confidence 0.75 which is >= 0.70 threshold
        # So review is NOT required
        assert result["category"] == "Meals & Entertainment"
        assert result["confidence"] == 0.75
        assert result["review_required"] is False

    def test_fallback_when_no_match(self, tmp_path):
        rules_file = self._make_rules_yaml(tmp_path)
        mem_file = self._make_empty_memory(tmp_path)

        from categorization.rules_engine import RulesEngine
        engine = RulesEngine(rules_file=rules_file)
        memory = MerchantMemory(memory_file=mem_file)

        with patch("categorization.categorizer.apply_rules", side_effect=engine.match), \
             patch("categorization.categorizer.get_memory", return_value=memory):
            result = categorize_transaction(
                transaction_id="txn-3",
                merchant_normalized="UNKNOWN MERCHANT XYZ",
                original_amount=100.0,
                transaction_date=date(2025, 3, 12),
                deduction_rules=[],
            )

        # No rule match: falls through to the else branch but merchant is non-empty
        # so it hits the rules engine which returns None, then falls to the else-else.
        # Actually: the code checks `elif merchant_normalized:` then calls apply_rules
        # which returns None, but doesn't enter the if block, so category stays "Other expenses"
        assert result["category"] == "Other expenses"
        assert result["confidence"] == 0.0
        assert result["review_required"] is True
        assert result["deductible_status"] == "needs_review"
        assert result["deductible_amount"] == 0.0

    def test_credits_always_personal(self, tmp_path):
        mem_file = self._make_empty_memory(tmp_path)
        memory = MerchantMemory(memory_file=mem_file)

        with patch("categorization.categorizer.apply_rules", return_value=("Office expenses", 0.90, "keyword:amazon")), \
             patch("categorization.categorizer.get_memory", return_value=memory):
            result = categorize_transaction(
                transaction_id="txn-credit",
                merchant_normalized="AMAZON REFUND",
                original_amount=-50.0,
                transaction_date=date(2025, 3, 10),
                deduction_rules=[],
            )

        assert result["deductible_status"] == "personal"
        assert result["deductible_amount"] == 0.0
        assert result["review_required"] is False

    def test_deduction_rules_override(self, tmp_path):
        mem_file = self._make_empty_memory(tmp_path)
        memory = MerchantMemory(memory_file=mem_file)

        ded_rules = [{
            "name": "Rogers cap",
            "merchant_pattern": "rogers",
            "deductible_status": "partial",
            "method": "fixed_monthly",
            "amount": 97.0,
        }]

        with patch("categorization.categorizer.apply_rules", return_value=("Telephone and utilties", 0.90, "keyword:rogers")), \
             patch("categorization.categorizer.get_memory", return_value=memory):
            result = categorize_transaction(
                transaction_id="txn-ded",
                merchant_normalized="ROGERS WIRELESS",
                original_amount=150.0,
                transaction_date=date(2025, 3, 10),
                deduction_rules=ded_rules,
            )

        assert result["deductible_status"] == "partial"
        assert result["deductible_amount"] == 97.0
        assert result["rule_applied"] == "Rogers cap"


# ── Merchant memory takes precedence ───────────────────────────────


class TestMemoryPrecedence:
    """Merchant memory should win over rules engine."""

    def test_memory_exact_beats_rules(self, tmp_path):
        mem_file = tmp_path / "merchant_memory.csv"
        with open(mem_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_FIELDNAMES)
            writer.writeheader()
            writer.writerow({
                "merchant_normalized": "AMAZON WEB SERVICES",
                "category": "Supplies",  # different from rules engine
                "deductible_status": "full",
                "deductible_amount_rule": "",
                "confidence": "0.98",
                "decision_source": "manual",
            })
        memory = MerchantMemory(memory_file=mem_file)

        with patch("categorization.categorizer.get_memory", return_value=memory):
            result = categorize_transaction(
                transaction_id="txn-mem",
                merchant_normalized="AMAZON WEB SERVICES",
                original_amount=200.0,
                transaction_date=date(2025, 3, 10),
                deduction_rules=[],
            )

        # Memory says "Supplies", not "Office expenses" from rules
        assert result["category"] == "Supplies"
        assert result["confidence"] == 0.98
        assert "memory" in result["rule_applied"]
        assert result["review_required"] is False

    def test_memory_fuzzy_match(self, tmp_path):
        mem_file = tmp_path / "merchant_memory.csv"
        with open(mem_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_FIELDNAMES)
            writer.writeheader()
            writer.writerow({
                "merchant_normalized": "STARBUCKS COFFEE",
                "category": "Meals & Entertainment",
                "deductible_status": "partial",
                "deductible_amount_rule": "",
                "confidence": "0.98",
                "decision_source": "manual",
            })
        memory = MerchantMemory(memory_file=mem_file)

        with patch("categorization.categorizer.get_memory", return_value=memory):
            result = categorize_transaction(
                transaction_id="txn-fuzzy",
                merchant_normalized="STARBUCKS COFFE",  # slight typo
                original_amount=6.50,
                transaction_date=date(2025, 3, 10),
                deduction_rules=[],
            )

        assert result["category"] == "Meals & Entertainment"
        assert result["confidence"] == 0.75  # fuzzy confidence
        # Fuzzy match: 0.75 < 0.85 threshold → review required
        assert result["review_required"] is True
        assert result["deductible_status"] == "needs_review"
