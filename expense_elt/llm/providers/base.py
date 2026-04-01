"""Abstract base class for LLM providers + shared response dataclass."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class LLMResponse:
    """Structured response from an LLM API call."""

    raw_text: str
    parsed_evaluations: List[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    latency_ms: float = 0.0


class LLMProvider(ABC):
    """Interface every LLM backend must implement."""

    @abstractmethod
    def evaluate_transactions(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Send prompts to the LLM and return a structured response."""

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier string."""

    @abstractmethod
    def get_cost_per_1k_input_tokens(self) -> float:
        """Return cost in USD per 1 000 input tokens."""

    @abstractmethod
    def get_cost_per_1k_output_tokens(self) -> float:
        """Return cost in USD per 1 000 output tokens."""
