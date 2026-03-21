"""Temporary JSON-based fabric bridge until intent-node CLI supports add/search commands.

Reads and writes a JSON file in a format compatible with the Ecphory fabric's JsonFileStore.
Uses simple text matching for search until CLI resonance is available.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory.memory_interface import MemoryInterface


class FabricBridge(MemoryInterface):
    """JSON file-based memory backend that mirrors the Ecphory fabric node format.

    This is a TEMPORARY bridge. When the intent-node CLI supports
    `intent fabric add` and `intent fabric search`, swap to subprocess calls.
    """

    def __init__(self, fabric_file: str | Path):
        self._fabric_file = Path(fabric_file)
        self._fabric_file.parent.mkdir(parents=True, exist_ok=True)
        self._nodes: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self):
        """Load nodes from the JSON file."""
        if self._fabric_file.exists() and self._fabric_file.stat().st_size > 0:
            with open(self._fabric_file) as f:
                data = json.load(f)
            # DECISION: Support both list-of-nodes and dict-of-nodes formats.
            # The Ecphory fabric uses a list; we index by ID for fast lookup.
            if isinstance(data, list):
                self._nodes = {n["id"]: n for n in data if "id" in n}
            elif isinstance(data, dict):
                if "nodes" in data:
                    self._nodes = {n["id"]: n for n in data["nodes"] if "id" in n}
                else:
                    self._nodes = data

    def _save(self):
        """Persist nodes to the JSON file."""
        with open(self._fabric_file, "w") as f:
            json.dump(list(self._nodes.values()), f, indent=2, default=str)

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        node_id = str(uuid.uuid4())
        node = {
            "id": node_id,
            "content": content,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._nodes[node_id] = node
        self._save()
        return node_id

    def retrieve(self, query: str, top_k: int = 5, domain: str | None = None) -> list[dict[str, Any]]:
        """Search nodes by simple text matching.

        DECISION: Using keyword overlap scoring as bootstrap until
        intent-node CLI resonance/embedding search is available.
        """
        query_words = set(query.lower().split())
        results = []

        for node in self._nodes.values():
            meta = node.get("metadata", {})
            if domain and meta.get("domain") != domain:
                continue

            content_lower = node.get("content", "").lower()
            content_words = set(content_lower.split())
            meta_str = str(meta).lower()

            # Score: fraction of query words found in content + metadata
            matches = sum(1 for w in query_words if w in content_lower or w in meta_str)
            score = matches / max(len(query_words), 1)

            if score > 0:
                results.append({
                    "id": node["id"],
                    "content": node.get("content", ""),
                    "score": score,
                    "metadata": meta,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def list_domains(self) -> list[str]:
        domains = set()
        for node in self._nodes.values():
            d = node.get("metadata", {}).get("domain")
            if d:
                domains.add(d)
        return sorted(domains)

    def delete(self, node_id: str) -> bool:
        if node_id in self._nodes:
            del self._nodes[node_id]
            self._save()
            return True
        return False
