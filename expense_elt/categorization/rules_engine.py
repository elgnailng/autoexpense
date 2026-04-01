"""
rules_engine.py - Load config/rules.yaml and apply keyword-based categorization.

Rules are case-insensitive substring matches against merchant_normalized.
Returns the first matching rule's (category, confidence, rule_name).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import yaml

_CONFIG_DIR = Path(__file__).parent.parent / "config"
_RULES_FILE = _CONFIG_DIR / "rules.yaml"


class RulesEngine:
    """Apply keyword rules from rules.yaml to categorize transactions."""

    def __init__(self, rules_file: Optional[Path] = None):
        self._rules_file = rules_file or _RULES_FILE
        self._rules: List[dict] = []
        self._load()

    def _load(self) -> None:
        """Load rules from YAML file. Sets empty list if file missing."""
        if not self._rules_file.exists():
            self._rules = []
            return
        with open(self._rules_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._rules = data.get("rules", []) if data else []

    def match(self, merchant_normalized: str) -> Optional[Tuple[str, float, str]]:
        """
        Try to match merchant_normalized against all rules.

        Returns (category, confidence, rule_name) for the first match,
        or None if no rule matches.
        """
        if not merchant_normalized:
            return None

        merchant_lower = merchant_normalized.lower()

        for rule in self._rules:
            keywords: List[str] = rule.get("keywords", [])
            category: str = rule.get("category", "Other expenses")
            confidence: float = float(rule.get("confidence", 0.5))

            for kw in keywords:
                if kw.lower() in merchant_lower:
                    rule_name = f"keyword:{kw}"
                    return category, confidence, rule_name

        return None

    def reload(self) -> None:
        """Reload rules from disk."""
        self._load()


# Module-level singleton for convenience
_engine: Optional[RulesEngine] = None


def get_engine() -> RulesEngine:
    """Return the module-level RulesEngine singleton."""
    global _engine
    if _engine is None:
        _engine = RulesEngine()
    return _engine


def apply_rules(merchant_normalized: str) -> Optional[Tuple[str, float, str]]:
    """Convenience wrapper around RulesEngine.match()."""
    return get_engine().match(merchant_normalized)
