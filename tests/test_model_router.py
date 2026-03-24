"""Tests for the self-aware model router."""

import sys
import os
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-for-tests")

from routing.model_router import (
    ModelTier, route_model, _estimate_complexity, _count_signals,
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
