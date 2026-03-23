"""Dynamic model router — selects model tier based on task complexity.

Three tiers:
  FAST    = Haiku   ($0.25/$1.25 per MTok) — simple tool calls, lookups, fetches
  STANDARD = Sonnet  ($3/$15 per MTok) — analysis, writing, domain work
  PREMIUM  = Opus/Sonnet ($15/$75 per MTok) — multi-step reasoning, architecture

The router classifies tasks by signal analysis, not a separate LLM call.
Signals: goal length, keyword complexity, domain, number of constraints,
whether prior fabric context exists.

This is heuristic-based (tier 1 in the industry taxonomy). Tier 2
(classifier-based) and tier 3 (learned routing via RouteLLM/Martian)
can be layered on top later without changing the interface.
"""

import re
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


# --- Signal patterns ---

HIGH_COMPLEXITY_SIGNALS = [
    # Multi-step reasoning
    "compare", "contrast", "trade-off", "tradeoff", "evaluate", "analyze",
    "synthesize", "architecture", "design system", "spec", "specification",
    "refactor", "migrate", "two plans", "multiple options", "pros and cons",
    # Creative/generative
    "mockup", "redesign", "write an article", "draft", "proposal",
    "thought leadership", "strategy",
    # Deep technical
    "debug complex", "optimize", "security audit", "threat model",
    "performance analysis",
]

LOW_COMPLEXITY_SIGNALS = [
    # Simple lookups and fetches
    "fetch", "list", "find", "search for", "look up", "what is",
    "get the", "check if", "show me", "status of",
    # Simple CRUD
    "store", "save", "add to", "update the", "rename",
]

MEDIUM_COMPLEXITY_SIGNALS = [
    # Standard analysis
    "summarize", "explain", "describe", "review", "recommend",
    "research", "investigate", "comment on", "respond to",
]


def _count_signals(text: str, signals: list[str]) -> int:
    """Count how many signal phrases appear in the text."""
    text_lower = text.lower()
    return sum(1 for s in signals if s in text_lower)


def _estimate_complexity(goal: str, domain: str, has_fabric_context: bool) -> int:
    """Score task complexity from 0-100.

    Factors:
    - Goal length (longer goals = more complex instructions)
    - High/medium/low complexity signal keywords
    - Domain (some domains inherently need more reasoning)
    - Whether fabric already has context (reduces needed work)
    """
    score = 0

    # Length signal: longer goals typically have more constraints
    word_count = len(goal.split())
    if word_count > 80:
        score += 25
    elif word_count > 40:
        score += 15
    elif word_count > 20:
        score += 8

    # Keyword signals
    high = _count_signals(goal, HIGH_COMPLEXITY_SIGNALS)
    medium = _count_signals(goal, MEDIUM_COMPLEXITY_SIGNALS)
    low = _count_signals(goal, LOW_COMPLEXITY_SIGNALS)

    score += high * 12
    score += medium * 5
    score -= low * 4  # Low complexity signals reduce score

    # Domain adjustments
    high_reasoning_domains = {"architect", "security", "data_analytics"}
    creative_domains = {"marketing", "sales"}

    if domain in high_reasoning_domains:
        score += 15
    elif domain in creative_domains:
        score += 10

    # Existing fabric context reduces complexity
    # (agent has prior work to build on, less from-scratch reasoning)
    if has_fabric_context:
        score -= 10

    # Multiple URLs or explicit multi-part requests
    url_count = len(re.findall(r'https?://', goal))
    if url_count > 1:
        score += 10

    # Clamp to 0-100
    return max(0, min(100, score))


def route_model(
    goal: str,
    domain: str,
    has_fabric_context: bool = False,
    force_tier: ModelTier | None = None,
) -> RoutingDecision:
    """Select the appropriate model tier for a task.

    Args:
        goal: The task description / goal text.
        domain: The agent domain (marketing, engineer, etc.).
        has_fabric_context: Whether the fabric already has relevant nodes.
        force_tier: Override to force a specific tier (for testing/debugging).

    Returns:
        RoutingDecision with the selected model and reasoning.
    """
    if force_tier:
        model_map = {
            ModelTier.FAST: MODEL_HAIKU,
            ModelTier.STANDARD: MODEL_SONNET,
            ModelTier.PREMIUM: MODEL_OPUS,
        }
        return RoutingDecision(
            tier=force_tier,
            model=model_map[force_tier],
            reason=f"Forced to {force_tier.value}",
            complexity_score=0,
        )

    complexity = _estimate_complexity(goal, domain, has_fabric_context)

    # Tier thresholds
    if complexity >= 60:
        tier = ModelTier.PREMIUM
        model = MODEL_SONNET  # Default premium is Sonnet; Opus via env override
        reason = f"High complexity ({complexity}): multi-step reasoning or creative generation"
    elif complexity >= 25:
        tier = ModelTier.STANDARD
        model = MODEL_SONNET
        reason = f"Standard complexity ({complexity}): domain analysis and synthesis"
    else:
        tier = ModelTier.FAST
        model = MODEL_HAIKU
        reason = f"Low complexity ({complexity}): lookup, fetch, or simple task"

    # Planner/researcher always gets at least STANDARD
    # (it does synthesis work, not just fetching)
    if domain == "planner_researcher" and tier == ModelTier.FAST:
        tier = ModelTier.STANDARD
        model = MODEL_SONNET
        reason = f"Planner minimum: {reason} -> upgraded to STANDARD"

    return RoutingDecision(
        tier=tier,
        model=model,
        reason=reason,
        complexity_score=complexity,
    )
