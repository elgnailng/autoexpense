"""OpenAI provider implementation."""

from __future__ import annotations

import json
import logging
import os
import time

from llm.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


# Default pricing for GPT-4o-mini (USD per 1k tokens)
_DEFAULT_INPUT_COST = 0.00015
_DEFAULT_OUTPUT_COST = 0.0006


class OpenAIProvider(LLMProvider):
    """OpenAI via the openai SDK."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        max_tokens: int = 4096,
    ):
        try:
            import openai  # noqa: F401
        except ImportError:
            raise ImportError(
                "The 'openai' package is required for the OpenAI provider. "
                "Install it with: pip install openai>=1.50"
            )

        self._model = model
        self._max_tokens = max_tokens

        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is not set. "
                "Set it or pass api_key= to the provider."
            )

        import openai
        self._client = openai.OpenAI(api_key=key)

    # --- LLMProvider interface ---

    def evaluate_transactions(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> LLMResponse:
        start = time.perf_counter()

        response = self._client.chat.completions.create(
            model=self._model,
            max_completion_tokens=self._max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        latency_ms = (time.perf_counter() - start) * 1000
        choice = response.choices[0]
        raw_text = choice.message.content or ""

        # Parse JSON from response
        parsed: list[dict] = []
        try:
            data = json.loads(raw_text)
            if isinstance(data, list):
                parsed = data
            elif isinstance(data, dict):
                # Accept any key that holds a list of evaluations
                if "evaluations" in data:
                    parsed = data["evaluations"]
                else:
                    # Find the first list value in the dict
                    for key, val in data.items():
                        if isinstance(val, list) and val and isinstance(val[0], dict):
                            logger.info("LLM response used key '%s' instead of 'evaluations'", key)
                            parsed = val
                            break
                    if not parsed:
                        # Single evaluation dict (no wrapping list)
                        if "index" in data and "category" in data:
                            parsed = [data]
                        else:
                            logger.error(
                                "LLM returned dict with no list values (keys=%s): %s...",
                                list(data.keys()), raw_text[:300],
                            )
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM JSON response (model=%s, %d chars): %s...", self._model, len(raw_text), raw_text[:200])

        usage = response.usage
        return LLMResponse(
            raw_text=raw_text,
            parsed_evaluations=parsed,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=self._model,
            latency_ms=latency_ms,
        )

    def get_model_name(self) -> str:
        return self._model

    def get_cost_per_1k_input_tokens(self) -> float:
        return _DEFAULT_INPUT_COST

    def get_cost_per_1k_output_tokens(self) -> float:
        return _DEFAULT_OUTPUT_COST
