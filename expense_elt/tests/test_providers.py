"""Tests for LLM provider factory and lazy imports."""

import sys
import pytest
from unittest.mock import patch, MagicMock

from llm.providers import get_provider
from llm.providers.base import LLMProvider


def _mock_anthropic():
    """Create a mock anthropic module and inject it into sys.modules."""
    mock_mod = MagicMock()
    mock_mod.Anthropic.return_value = MagicMock()
    return mock_mod


def _mock_openai():
    """Create a mock openai module and inject it into sys.modules."""
    mock_mod = MagicMock()
    mock_mod.OpenAI.return_value = MagicMock()
    return mock_mod


class TestProviderFactory:
    def test_get_anthropic_provider(self):
        mock_mod = _mock_anthropic()
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict("sys.modules", {"anthropic": mock_mod}):
                # Clear any cached module state
                sys.modules.pop("llm.providers.anthropic_provider", None)
                from llm.providers.anthropic_provider import AnthropicProvider
                provider = AnthropicProvider()
                assert isinstance(provider, LLMProvider)

    def test_get_openai_provider(self):
        mock_mod = _mock_openai()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            with patch.dict("sys.modules", {"openai": mock_mod}):
                sys.modules.pop("llm.providers.openai_provider", None)
                from llm.providers.openai_provider import OpenAIProvider
                provider = OpenAIProvider()
                assert isinstance(provider, LLMProvider)

    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_provider("invalid")

    def test_case_insensitive(self):
        mock_mod = _mock_anthropic()
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict("sys.modules", {"anthropic": mock_mod}):
                sys.modules.pop("llm.providers.anthropic_provider", None)
                provider = get_provider("Anthropic")
                assert isinstance(provider, LLMProvider)

    def test_missing_api_key_raises(self):
        mock_mod = _mock_anthropic()
        with patch.dict("os.environ", {}, clear=True):
            with patch.dict("sys.modules", {"anthropic": mock_mod}):
                sys.modules.pop("llm.providers.anthropic_provider", None)
                with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                    get_provider("anthropic")
