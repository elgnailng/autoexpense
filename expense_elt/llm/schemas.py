"""Pydantic models for LLM evaluation input/output."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class TransactionEvaluation(BaseModel):
    """A single transaction evaluation from the LLM."""

    index: int
    category: str
    expensable_pct: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)
    reasoning: str
    review_flag: bool


class EvaluationBatch(BaseModel):
    """A batch of evaluations returned by the LLM."""

    evaluations: List[TransactionEvaluation]
