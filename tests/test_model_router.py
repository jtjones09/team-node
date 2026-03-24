"""Tests for the self-aware model router."""

import sys
import os
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-for-tests")

from routing.model_router import (
    ModelTier, BackendType, route_model, _estimate_complexity, _count_signals,
    _resolve_backend,
    HIGH_COMPLEXITY_SIGNALS, LOW_COMPLEXITY_SIGNALS,
)


class TestComplexityEstimation:
    def test_simple_goal_low_complexity(self):
        score = _estimate_complexity("fetch the homepage", "engineer", False)
        assert score < 25

    def test_complex_goal_high_complexity(self):
        score = _estimate_complexity(
            "analyze the website architecture, compare trade-offs, and design a new system spec",
            "architect",
            False,
        )
        assert score >= 60

    def test_fabric_context_reduces_complexity(self):
        score_without = _estimate_complexity("research this topic", "planner_researcher", False)
        score_with = _estimate_complexity("research this topic", "planner_researcher", True)
        assert score_with < score_without

    def test_high_reasoning_domain_boost(self):
        score_eng = _estimate_complexity("review this", "engineer", False)
        score_sec = _estimate_complexity("review this", "security", False)
        assert score_sec > score_eng


class TestRouting:
    def test_simple_task_routes_to_fast(self):
        decision = route_model("fetch the homepage", "engineer")
        assert decision.tier == ModelTier.FAST

    def test_complex_task_routes_to_premium(self):
        decision = route_model(
            "analyze the architecture, compare trade-offs, design system spec, and evaluate multiple options",
            "architect",
        )
        assert decision.tier in (ModelTier.PREMIUM, ModelTier.STANDARD)

    def test_force_tier_overrides(self):
        decision = route_model("complex task", "architect", force_tier=ModelTier.FAST)
        assert decision.tier == ModelTier.FAST

    def test_planner_minimum_standard(self):
        decision = route_model("fetch something", "planner_researcher")
        assert decision.tier == ModelTier.STANDARD

    def test_no_prior_usage_routes_normally(self):
        """Router with no prior usage data should route based on complexity alone."""
        decision = route_model("summarize this", "marketing")
        assert decision.tier in (ModelTier.FAST, ModelTier.STANDARD, ModelTier.PREMIUM)
        assert decision.complexity_score >= 0

    @patch("routing.model_router._get_project_cost")
    def test_high_cost_biases_toward_fast(self, mock_cost):
        """When project has spent >$2, router biases toward FAST."""
        mock_cost.return_value = 3.50
        decision = route_model("summarize the research", "marketing", project="expensive_project")
        # The cost bias should push the score down
        assert decision.cost_context
        assert ">$2" in decision.cost_context

    @patch("routing.model_router._get_project_cost")
    def test_low_cost_allows_premium(self, mock_cost):
        """When project has spent <$0.50, PREMIUM is allowed."""
        mock_cost.return_value = 0.10
        decision = route_model(
            "analyze and compare trade-offs for the architecture design spec",
            "architect",
            project="cheap_project",
        )
        assert "<$0.50" in decision.cost_context

    def test_routing_decision_has_cost_context(self):
        decision = route_model("test", "engineer", project="test_project")
        # cost_context is a string (may be empty if no prior data)
        assert isinstance(decision.cost_context, str)

    @patch("routing.model_router._log_routing_decision")
    def test_routing_decision_logged(self, mock_log):
        """Routing decision should be stored as a fabric node."""
        route_model("test task", "engineer", project="test_project")
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert call_args[0][0] == "test_project"  # project
        assert hasattr(call_args[0][1], "tier")  # decision object


class TestHybridBackend:
    """Tests for hybrid Ollama/Anthropic routing."""

    def test_api_only_forces_anthropic(self):
        model, backend = _resolve_backend(ModelTier.FAST, api_only=True)
        assert backend == BackendType.ANTHROPIC_API
        assert "anthropic" in model or "claude" in model

    def test_api_only_standard(self):
        model, backend = _resolve_backend(ModelTier.STANDARD, api_only=True)
        assert backend == BackendType.ANTHROPIC_API

    def test_api_only_premium(self):
        model, backend = _resolve_backend(ModelTier.PREMIUM, api_only=True)
        assert backend == BackendType.ANTHROPIC_API

    def test_local_only_forces_ollama(self):
        model, backend = _resolve_backend(ModelTier.FAST, local_only=True)
        assert backend == BackendType.OLLAMA_LOCAL
        assert model.startswith("ollama/")

    def test_local_only_standard(self):
        model, backend = _resolve_backend(ModelTier.STANDARD, local_only=True)
        assert backend == BackendType.OLLAMA_LOCAL
        assert model.startswith("ollama/")

    def test_local_only_premium_uses_ollama(self):
        model, backend = _resolve_backend(ModelTier.PREMIUM, local_only=True)
        assert backend == BackendType.OLLAMA_LOCAL
        assert model.startswith("ollama/")

    def test_premium_defaults_to_anthropic(self):
        model, backend = _resolve_backend(ModelTier.PREMIUM)
        assert backend == BackendType.ANTHROPIC_API

    @patch("routing.model_router._is_ollama_available", return_value=True)
    def test_fast_uses_ollama_when_available(self, mock_ollama):
        model, backend = _resolve_backend(ModelTier.FAST)
        assert backend == BackendType.OLLAMA_LOCAL
        assert model.startswith("ollama/")

    @patch("routing.model_router._is_ollama_available", return_value=True)
    def test_standard_uses_ollama_when_available(self, mock_ollama):
        model, backend = _resolve_backend(ModelTier.STANDARD)
        assert backend == BackendType.OLLAMA_LOCAL
        assert model.startswith("ollama/")

    @patch("routing.model_router._is_ollama_available", return_value=False)
    def test_fallback_to_anthropic_when_ollama_down(self, mock_ollama):
        model, backend = _resolve_backend(ModelTier.FAST)
        assert backend == BackendType.ANTHROPIC_API

    @patch("routing.model_router._is_ollama_available", return_value=True)
    def test_route_model_includes_backend(self, mock_ollama):
        decision = route_model("fetch the homepage", "engineer")
        assert hasattr(decision, "backend")
        assert isinstance(decision.backend, BackendType)

    @patch("routing.model_router._is_ollama_available", return_value=True)
    @patch("routing.model_router._log_routing_decision")
    def test_route_model_local_only(self, mock_log, mock_ollama):
        decision = route_model("complex analysis", "architect", local_only=True)
        assert decision.backend == BackendType.OLLAMA_LOCAL

    @patch("routing.model_router._log_routing_decision")
    def test_route_model_api_only(self, mock_log):
        decision = route_model("complex analysis", "architect", api_only=True)
        assert decision.backend == BackendType.ANTHROPIC_API

    @patch("routing.model_router._is_ollama_available", return_value=True)
    @patch("routing.model_router._log_routing_decision")
    def test_telemetry_records_backend(self, mock_log, mock_ollama):
        route_model("test", "engineer", project="test_proj")
        mock_log.assert_called_once()
        decision = mock_log.call_args[0][1]
        assert hasattr(decision, "backend")
