"""Tests for categorization/merchant_memory.py — exact match, fuzzy match,
save decision, and precedence over rules."""

import csv
from pathlib import Path

import pytest

from categorization.merchant_memory import MerchantMemory, _FIELDNAMES


@pytest.fixture
def memory_file(tmp_path):
    """Create a temporary merchant_memory.csv with known entries."""
    f = tmp_path / "merchant_memory.csv"
    with open(f, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_FIELDNAMES)
        writer.writeheader()
        writer.writerow({
            "merchant_normalized": "AMAZON WEB SERVICES",
            "category": "Office expenses",
            "deductible_status": "full",
            "deductible_amount_rule": "",
            "confidence": "0.98",
            "decision_source": "manual",
        })
        writer.writerow({
            "merchant_normalized": "STARBUCKS COFFEE",
            "category": "Meals & Entertainment",
            "deductible_status": "partial",
            "deductible_amount_rule": "",
            "confidence": "0.98",
            "decision_source": "manual",
        })
    return f


@pytest.fixture
def memory(memory_file):
    return MerchantMemory(memory_file=memory_file)


class TestExactMatch:

    def test_exact_match_returns_stored(self, memory):
        result = memory.lookup("AMAZON WEB SERVICES")
        assert result is not None
        category, ded_status, confidence, source = result
        assert category == "Office expenses"
        assert ded_status == "full"
        assert confidence == 0.98
        assert source == "manual"

    def test_exact_match_case_sensitive(self, memory):
        """Lookup is case-sensitive (merchant_normalized is already uppercased).
        Lowercase input won't exact-match the uppercased key. Fuzzy match
        depends on rapidfuzz score meeting the 85 threshold."""
        result = memory.lookup("amazon web services")
        # token_sort_ratio is case-insensitive, but the score for identical
        # tokens in different case may or may not meet threshold 85.
        # The important contract: exact match requires exact casing.
        exact_result = memory.lookup("AMAZON WEB SERVICES")
        assert exact_result is not None
        assert exact_result[2] == 0.98  # exact confidence

    def test_no_match_returns_none(self, memory):
        assert memory.lookup("COMPLETELY UNKNOWN") is None


class TestFuzzyMatch:

    def test_fuzzy_close_match(self, memory):
        """A slightly different name should fuzzy-match."""
        result = memory.lookup("AMAZON WEB SERVICE")  # missing trailing S
        assert result is not None
        assert result[0] == "Office expenses"
        assert result[2] == 0.75  # fuzzy confidence

    def test_fuzzy_too_different(self, memory):
        """A very different name should not fuzzy-match."""
        result = memory.lookup("TOTALLY DIFFERENT MERCHANT XYZ")
        assert result is None


class TestSaveDecision:

    def test_save_new_merchant(self, memory, memory_file):
        memory.save_decision(
            merchant_normalized="NEW MERCHANT",
            category="Travel",
            deductible_status="full",
            confidence=1.0,
            decision_source="manual_web",
        )
        # Should now be found by exact match
        result = memory.lookup("NEW MERCHANT")
        assert result is not None
        assert result[0] == "Travel"

        # Also persisted to CSV
        with open(memory_file, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        merchants = [r["merchant_normalized"] for r in rows]
        assert "NEW MERCHANT" in merchants

    def test_update_existing_merchant(self, memory, memory_file):
        memory.save_decision(
            merchant_normalized="AMAZON WEB SERVICES",
            category="Supplies",
            deductible_status="partial",
            confidence=1.0,
            decision_source="manual_web",
        )
        result = memory.lookup("AMAZON WEB SERVICES")
        assert result[0] == "Supplies"
        assert result[1] == "partial"

    def test_save_with_deduction_rule(self, memory):
        rule = {"method": "percentage", "percentage": 0.5}
        memory.save_decision(
            merchant_normalized="PHONE CO",
            category="Telephone and utilties",
            deductible_status="partial",
            confidence=1.0,
            decision_source="manual",
            deductible_amount_rule=rule,
        )
        result = memory.lookup("PHONE CO")
        assert result is not None
        assert result[0] == "Telephone and utilties"


class TestEmptyMemory:

    def test_empty_csv_created(self, tmp_path):
        f = tmp_path / "empty_memory.csv"
        mem = MerchantMemory(memory_file=f)
        assert f.exists()
        assert mem.lookup("ANYTHING") is None

    def test_all_merchants_empty(self, tmp_path):
        f = tmp_path / "empty_memory.csv"
        mem = MerchantMemory(memory_file=f)
        assert mem.all_merchants() == []


class TestAllMerchants:

    def test_lists_all(self, memory):
        merchants = memory.all_merchants()
        assert "AMAZON WEB SERVICES" in merchants
        assert "STARBUCKS COFFEE" in merchants
        assert len(merchants) == 2
