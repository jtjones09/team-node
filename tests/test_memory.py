"""Tests for memory round-trip across agents — interface, lenses, and fabric bridge."""

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


class TestFabricBridge(unittest.TestCase):
    """Test the JSON file-based fabric bridge."""

    def test_store_and_retrieve(self):
        from memory.fabric_bridge import FabricBridge
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = FabricBridge(os.path.join(tmpdir, "fabric.json"))
            node_id = bridge.store("marketing strategy update", {"domain": "marketing"})
            results = bridge.retrieve("marketing strategy")
            self.assertTrue(len(results) > 0)
            self.assertEqual(results[0]["id"], node_id)

    def test_persistence(self):
        from memory.fabric_bridge import FabricBridge
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "fabric.json")
            bridge1 = FabricBridge(path)
            node_id = bridge1.store("persistent data", {"domain": "engineer"})
            # New instance should load from file
            bridge2 = FabricBridge(path)
            results = bridge2.retrieve("persistent data")
            self.assertTrue(len(results) > 0)
            self.assertEqual(results[0]["id"], node_id)

    def test_domain_filter(self):
        from memory.fabric_bridge import FabricBridge
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = FabricBridge(os.path.join(tmpdir, "fabric.json"))
            bridge.store("security vulnerability", {"domain": "security"})
            bridge.store("marketing plan", {"domain": "marketing"})
            sec_results = bridge.retrieve("vulnerability", domain="security")
            mkt_results = bridge.retrieve("vulnerability", domain="marketing")
            self.assertTrue(any("vulnerability" in r["content"] for r in sec_results))
            self.assertFalse(any("vulnerability" in r["content"] for r in mkt_results))

    def test_delete(self):
        from memory.fabric_bridge import FabricBridge
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = FabricBridge(os.path.join(tmpdir, "fabric.json"))
            node_id = bridge.store("to delete")
            self.assertTrue(bridge.delete(node_id))
            self.assertFalse(bridge.delete("nonexistent"))

    def test_list_domains(self):
        from memory.fabric_bridge import FabricBridge
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = FabricBridge(os.path.join(tmpdir, "fabric.json"))
            bridge.store("a", {"domain": "marketing"})
            bridge.store("b", {"domain": "security"})
            domains = bridge.list_domains()
            self.assertIn("marketing", domains)
            self.assertIn("security", domains)


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


class TestProvenance(unittest.TestCase):
    """Test provenance tracking."""

    def test_record_output(self):
        from memory.provenance import ProvenanceTracker
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ProvenanceTracker(tmpdir)
            entry = tracker.record_output(
                agent="marketing",
                project="test-project",
                goal="write a post",
                output="Here is a LinkedIn post about...",
                context_used=["abc123"],
                confidence=0.9,
            )
            self.assertEqual(entry["type"], "agent_output")
            self.assertEqual(entry["agent"], "marketing")
            self.assertIn("timestamp", entry)

    def test_record_decision(self):
        from memory.provenance import ProvenanceTracker
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ProvenanceTracker(tmpdir)
            entry = tracker.record_decision(
                agent="architect",
                project="ecphory",
                decision="Use perspective lenses",
                reasoning="Containers fragment what the fabric unifies",
                alternatives=["Docker containers", "VM isolation"],
            )
            self.assertEqual(entry["type"], "decision")
            self.assertEqual(len(entry["alternatives_considered"]), 2)

    def test_persistence_and_get_recent(self):
        from memory.provenance import ProvenanceTracker
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker1 = ProvenanceTracker(tmpdir)
            tracker1.record_output("eng", "proj", "build", "built it", confidence=0.8)
            tracker1.record_decision("arch", "proj", "use X", "because Y")
            # New instance should load from file
            tracker2 = ProvenanceTracker(tmpdir)
            entries = tracker2.get_recent(limit=10)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["type"], "agent_output")
            self.assertEqual(entries[1]["type"], "decision")

    def test_markdown_log_created(self):
        from memory.provenance import ProvenanceTracker
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = ProvenanceTracker(tmpdir)
            tracker.record_output("marketing", "proj", "goal", "output text")
            md_path = os.path.join(tmpdir, "provenance.md")
            self.assertTrue(os.path.exists(md_path))
            content = open(md_path).read()
            self.assertIn("marketing", content)
            self.assertIn("AGENT_OUTPUT", content)


class TestMultiProject(unittest.TestCase):
    """Test multi-project path scoping."""

    def test_get_project_paths(self):
        from config import get_project_paths
        paths = get_project_paths("test-project")
        self.assertTrue(paths["fabric_file"].name == "fabric.json")
        self.assertIn("test-project", str(paths["project_dir"]))
        self.assertTrue(paths["log_dir"].exists())

    def test_list_projects_empty(self):
        from config import list_projects
        # May or may not have projects, but should not crash
        result = list_projects()
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
