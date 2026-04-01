"""Tests for categorization/rules_engine.py — keyword rule matching."""

import textwrap
from pathlib import Path

import pytest
import yaml

from categorization.rules_engine import RulesEngine


@pytest.fixture
def rules_file(tmp_path):
    """Create a temporary rules.yaml with known content."""
    data = {
        "rules": [
            {
                "keywords": ["amazon", "aws"],
                "category": "Office expenses",
                "confidence": 0.88,
            },
            {
                "keywords": ["starbucks", "tim hortons"],
                "category": "Meals & Entertainment",
                "confidence": 0.75,
            },
            {
                "keywords": ["rogers", "telus"],
                "category": "Telephone and utilties",
                "confidence": 0.90,
            },
        ]
    }
    f = tmp_path / "rules.yaml"
    f.write_text(yaml.dump(data), encoding="utf-8")
    return f


@pytest.fixture
def engine(rules_file):
    return RulesEngine(rules_file=rules_file)


class TestRulesEngine:

    def test_exact_keyword_match(self, engine):
        result = engine.match("AMAZON WEB SERVICES")
        assert result is not None
        category, confidence, rule_name = result
        assert category == "Office expenses"
        assert confidence == 0.88
        assert rule_name == "keyword:amazon"

    def test_case_insensitive(self, engine):
        result = engine.match("Amazon.ca")
        assert result is not None
        assert result[0] == "Office expenses"

    def test_substring_match(self, engine):
        result = engine.match("TIM HORTONS #1234")
        assert result is not None
        assert result[0] == "Meals & Entertainment"

    def test_no_match_returns_none(self, engine):
        assert engine.match("TOTALLY UNKNOWN MERCHANT") is None

    def test_empty_string_returns_none(self, engine):
        assert engine.match("") is None

    def test_first_rule_wins(self, engine):
        """When multiple rules could match, first one wins."""
        result = engine.match("AMAZON STARBUCKS COMBO")
        assert result is not None
        assert result[0] == "Office expenses"  # amazon rule comes first

    def test_confidence_propagated(self, engine):
        result = engine.match("ROGERS WIRELESS")
        assert result is not None
        assert result[1] == 0.90

    def test_rule_name_format(self, engine):
        result = engine.match("AWS CLOUD")
        assert result is not None
        assert result[2] == "keyword:aws"

    def test_missing_rules_file(self, tmp_path):
        engine = RulesEngine(rules_file=tmp_path / "nonexistent.yaml")
        assert engine.match("AMAZON") is None

    def test_empty_rules_file(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("", encoding="utf-8")
        engine = RulesEngine(rules_file=f)
        assert engine.match("AMAZON") is None

    def test_reload(self, rules_file, engine):
        # Initially matches
        assert engine.match("AMAZON") is not None

        # Overwrite with empty rules
        rules_file.write_text(yaml.dump({"rules": []}), encoding="utf-8")
        engine.reload()
        assert engine.match("AMAZON") is None
