"""Dynamic model router — selects model tier based on task complexity + cost awareness.

Three tiers with hybrid local/API backends:
  FAST     = Ollama local  (default: qwen2.5:32b)    — $0/token
  STANDARD = Ollama local  (default: llama3.3:70b)    — $0/token
  PREMIUM  = Anthropic API (Sonnet or Opus)           — $3-$75/MTok

Falls back to Anthropic API if Ollama is unreachable.

Override modes:
  --local-only  → all tiers use Ollama (never calls Anthropic)
  --api-only    → all tiers use Anthropic API (original behavior)

The router classifies tasks by signal analysis, not a separate LLM call.
Self-aware: reads its own telemetry from the fabric to adjust routing.
"""

import re
import sys
from dataclasses import dataclass, field
from enum import Enum

from config import (
    MODEL_HAIKU, MODEL_SONNET, MODEL_OPUS,
    OLLAMA_URL, OLLAMA_FAST_MODEL, OLLAMA_STANDARD_MODEL,
    ANTHROPIC_PREMIUM,
)


class ModelTier(Enum):
    FAST = "fast"
    STANDARD = "standard"
    PREMIUM = "premium"


class BackendType(Enum):
    OLLAMA_LOCAL = "ollama_local"
    ANTHROPIC_API = "anthropic_api"


@dataclass
class RoutingDecision:
    tier: ModelTier
    model: str
    reason: str
    complexity_score: int
    cost_context: str = ""
    backend: BackendType = BackendType.ANTHROPIC_API


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


def _check_ollama_available() -> bool:
    """Check if Ollama is reachable."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


# Cache Ollama availability per session to avoid repeated checks
_ollama_available: bool | None = None


def _is_ollama_available() -> bool:
    global _ollama_available
    if _ollama_available is None:
        _ollama_available = _check_ollama_available()
    return _ollama_available


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
                "backend": decision.backend.value,
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
    local_only: bool = False,
    api_only: bool = False,
) -> RoutingDecision:
    """Select the appropriate model tier and backend for a task.

    Hybrid routing: FAST/STANDARD use Ollama (local), PREMIUM uses Anthropic API.
    Falls back to Anthropic if Ollama is unreachable.

    Args:
        goal: The task description / goal text.
        domain: The agent domain (marketing, engineer, etc.).
        has_fabric_context: Whether the fabric already has relevant nodes.
        force_tier: Override to force a specific tier.
        project: Project name for cost-aware routing.
        local_only: Force all tiers to Ollama.
        api_only: Force all tiers to Anthropic API.

    Returns:
        RoutingDecision with the selected model, backend, and reasoning.
    """
    if force_tier:
        model, backend = _resolve_backend(force_tier, local_only, api_only)
        decision = RoutingDecision(
            tier=force_tier,
            model=model,
            reason=f"Forced to {force_tier.value}",
            complexity_score=0,
            backend=backend,
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
        reason = f"High complexity ({complexity}{'+' + str(cost_bias) if cost_bias else ''}={adjusted}): multi-step reasoning or creative generation"
    elif adjusted >= 25:
        tier = ModelTier.STANDARD
        reason = f"Standard complexity ({complexity}{'+' + str(cost_bias) if cost_bias else ''}={adjusted}): domain analysis and synthesis"
    else:
        tier = ModelTier.FAST
        reason = f"Low complexity ({complexity}{'+' + str(cost_bias) if cost_bias else ''}={adjusted}): lookup, fetch, or simple task"

    # Planner/researcher always gets at least STANDARD
    if domain == "planner_researcher" and tier == ModelTier.FAST:
        tier = ModelTier.STANDARD
        reason = f"Planner minimum: {reason} -> upgraded to STANDARD"

    model, backend = _resolve_backend(tier, local_only, api_only)

    decision = RoutingDecision(
        tier=tier,
        model=model,
        reason=reason,
        complexity_score=adjusted,
        cost_context=cost_context,
        backend=backend,
    )

    # Log the routing decision as a fabric node
    if project:
        _log_routing_decision(project, decision)

    return decision


def _resolve_backend(
    tier: ModelTier,
    local_only: bool = False,
    api_only: bool = False,
) -> tuple[str, BackendType]:
    """Resolve the model string and backend type for a given tier.

    Returns (model_string, backend_type).
    """
    if api_only:
        api_map = {
            ModelTier.FAST: MODEL_HAIKU,
            ModelTier.STANDARD: MODEL_SONNET,
            ModelTier.PREMIUM: MODEL_OPUS,
        }
        return api_map[tier], BackendType.ANTHROPIC_API

    if local_only:
        ollama_map = {
            ModelTier.FAST: f"ollama/{OLLAMA_FAST_MODEL}",
            ModelTier.STANDARD: f"ollama/{OLLAMA_STANDARD_MODEL}",
            ModelTier.PREMIUM: f"ollama/{OLLAMA_STANDARD_MODEL}",
        }
        return ollama_map[tier], BackendType.OLLAMA_LOCAL

    # Hybrid: FAST/STANDARD → Ollama, PREMIUM → Anthropic
    if tier == ModelTier.PREMIUM:
        if ANTHROPIC_PREMIUM:
            return MODEL_SONNET, BackendType.ANTHROPIC_API
        else:
            return f"ollama/{OLLAMA_STANDARD_MODEL}", BackendType.OLLAMA_LOCAL

    # FAST or STANDARD — try Ollama first, fallback to API
    ollama_map = {
        ModelTier.FAST: OLLAMA_FAST_MODEL,
        ModelTier.STANDARD: OLLAMA_STANDARD_MODEL,
    }

    if _is_ollama_available():
        return f"ollama/{ollama_map[tier]}", BackendType.OLLAMA_LOCAL
    else:
        print(
            f"  Warning: Ollama unreachable at {OLLAMA_URL}, falling back to Anthropic API",
            file=sys.stderr,
        )
        fallback_map = {
            ModelTier.FAST: MODEL_HAIKU,
            ModelTier.STANDARD: MODEL_SONNET,
        }
        return fallback_map[tier], BackendType.ANTHROPIC_API


def print_backend_summary(decisions: dict[str, "RoutingDecision"]):
    """Print backend selection summary at startup."""
    print("  Backend selection:")
    for domain, d in decisions.items():
        backend_label = "local" if d.backend == BackendType.OLLAMA_LOCAL else "API"
        model_short = d.model.split("/")[-1] if "/" in d.model else d.model
        print(f"    {domain}: {d.tier.value} → {d.model} ({backend_label})")
    print()
