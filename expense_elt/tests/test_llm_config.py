"""Tests for LLM config loading."""

import tempfile
from pathlib import Path

import yaml

from llm.config import LLMConfig, load_llm_config


class TestLLMConfig:
    def test_defaults(self):
        cfg = LLMConfig()
        assert cfg.provider == "anthropic"
        assert cfg.batch_size == 10
        assert cfg.max_retries == 3
        assert cfg.max_cost_per_run == 5.00
        assert cfg.temperature == 0.1

    def test_load_from_yaml(self, tmp_path):
        config_file = tmp_path / "llm_config.yaml"
        config_file.write_text(yaml.dump({
            "provider": "openai",
            "model": "gpt-4o",
            "batch_size": 20,
            "max_cost_per_run": 10.00,
        }))
        cfg = load_llm_config(config_file)
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4o"
        assert cfg.batch_size == 20
        assert cfg.max_cost_per_run == 10.00
        # Unset fields keep defaults
        assert cfg.max_retries == 3
        assert cfg.temperature == 0.1

    def test_fallback_when_file_missing(self, tmp_path):
        cfg = load_llm_config(tmp_path / "nonexistent.yaml")
        assert cfg.provider == "anthropic"
        assert cfg.batch_size == 10

    def test_override_individual_fields(self, tmp_path):
        config_file = tmp_path / "llm_config.yaml"
        config_file.write_text(yaml.dump({"batch_size": 5}))
        cfg = load_llm_config(config_file)
        assert cfg.batch_size == 5
        assert cfg.provider == "anthropic"  # default preserved
