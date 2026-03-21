"""Abstract interface for memory backends (Ecphory fabric and ChromaDB fallback)."""

from abc import ABC, abstractmethod
from typing import Any


class MemoryInterface(ABC):
    """Common interface for all memory backends."""

    @abstractmethod
    def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store a memory node. Returns the node ID."""

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5, domain: str | None = None) -> list[dict[str, Any]]:
        """Retrieve memory nodes matching a query.

        Args:
            query: The search query.
            top_k: Maximum number of results.
            domain: Optional domain filter (e.g., "marketing", "security").

        Returns:
            List of dicts with at least "id", "content", "score", "metadata".
        """

    @abstractmethod
    def list_domains(self) -> list[str]:
        """List all domain namespaces in the memory store."""

    @abstractmethod
    def delete(self, node_id: str) -> bool:
        """Delete a memory node by ID. Returns True if deleted."""
