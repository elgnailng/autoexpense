from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

_CONFIG_DIR = Path(__file__).parent.parent / "config"
_DEDUCTION_RULES_FILE = _CONFIG_DIR / "deduction_rules.yaml"



def load_deduction_rules() -> List[Dict[str, Any]]:
    """Load deduction rules from YAML. Returns an empty list if the file is missing."""
    if not _DEDUCTION_RULES_FILE.exists():
        return []
    with open(_DEDUCTION_RULES_FILE, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data.get("deduction_rules", []) if data else []



def parse_rule_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(str(date_str), "%Y-%m-%d").date()
    except ValueError:
        return None



def apply_deduction_rule(
    merchant_normalized: str,
    original_amount: float,
    transaction_date: Optional[date],
    deduction_rules: List[Dict[str, Any]],
) -> Tuple[str, float, Optional[str]]:
    """Apply deduction rules to determine deductible status and amount."""
    if not merchant_normalized:
        return "full", original_amount, None

    merchant_lower = merchant_normalized.lower()

    for rule in deduction_rules:
        pattern = rule.get("merchant_pattern", "").lower()
        if not pattern or pattern not in merchant_lower:
            continue

        start_date = parse_rule_date(rule.get("start_date"))
        end_date = parse_rule_date(rule.get("end_date"))

        if start_date and transaction_date and transaction_date < start_date:
            continue
        if end_date and transaction_date and transaction_date > end_date:
            continue

        deductible_status = rule.get("deductible_status", "full")
        method = rule.get("method", "full")
        rule_name = rule.get("name", pattern)

        if deductible_status == "personal" or method == "percentage" and rule.get("percentage", 1.0) == 0.0:
            return "personal", 0.0, rule_name

        if method == "fixed_monthly":
            monthly_cap = float(rule.get("amount", original_amount))
            deductible_amount = min(abs(original_amount), monthly_cap)
            if original_amount < 0:
                deductible_amount = 0.0
            return deductible_status, deductible_amount, rule_name

        if method == "percentage":
            pct = float(rule.get("percentage", 1.0))
            deductible_amount = abs(original_amount) * pct
            return deductible_status, deductible_amount, rule_name

        if method == "full":
            return "full", abs(original_amount), rule_name

    return "full", abs(original_amount), None
