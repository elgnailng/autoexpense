"""Load LLM configuration from llm_config.yaml with fallback defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

_CONFIG_DIR = Path(__file__).parent.parent / "config"
_LLM_CONFIG_FILE = _CONFIG_DIR / "llm_config.yaml"


@dataclass
class LLMConfig:
    """LLM evaluator configuration."""

    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    batch_size: int = 10
    max_retries: int = 3
    initial_backoff_seconds: float = 2.0
    max_cost_per_run: float = 5.00
    skip_high_confidence_threshold: float = 0.85
    temperature: float = 0.1


def load_llm_config(config_file: Optional[Path] = None) -> LLMConfig:
    """
    Load LLM config from YAML, falling back to defaults for missing fields.

    If the file doesn't exist, returns all defaults.
    """
    path = config_file or _LLM_CONFIG_FILE
    config = LLMConfig()

    if not path.exists():
        return config

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or not isinstance(data, dict):
        return config

    for fld in config.__dataclass_fields__:
        if fld in data:
            setattr(config, fld, data[fld])

    return config
