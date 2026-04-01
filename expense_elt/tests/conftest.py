"""Shared fixtures for LLM evaluator tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_transactions():
    """Sample normalized transactions for testing."""
    return [
        {
            "transaction_id": "txn-001",
            "transaction_date": "2025-03-10",
            "merchant_normalized": "AMAZON WEB SERVICES",
            "original_amount": 150.00,
            "institution": "RBC_VISA",
        },
        {
            "transaction_id": "txn-002",
            "transaction_date": "2025-03-11",
            "merchant_normalized": "STARBUCKS COFFEE",
            "original_amount": 6.50,
            "institution": "BMO",
        },
        {
            "transaction_id": "txn-003",
            "transaction_date": "2025-03-12",
            "merchant_normalized": "NETFLIX",
            "original_amount": 19.99,
            "institution": "RBC_VISA",
        },
    ]


@pytest.fixture
def sample_categories():
    """CRA T2125 categories."""
    return [
        "Advertising",
        "Meals & Entertainment",
        "Insurance",
        "Business tax, fees, licences",
        "Office expenses",
        "Supplies",
        "Legal, accounting, and other professional fees",
        "Management and administration fees",
        "Rent",
        "Maintenance and repairs",
        "Salaries, wages, and benefits",
        "Telephone and utilties",
        "Travel",
        "Delivery, freight, and express",
        "Motor vehcie expenses",
        "Health Medical",
        "Other expenses",
    ]


@pytest.fixture
def mock_llm_response_json():
    """Valid JSON response matching 3 sample transactions."""
    return [
        {
            "index": 0,
            "category": "Office expenses",
            "expensable_pct": 100,
            "confidence": 95,
            "reasoning": "AWS is a cloud infrastructure service used for software development.",
            "review_flag": False,
        },
        {
            "index": 1,
            "category": "Meals & Entertainment",
            "expensable_pct": 50,
            "confidence": 60,
            "reasoning": "Coffee shop — could be personal or a business meeting. Flagging for review.",
            "review_flag": True,
        },
        {
            "index": 2,
            "category": "Other expenses",
            "expensable_pct": 0,
            "confidence": 95,
            "reasoning": "Netflix is a personal entertainment subscription.",
            "review_flag": False,
        },
    ]
