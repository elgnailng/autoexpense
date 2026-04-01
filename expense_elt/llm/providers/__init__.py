"""LLM provider factory — lazy imports so missing SDKs don't break the app."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm.providers.base import LLMProvider


def get_provider(name: str = "anthropic", **kwargs) -> "LLMProvider":
    """
    Return an LLMProvider instance by name.

    Providers are lazily imported so a missing SDK only raises
    when the user actually tries to use that provider.
    """
    name = name.lower().strip()

    if name == "anthropic":
        from llm.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(**kwargs)

    if name == "openai":
        from llm.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(**kwargs)

    raise ValueError(
        f"Unknown LLM provider '{name}'. Supported: anthropic, openai"
    )
