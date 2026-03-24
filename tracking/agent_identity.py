"""Fabric-aware agent identity — agents remember who they are and what they've done.

Each agent has an identity node (created on first run) and accumulates
reflection nodes after each run. On subsequent runs, the agent receives
its recent reflections as additional context.

Identity IS a fabric node. History IS fabric nodes.
There is no separate agent profile system.
"""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AgentIdentity:
    """Manages agent identity and reflection nodes in the fabric."""

    def __init__(self, binary_path: str | None = None, project: str = "default"):
        from config import FABRIC_BINARY
        self._binary = binary_path or FABRIC_BINARY
        self._project = project

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [self._binary, *args]
        try:
            return subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

    def ensure_identity(self, agent_name: str, backstory: str) -> bool:
        """Ensure an agent identity node exists. Returns True if created, False if already exists."""
        # Check if identity node already exists
        result = self._run_cli(
            "fabric", "search",
            "--where", f"kind=agent_identity AND agent={agent_name}",
            "--limit", "1",
            "--project", self._project,
        )

        if result.stdout and agent_name in result.stdout and "agent_identity" not in result.stdout.split("No matching")[0] if "No matching" in result.stdout else True:
            # Check more carefully
            if "No matching" in result.stdout:
                pass  # Need to create
            elif agent_name in result.stdout:
                return False  # Already exists

        # Create identity node
        identity_desc = backstory[:200] if len(backstory) > 200 else backstory
        self._run_cli(
            "fabric", "add",
            "--want", f"I am the {agent_name.replace('_', ' ').title()} agent. {identity_desc}",
            "--project", self._project,
            "--confidence", "0.95",
            "--meta", "kind=agent_identity",
            "--meta", f"agent={agent_name}",
            "--meta", f"created={datetime.now(timezone.utc).isoformat()}",
        )
        return True

    def store_reflection(
        self,
        agent_name: str,
        project: str,
        description: str,
    ) -> str:
        """Store an agent reflection after a run."""
        timestamp = datetime.now(timezone.utc).isoformat()

        result = self._run_cli(
            "fabric", "add",
            "--want", f"{agent_name.replace('_', ' ').title()} agent: {description}",
            "--project", self._project,
            "--confidence", "0.8",
            "--meta", "kind=agent_reflection",
            "--meta", f"agent={agent_name}",
            "--meta", f"project={project}",
            "--meta", f"timestamp={timestamp}",
        )

        node_id = ""
        if result.stdout:
            for line in result.stdout.split("\n"):
                if line.startswith("Added node:"):
                    node_id = line.split(":", 1)[1].strip()
                    break
        return node_id

    def get_recent_reflections(self, agent_name: str, limit: int = 3) -> list[str]:
        """Get recent reflections for an agent+project combination."""
        result = self._run_cli(
            "fabric", "search",
            "--where", f"kind=agent_reflection AND agent={agent_name} AND project={self._project}",
            "--limit", str(limit),
            "--project", self._project,
        )

        reflections = []
        if result.stdout:
            for line in result.stdout.split("\n"):
                if " — " in line:
                    parts = line.split(" — ", 1)
                    if len(parts) == 2:
                        reflections.append(parts[1].strip())

        return reflections

    def build_context_for_agent(self, agent_name: str, backstory: str) -> str:
        """Build enriched context for an agent based on identity and reflections.

        Returns the original backstory plus recent reflections.
        """
        # Ensure identity exists
        self.ensure_identity(agent_name, backstory)

        # Get recent reflections
        reflections = self.get_recent_reflections(agent_name)

        if not reflections:
            return backstory

        reflection_text = "\n".join(f"- {r}" for r in reflections)
        return (
            f"{backstory}\n\n"
            f"--- Your Recent History ---\n"
            f"{reflection_text}\n"
            f"Use this history to build on prior work. Don't repeat what's already done.\n"
            f"--- End History ---"
        )
