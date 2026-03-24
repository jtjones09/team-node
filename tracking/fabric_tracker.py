"""Fabric-native usage tracker — every API call becomes a node in the fabric.

Replaces the SQLite usage_tracker.py. All usage events are stored as
intent nodes with metadata, queryable via `intent fabric search --where`
and `intent fabric aggregate`.

Uses the Ecphory CLI binary for all operations.
"""

import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Cost per million tokens (input/output) as of March 2026
MODEL_COSTS = {
    "anthropic/claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
    "anthropic/claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "anthropic/claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "haiku": {"input": 0.25, "output": 1.25},
    "sonnet": {"input": 3.0, "output": 15.0},
    "opus": {"input": 15.0, "output": 75.0},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for an API call."""
    costs = MODEL_COSTS.get(model)
    if not costs:
        for key, val in MODEL_COSTS.items():
            if key in model or model in key:
                costs = val
                break
    if not costs:
        return 0.0
    return (
        (input_tokens / 1_000_000) * costs["input"]
        + (output_tokens / 1_000_000) * costs["output"]
    )


@dataclass
class UsageEvent:
    """A single API call event."""
    event_id: str = ""
    timestamp: str = ""
    project: str = ""
    domain: str = ""
    agent: str = ""
    model: str = ""
    tier: str = ""
    operation: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    success: bool = True
    error: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class FabricTracker:
    """Fabric-native usage tracking — every API call is a node.

    Usage events are stored as intent nodes with domain=system_telemetry
    and rich metadata for querying and aggregation.
    """

    def __init__(self, binary_path: str | None = None, project: str | None = None):
        from config import FABRIC_BINARY
        self._binary = binary_path or FABRIC_BINARY
        self._project = project or "default"

    def _run_cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """Run intent CLI command."""
        cmd = [self._binary, *args]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
            if check and result.returncode != 0:
                # Non-fatal: log warning but don't crash
                import sys
                print(f"Warning: fabric CLI error: {result.stderr.strip()}", file=sys.stderr)
            return result
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            import sys
            print(f"Warning: fabric CLI unavailable: {e}", file=sys.stderr)
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr=str(e))

    def log(self, event: UsageEvent) -> str:
        """Log a usage event as a fabric node. Returns event_id."""
        if not event.event_id:
            event.event_id = str(uuid.uuid4())[:8]
        if not event.timestamp:
            event.timestamp = datetime.now(timezone.utc).isoformat()
        if not event.total_tokens:
            event.total_tokens = event.input_tokens + event.output_tokens
        if not event.cost_usd:
            event.cost_usd = estimate_cost(
                event.model, event.input_tokens, event.output_tokens
            )

        want = f"API call: {event.agent or 'unknown'} used {event.model or 'unknown'} for {event.operation or 'unknown'}"

        args = [
            "fabric", "add",
            "--want", want,
            "--project", self._project,
            "--meta", f"domain=system_telemetry",
            "--meta", f"event_id={event.event_id}",
            "--meta", f"project={event.project}",
            "--meta", f"agent={event.agent}",
            "--meta", f"model={event.model}",
            "--meta", f"tier={event.tier}",
            "--meta", f"operation={event.operation}",
            "--meta", f"input_tokens={event.input_tokens}",
            "--meta", f"output_tokens={event.output_tokens}",
            "--meta", f"total_tokens={event.total_tokens}",
            "--meta", f"cost_usd={event.cost_usd}",
            "--meta", f"duration_ms={event.duration_ms}",
            "--meta", f"success={str(event.success).lower()}",
            "--meta", f"timestamp={event.timestamp}",
        ]

        self._run_cli(*args)
        return event.event_id

    def query(
        self,
        project: str | None = None,
        domain: str | None = None,
        model: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query usage events from the fabric."""
        where_parts = ["domain=system_telemetry"]
        if project:
            where_parts.append(f"project={project}")
        if domain:
            where_parts.append(f"agent_domain={domain}")
        if model:
            where_parts.append(f"model={model}")

        where_clause = " AND ".join(where_parts)

        result = self._run_cli(
            "fabric", "search",
            "--where", where_clause,
            "--limit", str(limit),
            "--project", self._project,
            check=False,
        )

        # Parse the text output — we get human-readable format, not JSON
        # For now, return raw status
        return [{"raw": result.stdout}] if result.stdout else []

    def summary(
        self,
        project: str | None = None,
        group_by: str = "model",
    ) -> str:
        """Get aggregated usage summary as JSON string."""
        where_parts = ["domain=system_telemetry"]
        if project:
            where_parts.append(f"project={project}")

        where_clause = " AND ".join(where_parts)

        result = self._run_cli(
            "fabric", "aggregate",
            "--field", "cost_usd",
            "--op", "sum",
            "--group-by", group_by,
            "--where", where_clause,
            "--project", self._project,
            check=False,
        )

        return result.stdout.strip() if result.stdout else '{"result": 0}'

    def total_cost(self, project: str | None = None) -> float:
        """Get total cost for a project."""
        where_parts = ["domain=system_telemetry"]
        if project:
            where_parts.append(f"project={project}")

        where_clause = " AND ".join(where_parts)

        result = self._run_cli(
            "fabric", "aggregate",
            "--field", "cost_usd",
            "--op", "sum",
            "--where", where_clause,
            "--project", self._project,
            check=False,
        )

        try:
            data = json.loads(result.stdout.strip())
            return float(data.get("result", 0))
        except (json.JSONDecodeError, ValueError, AttributeError):
            return 0.0

    def export_json(self, project: str | None = None, limit: int = 100) -> str:
        """Export usage events as JSON."""
        events = self.query(project=project, limit=limit)
        return json.dumps(events, indent=2, default=str)
