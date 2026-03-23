"""API usage tracker — logs every LLM call with tags for dashboarding.

Stores usage data in a local SQLite database at
~/.ecphory/usage/teamnode_usage.db

Every API call gets tagged with:
  - project (reallycoons, aios, etc.)
  - domain (marketing, engineer, planner_researcher, etc.)
  - model (haiku, sonnet, opus)
  - tier (fast, standard, premium)
  - operation type (research, execution, tool_call, etc.)
  - custom tags (anything you want)

The schema is intentionally simple and composable:
  - usage_events: one row per API call
  - usage_tags: many-to-many tag table

Add whatever tags you want at any time. The dashboard reads
them dynamically.
"""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Default DB location — lives alongside the fabric data
DEFAULT_DB_PATH = Path.home() / ".ecphory" / "usage" / "teamnode_usage.db"


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
    operation: str = ""  # research, execution, tool_call, routing, etc.
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    success: bool = True
    error: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# Cost per million tokens (input/output) as of March 2026
MODEL_COSTS = {
    "anthropic/claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
    "anthropic/claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "anthropic/claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    # Aliases for display
    "haiku": {"input": 0.25, "output": 1.25},
    "sonnet": {"input": 3.0, "output": 15.0},
    "opus": {"input": 15.0, "output": 75.0},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for an API call."""
    costs = MODEL_COSTS.get(model)
    if not costs:
        # Try matching by substring
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


class UsageTracker:
    """SQLite-backed usage tracking with composable tags."""

    def __init__(self, db_path: Path | str | None = None):
        self._db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS usage_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    project TEXT DEFAULT '',
                    domain TEXT DEFAULT '',
                    agent TEXT DEFAULT '',
                    model TEXT DEFAULT '',
                    tier TEXT DEFAULT '',
                    operation TEXT DEFAULT '',
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0.0,
                    duration_ms INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 1,
                    error TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS usage_tags (
                    event_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES usage_events(event_id),
                    PRIMARY KEY (event_id, tag)
                );

                CREATE INDEX IF NOT EXISTS idx_events_project ON usage_events(project);
                CREATE INDEX IF NOT EXISTS idx_events_domain ON usage_events(domain);
                CREATE INDEX IF NOT EXISTS idx_events_model ON usage_events(model);
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON usage_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_tags_tag ON usage_tags(tag);
            """)

    @contextmanager
    def _conn(self):
        """Context manager for DB connections."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def log(self, event: UsageEvent) -> str:
        """Log a usage event. Returns the event_id."""
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

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO usage_events
                (event_id, timestamp, project, domain, agent, model, tier,
                 operation, input_tokens, output_tokens, total_tokens,
                 cost_usd, duration_ms, success, error, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.event_id, event.timestamp, event.project,
                    event.domain, event.agent, event.model, event.tier,
                    event.operation, event.input_tokens, event.output_tokens,
                    event.total_tokens, event.cost_usd, event.duration_ms,
                    1 if event.success else 0, event.error,
                    json.dumps(event.metadata),
                ),
            )
            for tag in event.tags:
                conn.execute(
                    "INSERT OR IGNORE INTO usage_tags (event_id, tag) VALUES (?, ?)",
                    (event.event_id, tag),
                )
        return event.event_id

    def query(
        self,
        project: str | None = None,
        domain: str | None = None,
        model: str | None = None,
        tag: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query usage events with filters."""
        conditions = []
        params = []

        if project:
            conditions.append("e.project = ?")
            params.append(project)
        if domain:
            conditions.append("e.domain = ?")
            params.append(domain)
        if model:
            conditions.append("e.model LIKE ?")
            params.append(f"%{model}%")
        if since:
            conditions.append("e.timestamp >= ?")
            params.append(since)
        if until:
            conditions.append("e.timestamp <= ?")
            params.append(until)
        if tag:
            conditions.append("e.event_id IN (SELECT event_id FROM usage_tags WHERE tag = ?)")
            params.append(tag)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(
                f"""SELECT e.*, GROUP_CONCAT(t.tag) as tags
                FROM usage_events e
                LEFT JOIN usage_tags t ON e.event_id = t.event_id
                {where}
                GROUP BY e.event_id
                ORDER BY e.timestamp DESC
                LIMIT ?""",
                params,
            ).fetchall()

        return [dict(r) for r in rows]

    def summary(
        self,
        project: str | None = None,
        since: str | None = None,
        group_by: str = "model",
    ) -> list[dict]:
        """Get aggregated usage summary."""
        conditions = []
        params = []

        if project:
            conditions.append("project = ?")
            params.append(project)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        valid_groups = {"model", "domain", "project", "tier", "operation", "agent"}
        if group_by not in valid_groups:
            group_by = "model"

        with self._conn() as conn:
            rows = conn.execute(
                f"""SELECT {group_by},
                    COUNT(*) as call_count,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_usd) as total_cost_usd,
                    AVG(duration_ms) as avg_duration_ms
                FROM usage_events
                {where}
                GROUP BY {group_by}
                ORDER BY total_cost_usd DESC""",
                params,
            ).fetchall()

        return [dict(r) for r in rows]

    def export_json(self, **kwargs) -> str:
        """Export query results as JSON (for dashboard consumption)."""
        events = self.query(**kwargs)
        return json.dumps(events, indent=2, default=str)

    def get_all_tags(self) -> list[str]:
        """Get all unique tags in the database."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT tag FROM usage_tags ORDER BY tag"
            ).fetchall()
        return [r["tag"] for r in rows]

    def get_all_projects(self) -> list[str]:
        """Get all unique projects."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT project FROM usage_events WHERE project != '' ORDER BY project"
            ).fetchall()
        return [r["project"] for r in rows]
