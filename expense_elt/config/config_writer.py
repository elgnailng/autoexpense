"""
config_writer.py - Shared helpers for reading/writing config YAML files.

Used by both the Review page and the Configuration page to avoid
duplicating YAML manipulation logic.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

_CONFIG_DIR = Path(__file__).parent
_HISTORY_FILE = _CONFIG_DIR / "config_history.jsonl"


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# Config change history
# ---------------------------------------------------------------------------

def record_config_change(
    config_file: str,
    action: str,
    detail: str,
    source: str = "unknown",
) -> None:
    """Append a config change entry to the history log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config_file": config_file,
        "action": action,
        "detail": detail,
        "source": source,
    }
    with open(_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def load_config_history(
    limit: int = 50,
    config_file: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Read config change history, newest first."""
    if not _HISTORY_FILE.exists():
        return []
    entries = []
    with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if config_file and entry.get("config_file") != config_file:
                    continue
                entries.append(entry)
            except json.JSONDecodeError:
                continue
    entries.reverse()
    return entries[:limit] if limit else entries


# ---------------------------------------------------------------------------
# Keyword rules (config/rules.yaml)
# ---------------------------------------------------------------------------

def load_keyword_rules() -> List[Dict]:
    data = _load_yaml(_CONFIG_DIR / "rules.yaml")
    return data.get("rules", [])


def save_keyword_rules(rules: List[Dict]) -> None:
    _save_yaml(_CONFIG_DIR / "rules.yaml", {"rules": rules})


def append_keyword_rule(keyword: str, category: str, confidence: float = 0.90, *, source: str = "unknown") -> None:
    """Append a new keyword rule. If the keyword already exists in any rule, skip."""
    rules = load_keyword_rules()
    kw_lower = keyword.strip().lower()

    # Check for duplicate
    for rule in rules:
        existing_kws = [k.lower() for k in rule.get("keywords", [])]
        if kw_lower in existing_kws:
            return  # already exists

    rules.append({
        "keywords": [keyword.strip()],
        "category": category,
        "confidence": confidence,
    })
    save_keyword_rules(rules)
    record_config_change("rules.yaml", "add", f"Added keyword rule: '{keyword.strip()}' -> {category}", source)


# ---------------------------------------------------------------------------
# Deduction rules (config/deduction_rules.yaml)
# ---------------------------------------------------------------------------

def load_deduction_rules() -> List[Dict]:
    data = _load_yaml(_CONFIG_DIR / "deduction_rules.yaml")
    return data.get("deduction_rules", [])


def save_deduction_rules(rules: List[Dict]) -> None:
    _save_yaml(_CONFIG_DIR / "deduction_rules.yaml", {"deduction_rules": rules})


def append_deduction_rule(
    name: str,
    merchant_pattern: str,
    deductible_status: str,
    method: str,
    amount: Optional[float] = None,
    percentage: Optional[float] = None,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    notes: Optional[str] = None,
    *,
    source: str = "unknown",
) -> None:
    """Append a new deduction rule. Skips if merchant_pattern already exists."""
    rules = load_deduction_rules()
    pattern_lower = merchant_pattern.strip().lower()

    for rule in rules:
        if rule.get("merchant_pattern", "").lower() == pattern_lower:
            return  # already exists

    new_rule: Dict[str, Any] = {
        "name": name,
        "merchant_pattern": merchant_pattern.strip(),
        "deductible_status": deductible_status,
        "method": method,
    }
    if category:
        new_rule["category"] = category
    if method == "fixed_monthly" and amount is not None:
        new_rule["amount"] = amount
    if method == "percentage" and percentage is not None:
        new_rule["percentage"] = percentage
    if start_date:
        new_rule["start_date"] = start_date
    if end_date:
        new_rule["end_date"] = end_date
    if notes:
        new_rule["notes"] = notes

    rules.append(new_rule)
    save_deduction_rules(rules)
    record_config_change("deduction_rules.yaml", "add", f"Added deduction rule: '{name}' ({method})", source)


def update_deduction_rule(index: int, rule: Dict, *, source: str = "unknown") -> None:
    """Replace the rule at the given index."""
    rules = load_deduction_rules()
    if 0 <= index < len(rules):
        rules[index] = rule
        save_deduction_rules(rules)
        record_config_change("deduction_rules.yaml", "update", f"Updated deduction rule #{index}: '{rule.get('name', '')}'", source)


def remove_deduction_rule(index: int, *, source: str = "unknown") -> None:
    """Remove the deduction rule at the given index."""
    rules = load_deduction_rules()
    if 0 <= index < len(rules):
        removed_name = rules[index].get("name", f"Rule #{index}")
        rules.pop(index)
        save_deduction_rules(rules)
        record_config_change("deduction_rules.yaml", "delete", f"Deleted deduction rule: '{removed_name}'", source)


# ---------------------------------------------------------------------------
# Categories (config/categories.yaml)
# ---------------------------------------------------------------------------

def load_categories() -> List[str]:
    data = _load_yaml(_CONFIG_DIR / "categories.yaml")
    return data.get("categories", [])
