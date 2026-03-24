"""Tests for fabric-aware agent identity."""

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.agent_identity import AgentIdentity

FABRIC_BINARY = str(Path.home() / "projects" / "ecphory" / "target" / "release" / "intent")
TEST_PROJECT = "_test_agent_identity"


def cleanup():
    test_dir = Path.home() / ".ecphory" / TEST_PROJECT
    if test_dir.exists():
        shutil.rmtree(test_dir)


class TestAgentIdentity:
    def setup_method(self):
        cleanup()
        if not Path(FABRIC_BINARY).exists():
            import pytest
            pytest.skip("Fabric binary not found")

    def teardown_method(self):
        cleanup()

    def test_create_identity_first_run(self):
        ai = AgentIdentity(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        created = ai.ensure_identity("marketing", "Expert in content strategy and SEO")
        assert created is True

    def test_identity_not_duplicated(self):
        ai = AgentIdentity(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        ai.ensure_identity("marketing", "Expert in content strategy")
        created = ai.ensure_identity("marketing", "Expert in content strategy")
        assert created is False

    def test_store_reflection(self):
        ai = AgentIdentity(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        node_id = ai.store_reflection(
            agent_name="marketing",
            project="reallycoons",
            description="Completed website analysis. Key finding: 22 external scripts on Wix site.",
        )
        assert node_id

    def test_get_recent_reflections(self):
        ai = AgentIdentity(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        ai.store_reflection("marketing", TEST_PROJECT, "Analyzed website performance")
        ai.store_reflection("marketing", TEST_PROJECT, "Produced two-plan proposal")
        reflections = ai.get_recent_reflections("marketing")
        assert len(reflections) >= 1

    def test_build_context_adds_reflections(self):
        ai = AgentIdentity(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        ai.store_reflection("marketing", TEST_PROJECT, "Analyzed homepage SEO")
        context = ai.build_context_for_agent("marketing", "I am the marketing specialist.")
        assert "marketing specialist" in context
        # May or may not include history depending on search results
        assert len(context) > len("I am the marketing specialist.")

    def test_reflections_from_different_agents_separate(self):
        ai = AgentIdentity(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        ai.store_reflection("marketing", TEST_PROJECT, "Marketing did X")
        ai.store_reflection("engineer", TEST_PROJECT, "Engineer did Y")
        marketing_refs = ai.get_recent_reflections("marketing")
        engineer_refs = ai.get_recent_reflections("engineer")
        # Each should only see their own reflections
        for r in marketing_refs:
            assert "Engineer" not in r
        for r in engineer_refs:
            assert "Marketing" not in r
