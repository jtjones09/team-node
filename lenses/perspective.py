"""Perspective lenses — each agent views the shared fabric through a different resonance profile."""

from enum import Enum
from typing import Any

from memory.memory_interface import MemoryInterface


class AccessPolicy(Enum):
    """Domain isolation policies."""
    FULL_FABRIC = "full_fabric"            # Planner/Researcher only
    DOMAIN_PLUS_SHARED = "domain_plus_shared"  # Most agents
    DOMAIN_ONLY = "domain_only"            # Security


# Default resonance weights per domain — higher weight = more amplification
RESONANCE_PROFILES: dict[str, dict[str, float]] = {
    "marketing": {
        "positioning": 1.5, "messaging": 1.5, "audience": 1.3,
        "brand": 1.3, "content": 1.2, "linkedin": 1.2,
    },
    "sales": {
        "outreach": 1.5, "pipeline": 1.4, "partnership": 1.3,
        "prospect": 1.3, "deal": 1.2, "revenue": 1.2,
    },
    "engineer": {
        "implementation": 1.5, "dependency": 1.4, "performance": 1.3,
        "testing": 1.3, "code": 1.2, "deployment": 1.2,
    },
    "architect": {
        "system_design": 1.5, "specification": 1.4, "tradeoff": 1.3,
        "scalability": 1.3, "integration": 1.2, "pattern": 1.2,
    },
    "security": {
        "vulnerability": 1.5, "compliance": 1.4, "threat": 1.3,
        "attack_surface": 1.3, "cve": 1.2, "audit": 1.2,
    },
    "data_analytics": {
        "metrics": 1.5, "evidence": 1.4, "competitive": 1.3,
        "analysis": 1.3, "benchmark": 1.2, "trend": 1.2,
    },
    "planner_researcher": {
        "cross_domain": 1.3, "synthesis": 1.3, "research": 1.2,
        "strategy": 1.2, "connection": 1.2, "insight": 1.2,
    },
}

# Domain-to-policy mapping
DOMAIN_POLICIES: dict[str, AccessPolicy] = {
    "marketing": AccessPolicy.DOMAIN_PLUS_SHARED,
    "sales": AccessPolicy.DOMAIN_PLUS_SHARED,
    "engineer": AccessPolicy.DOMAIN_PLUS_SHARED,
    "architect": AccessPolicy.DOMAIN_PLUS_SHARED,
    "security": AccessPolicy.DOMAIN_ONLY,
    "data_analytics": AccessPolicy.DOMAIN_PLUS_SHARED,
    "planner_researcher": AccessPolicy.FULL_FABRIC,
}


class PerspectiveLens:
    """Wraps a MemoryInterface to filter and re-score results through a domain lens."""

    def __init__(self, memory: MemoryInterface, domain: str):
        self.memory = memory
        self.domain = domain
        self.policy = DOMAIN_POLICIES.get(domain, AccessPolicy.DOMAIN_PLUS_SHARED)
        self.resonance = RESONANCE_PROFILES.get(domain, {})

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Retrieve memories through this agent's perspective lens."""
        if self.policy == AccessPolicy.DOMAIN_ONLY:
            results = self.memory.retrieve(query, top_k=top_k * 2, domain=self.domain)
        elif self.policy == AccessPolicy.FULL_FABRIC:
            results = self.memory.retrieve(query, top_k=top_k * 2)
        else:
            # DOMAIN_PLUS_SHARED: get own domain + shared
            own = self.memory.retrieve(query, top_k=top_k, domain=self.domain)
            shared = self.memory.retrieve(query, top_k=top_k, domain="shared")
            seen_ids = set()
            results = []
            for node in own + shared:
                if node["id"] not in seen_ids:
                    seen_ids.add(node["id"])
                    results.append(node)

        # Apply resonance amplification
        for node in results:
            content_lower = node.get("content", "").lower()
            meta_str = str(node.get("metadata", {})).lower()
            combined = content_lower + " " + meta_str
            boost = 1.0
            for keyword, weight in self.resonance.items():
                if keyword.replace("_", " ") in combined or keyword in combined:
                    boost = max(boost, weight)
            node["score"] = node.get("score", 0.0) * boost

        results.sort(key=lambda n: n["score"], reverse=True)
        return results[:top_k]

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store a memory node in this agent's domain namespace."""
        meta = metadata or {}
        meta["domain"] = self.domain
        return self.memory.store(content, meta)
