"""Ecphory Fabric bridge — calls intent-node CLI for real resonance retrieval.

This replaces the temporary JSON file bridge. All memory operations now go
through the Ecphory fabric via subprocess calls to `intent fabric` commands,
getting real TF-IDF resonance scoring, confidence surfaces, and domain isolation.
"""

import json
import subprocess
from pathlib import Path
from typing import Any

from memory.memory_interface import MemoryInterface


class FabricBridge(MemoryInterface):
    """Calls the Ecphory fabric CLI for all memory operations.

    Uses `intent fabric add`, `intent fabric search`, etc.
    The binary must be built: `cd ~/projects/intent-node && cargo build --release`

    DECISION: All subprocess calls use cwd=intent-node directory so that
    fabric data files (data/projects/{project}/fabric.json) resolve correctly
    regardless of where TeamNode is run from.
    """

    def __init__(self, binary_path: str, project: str | None = None):
        self._binary = str(binary_path)
        self._project = project
        # The working directory for all CLI calls is the intent-node repo root
        # (two levels up from target/release/intent)
        self._cwd = str(Path(binary_path).resolve().parent.parent.parent)
        self._verify_binary()

    def _verify_binary(self):
        """Check that the fabric binary exists and runs."""
        try:
            result = subprocess.run(
                [self._binary, "--help"],
                capture_output=True, text=True, timeout=10,
                cwd=self._cwd,
            )
            if result.returncode not in (0, 1):
                raise RuntimeError(f"Fabric binary check failed: {result.stderr.strip()}")
        except FileNotFoundError:
            raise RuntimeError(
                f"Fabric binary not found at {self._binary}\n"
                f"Build it: cd ~/projects/intent-node && cargo build --release"
            )

    def _run(self, *args: str) -> dict[str, Any]:
        """Run a fabric CLI command and return parsed JSON output."""
        cmd = [self._binary, "fabric", *args, "--json"]
        if self._project:
            cmd.extend(["--project", self._project])

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            cwd=self._cwd,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"Ecphory CLI error: {stderr}")

        stdout = result.stdout.strip()
        if not stdout:
            return {}

        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            for line in stdout.split("\n"):
                line = line.strip()
                if line.startswith("{") or line.startswith("["):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
            raise RuntimeError(f"Could not parse JSON from fabric output: {stdout}")

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store a node in the Ecphory fabric."""
        meta = metadata or {}
        domain = meta.get("domain", "")

        args = ["add", "--want", content]
        if domain:
            args.extend(["--domain", domain])

        result = self._run(*args)
        return result.get("id", "")

    def retrieve(self, query: str, top_k: int = 5, domain: str | None = None) -> list[dict[str, Any]]:
        """Search the fabric using resonance matching."""
        args = ["search", "--query", query, "--top-k", str(top_k)]
        if domain:
            args.extend(["--domain", domain])

        result = self._run(*args)
        nodes = result.get("nodes", [])

        return [
            {
                "id": n.get("id", ""),
                "content": n.get("content", ""),
                "score": n.get("score", 0.0),
                "metadata": n.get("metadata", {}),
            }
            for n in nodes
        ]

    def list_domains(self) -> list[str]:
        """List all domain namespaces in the fabric."""
        result = self._run("list")
        nodes = result.get("nodes", [])
        domains = set()
        for n in nodes:
            d = n.get("domain", "")
            if d:
                domains.add(d)
        return sorted(domains)

    def delete(self, node_id: str) -> bool:
        """Delete a node from the fabric."""
        return False
