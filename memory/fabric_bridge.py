"""Python wrapper around the Ecphory Rust binary for fabric memory operations."""

import json
import subprocess
import uuid
from typing import Any

from memory.memory_interface import MemoryInterface


class FabricBridge(MemoryInterface):
    """Calls the Ecphory fabric CLI via subprocess.

    Expects the binary to support:
        ecphory add --data <json> --file <fabric_file>
        ecphory resonate --query <text> --top-k <n> --file <fabric_file>
        ecphory delete --id <id> --file <fabric_file>
        ecphory list-domains --file <fabric_file>
    """

    def __init__(self, binary_path: str, fabric_file: str):
        self._binary = binary_path
        self._fabric_file = fabric_file

    def _run(self, *args: str) -> dict[str, Any]:
        cmd = [self._binary, *args, "--file", str(self._fabric_file)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"Ecphory CLI error: {result.stderr.strip()}")
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        node_id = str(uuid.uuid4())
        payload = json.dumps({"id": node_id, "content": content, "metadata": metadata or {}})
        self._run("add", "--data", payload)
        return node_id

    def retrieve(self, query: str, top_k: int = 5, domain: str | None = None) -> list[dict[str, Any]]:
        args = ["resonate", "--query", query, "--top-k", str(top_k)]
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
        result = self._run("list-domains")
        return result.get("domains", [])

    def delete(self, node_id: str) -> bool:
        try:
            self._run("delete", "--id", node_id)
            return True
        except RuntimeError:
            return False
