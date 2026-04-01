"""Tests for the LLM categorize API endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.server import app
    from api.auth import require_auth, require_owner

    app.dependency_overrides[require_auth] = lambda: {"email": "test@test.com", "role": "owner"}
    app.dependency_overrides[require_owner] = lambda: {"email": "test@test.com", "role": "owner"}
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestLLMCategorizeEndpoint:
    def test_dry_run_returns_estimate(self, client):
        mock_stats = {
            "total_normalized": 100,
            "categorized": 10,
            "skipped": 10,
            "review_required": 0,
            "errors": 0,
            "memory_matched": 10,
            "dry_run": True,
            "llm_candidates": 80,
            "estimated_batches": 8,
            "model": "claude-sonnet-4-20250514",
        }
        with patch("categorization.categorizer.categorize_all", return_value=mock_stats):
            resp = client.post(
                "/api/pipeline/llm-categorize",
                json={"dry_run": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["step"] == "llm-categorize"
            assert "80" in data["message"]

    def test_full_run_returns_stats(self, client):
        mock_stats = {
            "total_normalized": 50,
            "categorized": 40,
            "skipped": 5,
            "review_required": 10,
            "errors": 0,
            "memory_matched": 5,
            "llm_evaluated": 40,
            "total_cost_usd": 0.0312,
            "total_input_tokens": 5000,
            "total_output_tokens": 2000,
            "model": "claude-sonnet-4-20250514",
        }
        with patch("categorization.categorizer.categorize_all", return_value=mock_stats):
            resp = client.post("/api/pipeline/llm-categorize", json={})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "40" in data["message"]
            assert "$0.0312" in data["message"]

    def test_custom_provider_and_model(self, client):
        mock_stats = {
            "total_normalized": 10,
            "categorized": 5,
            "skipped": 5,
            "review_required": 2,
            "errors": 0,
            "memory_matched": 0,
            "llm_evaluated": 5,
            "total_cost_usd": 0.001,
            "total_input_tokens": 500,
            "total_output_tokens": 200,
            "model": "gpt-4o-mini",
        }
        with patch("categorization.categorizer.categorize_all", return_value=mock_stats) as mock_cat:
            resp = client.post(
                "/api/pipeline/llm-categorize",
                json={"provider": "openai", "model": "gpt-4o-mini"},
            )
            assert resp.status_code == 200
            # Verify params were passed through
            call_kwargs = mock_cat.call_args
            assert call_kwargs.kwargs.get("llm_provider") == "openai"
            assert call_kwargs.kwargs.get("llm_model") == "gpt-4o-mini"


    def test_force_recategorize_passes_through(self, client):
        mock_stats = {
            "total_normalized": 50,
            "categorized": 40,
            "skipped": 0,
            "review_required": 5,
            "errors": 0,
            "cleared": 45,
            "memory_matched": 5,
            "llm_evaluated": 40,
            "total_cost_usd": 0.02,
            "total_input_tokens": 3000,
            "total_output_tokens": 1500,
            "model": "claude-sonnet-4-20250514",
        }
        with patch("categorization.categorizer.categorize_all", return_value=mock_stats) as mock_cat:
            resp = client.post(
                "/api/pipeline/llm-categorize",
                json={"force": True},
            )
            assert resp.status_code == 200
            call_kwargs = mock_cat.call_args
            assert call_kwargs.kwargs.get("force") is True

    def test_categorize_force_recategorize(self, client):
        mock_stats = {
            "total_normalized": 50,
            "categorized": 45,
            "skipped": 0,
            "review_required": 5,
            "errors": 0,
            "cleared": 45,
        }
        with patch("categorization.categorizer.categorize_all", return_value=mock_stats) as mock_cat:
            resp = client.post(
                "/api/pipeline/categorize",
                json={"force": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "Recategorized" in data["message"]
            call_kwargs = mock_cat.call_args
            assert call_kwargs.kwargs.get("force") is True


class TestLLMConfigEndpoint:
    def test_get_llm_config(self, client):
        resp = client.get("/api/pipeline/llm-config")
        assert resp.status_code == 200
        data = resp.json()
        assert "provider" in data
        assert "model" in data
        assert "suggested_models" in data
        assert "anthropic" in data["suggested_models"]
        assert "openai" in data["suggested_models"]
        assert isinstance(data["has_anthropic_key"], bool)
        assert isinstance(data["has_openai_key"], bool)


class TestLLMProgressEndpoint:
    def test_no_active_progress(self, client):
        resp = client.get("/api/pipeline/llm-progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False


class TestResetEndpoint:
    def test_reset_soft(self, client):
        with patch("services.reset_service.execute_reset") as mock_reset:
            mock_reset.return_value = {
                "level": "soft",
                "deleted_count": 3,
                "backed_up": ["20260311_file.yaml"],
                "message": "Reset (soft) complete. Deleted 3 file(s).",
            }
            resp = client.post("/api/pipeline/reset", json={"level": "soft"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["level"] == "soft"
            assert data["deleted_count"] == 3

    def test_reset_rejects_during_pipeline(self, client):
        from api.dependencies import pipeline_lock
        pipeline_lock.acquire()
        try:
            resp = client.post("/api/pipeline/reset", json={"level": "soft"})
            assert resp.status_code == 409
        finally:
            pipeline_lock.release()
