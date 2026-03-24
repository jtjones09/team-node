"""Tests for cross-session continuity."""

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.continuity import ContinuityThread

FABRIC_BINARY = str(Path.home() / "projects" / "ecphory" / "target" / "release" / "intent")
TEST_PROJECT = "_test_continuity"


def cleanup():
    test_dir = Path.home() / ".ecphory" / TEST_PROJECT
    if test_dir.exists():
        shutil.rmtree(test_dir)


class TestContinuityThread:
    def setup_method(self):
        cleanup()
        if not Path(FABRIC_BINARY).exists():
            import pytest
            pytest.skip("Fabric binary not found")

    def teardown_method(self):
        cleanup()

    def test_no_previous_session_returns_none(self):
        ct = ContinuityThread(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        prev = ct.get_previous_session()
        assert prev is None

    def test_store_session_summary(self):
        ct = ContinuityThread(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        node_id = ct.store_session_summary(
            description="Analyzed reallycoons.com, stored site assessment",
            agents=["planner_researcher", "marketing"],
            models=["sonnet"],
            cost=0.42,
            duration_ms=45000,
        )
        assert node_id  # Should return non-empty

    def test_second_run_finds_previous_session(self):
        ct = ContinuityThread(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        # Store first session
        ct.store_session_summary(
            description="First session: analyzed website",
            agents=["planner_researcher"],
            models=["sonnet"],
            cost=0.20,
            duration_ms=30000,
        )
        # Query for previous session
        prev = ct.get_previous_session()
        assert prev is not None
        assert "First session" in prev

    def test_build_context_injection_empty_on_first_run(self):
        ct = ContinuityThread(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        context = ct.build_context_injection()
        assert context == ""

    def test_build_context_injection_has_content_after_run(self):
        ct = ContinuityThread(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        ct.store_session_summary(
            description="Completed marketing analysis",
            agents=["marketing"],
            models=["sonnet"],
            cost=0.10,
            duration_ms=20000,
        )
        context = ct.build_context_injection()
        assert "Previous Session Context" in context
        assert "Completed marketing analysis" in context

    def test_session_chain_references_previous(self):
        ct = ContinuityThread(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        first_id = ct.store_session_summary(
            description="First run",
            agents=["planner_researcher"],
            models=["sonnet"],
            cost=0.1,
            duration_ms=10000,
        )
        second_id = ct.store_session_summary(
            description="Second run",
            agents=["marketing"],
            models=["sonnet"],
            cost=0.2,
            duration_ms=15000,
            previous_node_id=first_id,
        )
        assert second_id
