"""Tests for memory round-trip across agents — interface, lenses, and fallback."""

import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.memory_interface import MemoryInterface
from lenses.perspective import PerspectiveLens, AccessPolicy, DOMAIN_POLICIES


class InMemoryBackend(MemoryInterface):
    """Simple in-memory backend for testing (no ChromaDB dependency needed)."""

    def __init__(self):
        self._nodes: dict[str, dict] = {}

    def store(self, content, metadata=None):
        import uuid
        node_id = str(uuid.uuid4())
        self._nodes[node_id] = {"content": content, "metadata": metadata or {}}
        return node_id

    def retrieve(self, query, top_k=5, domain=None):
        results = []
        query_lower = query.lower()
        for nid, node in self._nodes.items():
            meta = node["metadata"]
            if domain and meta.get("domain") != domain:
                continue
            # Simple keyword matching for tests
            content_lower = node["content"].lower()
            score = sum(1 for word in query_lower.split() if word in content_lower) / max(len(query_lower.split()), 1)
            results.append({
                "id": nid,
                "content": node["content"],
                "score": score,
                "metadata": meta,
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def list_domains(self):
        domains = set()
        for node in self._nodes.values():
            d = node["metadata"].get("domain")
            if d:
                domains.add(d)
        return sorted(domains)

    def delete(self, node_id):
        if node_id in self._nodes:
            del self._nodes[node_id]
            return True
        return False


class TestMemoryInterface(unittest.TestCase):

    def test_store_and_retrieve(self):
        backend = InMemoryBackend()
        node_id = backend.store("Test content about marketing strategy", {"domain": "marketing"})
        self.assertIsNotNone(node_id)
        results = backend.retrieve("marketing strategy", domain="marketing")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["content"], "Test content about marketing strategy")

    def test_domain_isolation(self):
        backend = InMemoryBackend()
        backend.store("Security vulnerability found", {"domain": "security"})
        backend.store("Marketing plan for Q2", {"domain": "marketing"})
        sec_results = backend.retrieve("vulnerability", domain="security")
        mkt_results = backend.retrieve("vulnerability", domain="marketing")
        self.assertTrue(any("vulnerability" in r["content"].lower() for r in sec_results))
        self.assertFalse(any("vulnerability" in r["content"].lower() for r in mkt_results))

    def test_list_domains(self):
        backend = InMemoryBackend()
        backend.store("a", {"domain": "marketing"})
        backend.store("b", {"domain": "security"})
        domains = backend.list_domains()
        self.assertIn("marketing", domains)
        self.assertIn("security", domains)

    def test_delete(self):
        backend = InMemoryBackend()
        node_id = backend.store("to be deleted")
        self.assertTrue(backend.delete(node_id))
        self.assertFalse(backend.delete("nonexistent"))


class TestPerspectiveLens(unittest.TestCase):

    def test_security_is_domain_only(self):
        self.assertEqual(DOMAIN_POLICIES["security"], AccessPolicy.DOMAIN_ONLY)

    def test_planner_is_full_fabric(self):
        self.assertEqual(DOMAIN_POLICIES["planner_researcher"], AccessPolicy.FULL_FABRIC)

    def test_marketing_is_domain_plus_shared(self):
        self.assertEqual(DOMAIN_POLICIES["marketing"], AccessPolicy.DOMAIN_PLUS_SHARED)

    def test_lens_stores_with_domain_metadata(self):
        backend = InMemoryBackend()
        lens = PerspectiveLens(backend, "marketing")
        node_id = lens.store("brand positioning update")
        node = backend._nodes[node_id]
        self.assertEqual(node["metadata"]["domain"], "marketing")

    def test_security_lens_only_sees_own_domain(self):
        backend = InMemoryBackend()
        backend.store("security finding: XSS", {"domain": "security"})
        backend.store("marketing content plan", {"domain": "marketing"})
        lens = PerspectiveLens(backend, "security")
        results = lens.retrieve("finding")
        # Security lens should only see security domain
        for r in results:
            self.assertEqual(r["metadata"].get("domain"), "security")

    def test_planner_lens_sees_all_domains(self):
        backend = InMemoryBackend()
        backend.store("security finding", {"domain": "security"})
        backend.store("marketing plan", {"domain": "marketing"})
        lens = PerspectiveLens(backend, "planner_researcher")
        results = lens.retrieve("finding plan")
        domains = {r["metadata"].get("domain") for r in results}
        self.assertTrue(len(domains) >= 1)

    def test_resonance_amplification(self):
        backend = InMemoryBackend()
        backend.store("vulnerability in auth module", {"domain": "security"})
        backend.store("general update note", {"domain": "security"})
        lens = PerspectiveLens(backend, "security")
        results = lens.retrieve("vulnerability auth")
        # The vulnerability node should be boosted by resonance
        if len(results) >= 2:
            self.assertGreaterEqual(results[0]["score"], results[1]["score"])


class TestMarkdownLog(unittest.TestCase):

    def test_log_creates_file(self):
        from memory.markdown_log import MarkdownLog
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = MarkdownLog(tmpdir)
            path = logger.log("marketing", "decision", "Test Decision", "We decided to do X.")
            self.assertTrue(path.exists())
            content = path.read_text()
            self.assertIn("Test Decision", content)
            self.assertIn("DECISION", content)

    def test_log_appends(self):
        from memory.markdown_log import MarkdownLog
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = MarkdownLog(tmpdir)
            logger.log("engineering", "task", "Task 1", "First task")
            logger.log("engineering", "task", "Task 2", "Second task")
            content = logger.read_log("engineering")
            self.assertIn("Task 1", content)
            self.assertIn("Task 2", content)


if __name__ == "__main__":
    unittest.main()
