"""CrewAI callback hooks for automatic usage tracking.

CrewAI emits step callbacks that include token usage.
This module hooks into those callbacks to automatically
log every LLM call to the usage tracker.

Usage:
    tracker = UsageTracker()
    callbacks = create_tracking_callbacks(tracker, project="reallycoons")
    # Pass to crew or agent configuration
"""

import time
from typing import Any

from tracking.usage_tracker import UsageTracker, UsageEvent


def create_step_callback(
    tracker: UsageTracker,
    project: str = "",
    domain: str = "",
    tier: str = "",
    model: str = "",
    tags: list[str] | None = None,
):
    """Create a CrewAI step_callback that logs usage.

    CrewAI calls step_callback(step_output) after each agent step.
    The step_output contains token usage when available.
    """
    _tags = tags or []
    _start_time = time.time()

    def callback(step_output: Any) -> None:
        nonlocal _start_time
        elapsed = int((time.time() - _start_time) * 1000)
        _start_time = time.time()  # Reset for next step

        # Extract what we can from CrewAI's step output
        agent_name = ""
        operation = "step"
        output_text = ""

        if hasattr(step_output, "agent"):
            agent_name = str(step_output.agent)
        if hasattr(step_output, "output"):
            output_text = str(step_output.output)[:200]
        if hasattr(step_output, "tool"):
            operation = f"tool:{step_output.tool}"

        # Estimate tokens from output length (rough: 1 token ~= 4 chars)
        est_output_tokens = len(output_text) // 4 if output_text else 0

        event = UsageEvent(
            project=project,
            domain=domain,
            agent=agent_name,
            model=model,
            tier=tier,
            operation=operation,
            output_tokens=est_output_tokens,
            duration_ms=elapsed,
            tags=[*_tags, f"project:{project}"] if project else _tags,
        )
        tracker.log(event)

    return callback


def log_crew_run(
    tracker: UsageTracker,
    project: str,
    goal: str,
    domains: list[str],
    models: dict[str, str],
    tiers: dict[str, str],
    result: Any = None,
    duration_ms: int = 0,
    tags: list[str] | None = None,
) -> str:
    """Log a complete crew run as a single summary event."""
    event = UsageEvent(
        project=project,
        domain=",".join(domains),
        agent="crew",
        model=",".join(set(models.values())),
        tier=",".join(set(tiers.values())),
        operation="crew_run",
        duration_ms=duration_ms,
        tags=[
            f"project:{project}",
            f"domains:{','.join(domains)}",
            *(tags or []),
        ],
        metadata={
            "goal": goal[:500],
            "models": models,
            "tiers": tiers,
            "result_length": len(str(result)) if result else 0,
        },
    )
    return tracker.log(event)
