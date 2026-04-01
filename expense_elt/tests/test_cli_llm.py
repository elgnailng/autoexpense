"""Tests for CLI LLM flags."""

import subprocess
import sys


def test_categorize_help_shows_llm_flags():
    """Verify --use-llm, --llm-provider, --dry-run appear in help."""
    result = subprocess.run(
        [sys.executable, "main.py", "categorize", "--help"],
        capture_output=True,
        cwd=str(__import__("pathlib").Path(__file__).parent.parent),
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0
    assert "--use-llm" in result.stdout
    assert "--llm-provider" in result.stdout
    assert "--dry-run" in result.stdout
