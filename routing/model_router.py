"""Dynamic model router — selects model tier based on task complexity + cost awareness.

Three tiers:
  FAST    = Haiku   ($0.25/$1.25 per MTok) — simple tool calls, lookups, fetches
  STANDARD = Sonnet  ($3/$15 per MTok) — analysis, writing, domain work
  PREMIUM  = Opus/Sonnet ($15/$75 per MTok) — multi-step reasoning, architecture

The router classifies tasks by signal analysis, not a separate LLM call.
Signals: goal length, keyword complexity, domain, number of constraints,
whether prior fabric context exists.

Self-aware: reads its own telemetry from the fabric to adjust routing
based on accumulated cost. This is the first self-referential reasoning loop.
"""

import re
import sys
from dataclasses import dataclass
from enum import Enum

from config import MODEL_HAIKU, MODEL_SONNET, MODEL_OPUS


class ModelTier(Enum):
    FAST = "fast"
    STANDARD = "standard"
    PREMIUM = "premium"


@dataclass
class RoutingDecision:
    tier: ModelTier
    model: str
    reason: str
    complexity_score: int
    cost_context: str = ""


# --- Signal patterns ---

HIGH_COMPLEXITY_SIGNALS = [
    "compare", "contrast", "trade-off", "tradeoff", "evaluate", "analyze",
    "synthesize", "architecture", "design system", "spec", "specification",
    "refactor", "migrate", "two plans", "multiple options", "pros and cons",
    "mockup", "redesign", "write an article", "draft", "proposal",
    "thought leadership", "strategy",
    "debug complex", "optimize", "security audit", "threat model",
    "performance analysis",
]

LOW_COMPLEXITY_SIGNALS = [
    "fetch", "list", "find", "search for", "look up", "what is",
    "get the", "check if", "show me", "status of",
    "store", "save", "add to", "update the", "rename",
]

MEDIUM_COMPLEXITY_SIGNALS = [
    "summarize", "explain", "describe", "review", "recommend",
    "research", "investigate", "comment on", "respond to",
]


def _count_signals(text: str, signals: list[str]) -> int:
    text_lower = text.lower()
    return sum(1 for s in signals if s in text_lower)


def _estimate_complexity(goal: str, domain: str, has_fabric_context: bool) -> int:
    score = 0
    word_count = len(goal.split())
    if word_count > 80:
        score += 25
    elif word_count > 40:
        score += 15
    elif word_count > 20:
        score += 8

    high = _count_signals(goal, HIGH_COMPLEXITY_SIGNALS)
    medium = _count_signals(goal, MEDIUM_COMPLEXITY_SIGNALS)
    low = _count_signals(goal, LOW_COMPLEXITY_SIGNALS)

    score += high * 12
    score += medium * 5
    score -= low * 4

    high_reasoning_domains = {"architect", "security", "data_analytics"}
    creative_domains = {"marketing", "sales"}

    if domain in high_reasoning_domains:
        score += 15
    elif domain in creative_domains:
        score += 10

    if has_fabric_context:
        score -= 10

    url_count = len(re.findall(r'https?://', goal))
    if url_count > 1:
        score += 10

    return max(0, min(100, score))


def _get_project_cost(project: str) -> float:
    """Query fabric for total cost spent on this project's telemetry.

    Returns 0.0 if fabric is unavailable or no data exists.
    """
    try:
        from tracking.fabric_tracker import FabricTracker
        tracker = FabricTracker(project=project)
        return tracker.total_cost(project=project)
    except Exception:
        return 0.0


def _log_routing_decision(project: str, decision: "RoutingDecision"):
    """Store the routing decision as a fabric node."""
    try:
        from tracking.fabric_tracker import FabricTracker, UsageEvent
        tracker = FabricTracker(project=project)
        event = UsageEvent(
            project=project,
            agent="router",
            model=decision.model,
            tier=decision.tier.value,
            operation="routing_decision",
            metadata={
                "decision": decision.tier.value,
                "reason": decision.reason,
                "complexity_score": decision.complexity_score,
            },
        )
        tracker.log(event)
    except Exception as e:
        print(f"Warning: could not log routing decision: {e}", file=sys.stderr)


def route_model(
    goal: str,
    domain: str,
    has_fabric_context: bool = False,
    force_tier: ModelTier | None = None,
    project: str | None = None,
) -> RoutingDecision:
    """Select the appropriate model tier for a task.

    Now self-aware: checks fabric telemetry for accumulated cost
    and adjusts routing accordingly.

    Args:
        goal: The task description / goal text.
        domain: The agent domain (marketing, engineer, etc.).
        has_fabric_context: Whether the fabric already has relevant nodes.
        force_tier: Override to force a specific tier.
        project: Project name for cost-aware routing.

    Returns:
        RoutingDecision with the selected model and reasoning.
    """
    if force_tier:
        model_map = {
            ModelTier.FAST: MODEL_HAIKU,
            ModelTier.STANDARD: MODEL_SONNET,
            ModelTier.PREMIUM: MODEL_OPUS,
        }
        decision = RoutingDecision(
            tier=force_tier,
            model=model_map[force_tier],
            reason=f"Forced to {force_tier.value}",
            complexity_score=0,
        )
        if project:
            _log_routing_decision(project, decision)
        return decision

    complexity = _estimate_complexity(goal, domain, has_fabric_context)

    # Check accumulated cost from fabric telemetry
    cost_context = ""
    cost_bias = 0
    if project:
        prior_cost = _get_project_cost(project)
        if prior_cost > 0:
            cost_context = f"Prior spend: ${prior_cost:.2f}"
            if prior_cost > 2.0:
                cost_bias = -20  # Push toward FAST
                cost_context += " (>$2 — biasing toward FAST)"
            elif prior_cost < 0.50:
                cost_bias = 10  # Allow PREMIUM
                cost_context += " (<$0.50 — PREMIUM allowed)"

    adjusted = max(0, min(100, complexity + cost_bias))

    # Tier thresholds
    if adjusted >= 60:
        tier = ModelTier.PREMIUM
        model = MODEL_SONNET
        reason = f"High complexity ({complexity}{'+' + str(cost_bias) if cost_bias else ''}={adjusted}): multi-step reasoning or creative generation"
    elif adjusted >= 25:
        tier = ModelTier.STANDARD
        model = MODEL_SONNET
        reason = f"Standard complexity ({complexity}{'+' + str(cost_bias) if cost_bias else ''}={adjusted}): domain analysis and synthesis"
    else:
        tier = ModelTier.FAST
        model = MODEL_HAIKU
        reason = f"Low complexity ({complexity}{'+' + str(cost_bias) if cost_bias else ''}={adjusted}): lookup, fetch, or simple task"

    # Planner/researcher always gets at least STANDARD
    if domain == "planner_researcher" and tier == ModelTier.FAST:
        tier = ModelTier.STANDARD
        model = MODEL_SONNET
        reason = f"Planner minimum: {reason} -> upgraded to STANDARD"

    decision = RoutingDecision(
        tier=tier,
        model=model,
        reason=reason,
        complexity_score=adjusted,
        cost_context=cost_context,
    )

    # Log the routing decision as a fabric node
    if project:
        _log_routing_decision(project, decision)

    return decision
