from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Literal, Optional

from api.dependencies import require_pipeline_idle

from config.config_writer import (
    load_keyword_rules,
    save_keyword_rules,
    load_deduction_rules,
    save_deduction_rules,
    remove_deduction_rule,
    update_deduction_rule,
    load_categories,
    record_config_change,
    load_config_history,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class KeywordRuleRequest(BaseModel):
    keywords: list[str]
    category: str
    confidence: float = 0.90


class DeductionRuleRequest(BaseModel):
    name: str
    merchant_pattern: str
    deductible_status: Literal["full", "partial", "personal"]
    method: Literal["full", "percentage", "fixed_monthly", "personal"]
    amount: Optional[float] = None
    percentage: Optional[float] = None
    category: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Keyword rules
# ---------------------------------------------------------------------------


@router.get("/config/rules")
def get_keyword_rules():
    rules = load_keyword_rules()
    return [{"index": i, **rule} for i, rule in enumerate(rules)]


@router.post("/config/rules")
def add_keyword_rule(body: KeywordRuleRequest, _=Depends(require_pipeline_idle)):
    rules = load_keyword_rules()
    for rule in rules:
        existing_kws = [k.lower() for k in rule.get("keywords", [])]
        for kw in body.keywords:
            if kw.strip().lower() in existing_kws:
                raise HTTPException(400, f"Keyword '{kw}' already exists in a rule")
    keywords = [k.strip() for k in body.keywords if k.strip()]
    rules.append({
        "keywords": keywords,
        "category": body.category,
        "confidence": body.confidence,
    })
    save_keyword_rules(rules)
    record_config_change("rules.yaml", "add", f"Added keyword rule: {keywords} -> {body.category}", "api")
    return {"success": True, "index": len(rules) - 1}


@router.put("/config/rules/{index}")
def update_keyword_rule_endpoint(index: int, body: KeywordRuleRequest, _=Depends(require_pipeline_idle)):
    rules = load_keyword_rules()
    if index < 0 or index >= len(rules):
        raise HTTPException(404, "Rule not found")
    keywords = [k.strip() for k in body.keywords if k.strip()]
    rules[index] = {
        "keywords": keywords,
        "category": body.category,
        "confidence": body.confidence,
    }
    save_keyword_rules(rules)
    record_config_change("rules.yaml", "update", f"Updated keyword rule #{index}: {keywords} -> {body.category}", "api")
    return {"success": True}


@router.delete("/config/rules/{index}")
def delete_keyword_rule(index: int, _=Depends(require_pipeline_idle)):
    rules = load_keyword_rules()
    if index < 0 or index >= len(rules):
        raise HTTPException(404, "Rule not found")
    removed = rules.pop(index)
    save_keyword_rules(rules)
    record_config_change("rules.yaml", "delete", f"Deleted keyword rule #{index}: {removed.get('keywords', [])}", "api")
    return {"success": True}


# ---------------------------------------------------------------------------
# Deduction rules
# ---------------------------------------------------------------------------


@router.get("/config/deduction-rules")
def get_deduction_rules():
    rules = load_deduction_rules()
    return [{"index": i, **rule} for i, rule in enumerate(rules)]


@router.post("/config/deduction-rules")
def add_deduction_rule(body: DeductionRuleRequest, _=Depends(require_pipeline_idle)):
    rules = load_deduction_rules()
    for rule in rules:
        if rule.get("merchant_pattern", "").lower() == body.merchant_pattern.strip().lower():
            raise HTTPException(400, f"Merchant pattern '{body.merchant_pattern}' already exists")
    new_rule = {
        "name": body.name,
        "merchant_pattern": body.merchant_pattern.strip(),
        "deductible_status": body.deductible_status,
        "method": body.method,
    }
    if body.category:
        new_rule["category"] = body.category
    if body.method == "fixed_monthly" and body.amount is not None:
        new_rule["amount"] = body.amount
    if body.method == "percentage" and body.percentage is not None:
        new_rule["percentage"] = body.percentage
    if body.start_date:
        new_rule["start_date"] = body.start_date
    if body.end_date:
        new_rule["end_date"] = body.end_date
    if body.notes:
        new_rule["notes"] = body.notes
    rules.append(new_rule)
    save_deduction_rules(rules)
    record_config_change("deduction_rules.yaml", "add", f"Added deduction rule: '{body.name}' ({body.method})", "api")
    return {"success": True, "index": len(rules) - 1}


@router.put("/config/deduction-rules/{index}")
def update_deduction_rule_endpoint(index: int, body: DeductionRuleRequest, _=Depends(require_pipeline_idle)):
    rules = load_deduction_rules()
    if index < 0 or index >= len(rules):
        raise HTTPException(404, "Rule not found")
    updated = {
        "name": body.name,
        "merchant_pattern": body.merchant_pattern.strip(),
        "deductible_status": body.deductible_status,
        "method": body.method,
    }
    if body.category:
        updated["category"] = body.category
    if body.method == "fixed_monthly" and body.amount is not None:
        updated["amount"] = body.amount
    if body.method == "percentage" and body.percentage is not None:
        updated["percentage"] = body.percentage
    if body.start_date:
        updated["start_date"] = body.start_date
    if body.end_date:
        updated["end_date"] = body.end_date
    if body.notes:
        updated["notes"] = body.notes
    update_deduction_rule(index, updated, source="api")
    return {"success": True}


@router.delete("/config/deduction-rules/{index}")
def delete_deduction_rule(index: int, _=Depends(require_pipeline_idle)):
    rules = load_deduction_rules()
    if index < 0 or index >= len(rules):
        raise HTTPException(404, "Rule not found")
    remove_deduction_rule(index, source="api")
    return {"success": True}


# ---------------------------------------------------------------------------
# Categories (read-only)
# ---------------------------------------------------------------------------


@router.get("/config/categories")
def get_categories_list():
    return load_categories()


# ---------------------------------------------------------------------------
# Config change history
# ---------------------------------------------------------------------------


@router.get("/config/history")
def get_config_history(limit: int = 50, config_file: Optional[str] = None):
    return load_config_history(limit=limit, config_file=config_file)
