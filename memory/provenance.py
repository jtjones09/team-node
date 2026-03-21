"""Provenance tracking — records what the team did, why, and what led to what."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProvenanceTracker:
    """Tracks agent outputs and decisions with full provenance chains.

    Stores entries both as structured JSON (for machine consumption)
    and as a readable markdown log (for human review).
    """

    def __init__(self, project_dir: str | Path):
        self._project_dir = Path(project_dir)
        self._project_dir.mkdir(parents=True, exist_ok=True)
        self._json_file = self._project_dir / "provenance.json"
        self._md_file = self._project_dir / "provenance.md"
        self._entries: list[dict[str, Any]] = []
        self._load()

    def _load(self):
        if self._json_file.exists() and self._json_file.stat().st_size > 0:
            with open(self._json_file) as f:
                self._entries = json.load(f)

    def _save(self):
        with open(self._json_file, "w") as f:
            json.dump(self._entries, f, indent=2, default=str)

    def _append_markdown(self, entry: dict[str, Any]):
        etype = entry["type"]
        agent = entry["agent"]
        ts = entry["timestamp"]

        md = f"\n## [{etype.upper()}] {agent}\n"
        md += f"**Timestamp**: {ts}\n"
        md += f"**Project**: {entry.get('project', 'unknown')}\n\n"

        if etype == "agent_output":
            md += f"**Goal**: {entry.get('goal', '')}\n\n"
            md += f"**Output Summary**:\n{entry.get('output_summary', '')}\n\n"
            md += f"**Confidence**: {entry.get('confidence', 'N/A')}\n"
            context = entry.get("context_used", [])
            if context:
                md += f"**Context Used**: {', '.join(context)}\n"
        elif etype == "decision":
            md += f"**Decision**: {entry.get('decision', '')}\n\n"
            md += f"**Reasoning**: {entry.get('reasoning', '')}\n\n"
            alts = entry.get("alternatives_considered", [])
            if alts:
                md += f"**Alternatives**: {', '.join(alts)}\n"

        md += "\n---\n"

        with open(self._md_file, "a") as f:
            if not self._md_file.exists() or self._md_file.stat().st_size == 0:
                f.write("# Provenance Log\n\n---\n")
            f.write(md)

    def record_output(
        self,
        agent: str,
        project: str,
        goal: str,
        output: str,
        context_used: list[str] | None = None,
        confidence: float = 0.85,
    ) -> dict[str, Any]:
        """Record an agent output with provenance metadata."""
        entry = {
            "type": "agent_output",
            "agent": agent,
            "project": project,
            "goal": goal,
            "output_summary": output[:500],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context_used": context_used or [],
            "confidence": confidence,
        }
        self._entries.append(entry)
        self._save()
        self._append_markdown(entry)
        return entry

    def record_decision(
        self,
        agent: str,
        project: str,
        decision: str,
        reasoning: str,
        alternatives: list[str] | None = None,
    ) -> dict[str, Any]:
        """Record a decision with rationale and alternatives considered."""
        entry = {
            "type": "decision",
            "agent": agent,
            "project": project,
            "decision": decision,
            "reasoning": reasoning,
            "alternatives_considered": alternatives or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._entries.append(entry)
        self._save()
        self._append_markdown(entry)
        return entry

    def get_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get the most recent provenance entries."""
        return self._entries[-limit:]
