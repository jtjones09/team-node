"""ChromaDB fallback memory backend."""

import uuid
from typing import Any

import chromadb
from chromadb.config import Settings

from memory.memory_interface import MemoryInterface


class ChromaFallback(MemoryInterface):
    """ChromaDB-based memory backend. Used when Ecphory fabric isn't available."""

    def __init__(self, persist_dir: str):
        self._client = chromadb.Client(Settings(
            persist_directory=str(persist_dir),
            anonymized_telemetry=False,
            is_persistent=True,
        ))
        self._collection = self._client.get_or_create_collection(
            name="team_memory",
            metadata={"hnsw:space": "cosine"},
        )

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        node_id = str(uuid.uuid4())
        meta = metadata or {}
        # ChromaDB requires metadata values to be str, int, float, or bool
        safe_meta = {k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))}
        self._collection.add(
            ids=[node_id],
            documents=[content],
            metadatas=[safe_meta],
        )
        return node_id

    def retrieve(self, query: str, top_k: int = 5, domain: str | None = None) -> list[dict[str, Any]]:
        where = {"domain": domain} if domain else None
        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
        )
        nodes = []
        if results and results["ids"]:
            for i, node_id in enumerate(results["ids"][0]):
                nodes.append({
                    "id": node_id,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "score": 1.0 - (results["distances"][0][i] if results["distances"] else 0.0),
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })
        return nodes

    def list_domains(self) -> list[str]:
        all_meta = self._collection.get(include=["metadatas"])
        domains = set()
        if all_meta and all_meta["metadatas"]:
            for meta in all_meta["metadatas"]:
                if meta and "domain" in meta:
                    domains.add(meta["domain"])
        return sorted(domains)

    def delete(self, node_id: str) -> bool:
        try:
            self._collection.delete(ids=[node_id])
            return True
        except Exception:
            return False
