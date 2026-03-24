"""Cross-session continuity — the thread that connects crew runs.

Each crew run stores a session_summary node and retrieves the previous one.
This gives the Planner context about what happened last time.

Session summaries form a chain: each references the previous via metadata.
Combined with weight decay, old sessions fade but never disappear.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ContinuityThread:
    """Manages session summaries in the fabric for cross-session continuity."""

    def __init__(self, binary_path: str | None = None, project: str = "default"):
        from config import FABRIC_BINARY
        self._binary = binary_path or FABRIC_BINARY
        self._project = project

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        """Run intent CLI command."""
        cmd = [self._binary, *args]
        try:
            return subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="CLI unavailable")

    def get_previous_session(self) -> str | None:
        """Get the most recent session summary for this project.

        Returns a human-readable summary string, or None if no previous session.
        """
        result = self._run_cli(
            "fabric", "search",
            "--where", f"kind=session_summary AND project={self._project}",
            "--limit", "1",
            "--project", self._project,
        )

        if result.returncode != 0 or not result.stdout.strip():
            return None

        # Parse the output to extract the want description
        lines = result.stdout.strip().split("\n")
        for line in lines:
            # Look for lines with node descriptions (contain " — ")
            if " — " in line:
                parts = line.split(" — ", 1)
                if len(parts) == 2:
                    return parts[1].strip()

        return None

    def store_session_summary(
        self,
        description: str,
        agents: list[str],
        models: list[str],
        cost: float,
        duration_ms: int,
        previous_node_id: str | None = None,
    ) -> str:
        """Store a session summary as a fabric node.

        Returns a description of what was stored.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        args = [
            "fabric", "add",
            "--want", f"Session summary for {self._project}: {description}",
            "--project", self._project,
            "--confidence", "0.9",
            "--meta", f"kind=session_summary",
            "--meta", f"project={self._project}",
            "--meta", f"agents={','.join(agents)}",
            "--meta", f"models={','.join(set(models))}",
            "--meta", f"cost={cost}",
            "--meta", f"duration_ms={duration_ms}",
            "--meta", f"timestamp={timestamp}",
        ]

        if previous_node_id:
            args.extend(["--meta", f"previous_session={previous_node_id}"])

        result = self._run_cli(*args)

        # Extract node ID from output
        node_id = ""
        if result.stdout:
            for line in result.stdout.split("\n"):
                if line.startswith("Added node:"):
                    node_id = line.split(":", 1)[1].strip()
                    break

        return node_id

    def build_context_injection(self) -> str:
        """Build a context string for the Planner based on previous sessions.

        Returns empty string if no previous sessions exist.
        """
        prev = self.get_previous_session()
        if not prev:
            return ""

        return (
            f"\n\n--- Previous Session Context ---\n"
            f"Last session: {prev}\n"
            f"Use this context to pick up where we left off. "
            f"Don't repeat work that was already done.\n"
            f"--- End Previous Session Context ---\n"
        )
