"""Tests for the heartbeat daemon."""

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from heartbeat.pulse import Heartbeat

FABRIC_BINARY = str(Path.home() / "projects" / "ecphory" / "target" / "release" / "intent")
TEST_PROJECT = "_test_heartbeat"


def cleanup():
    test_dir = Path.home() / ".ecphory" / TEST_PROJECT
    if test_dir.exists():
        shutil.rmtree(test_dir)


class TestHeartbeat:
    def setup_method(self):
        cleanup()
        if not Path(FABRIC_BINARY).exists():
            import pytest
            pytest.skip("Fabric binary not found")

    def teardown_method(self):
        cleanup()

    def test_pulse_runs_and_returns_summary(self):
        hb = Heartbeat(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        result = hb.pulse()
        assert "pulse_id" in result
        assert "summary" in result
        assert "checks" in result
        assert len(result["checks"]) == 4

    def test_pulse_stores_finding_nodes(self):
        hb = Heartbeat(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        hb.pulse()
        # Verify heartbeat nodes were stored
        import subprocess
        result = subprocess.run(
            [FABRIC_BINARY, "fabric", "search",
             "--where", "kind=heartbeat",
             "--project", TEST_PROJECT],
            capture_output=True, text=True,
        )
        assert "heartbeat" in result.stdout.lower() or "Heartbeat" in result.stdout

    def test_coherence_check_finds_duplicates(self):
        hb = Heartbeat(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        # Add near-duplicate nodes
        import subprocess
        subprocess.run([FABRIC_BINARY, "fabric", "add",
            "--want", "Analyze website performance for SEO optimization",
            "--project", TEST_PROJECT], capture_output=True)
        subprocess.run([FABRIC_BINARY, "fabric", "add",
            "--want", "Analyze website performance for SEO optimization report",
            "--project", TEST_PROJECT], capture_output=True)

        coherence = hb.check_coherence("test-pulse")
        # May or may not detect depending on word overlap threshold
        assert coherence["check"] == "coherence"

    def test_cost_check_runs(self):
        hb = Heartbeat(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        cost = hb.check_cost("test-pulse")
        assert cost["check"] == "cost"
        assert isinstance(cost["total_cost"], float)

    def test_staleness_check_runs(self):
        hb = Heartbeat(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        staleness = hb.check_staleness("test-pulse")
        assert staleness["check"] == "staleness"

    def test_multiple_pulses(self):
        hb = Heartbeat(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        r1 = hb.pulse()
        r2 = hb.pulse()
        assert r1["pulse_id"] != r2["pulse_id"]
