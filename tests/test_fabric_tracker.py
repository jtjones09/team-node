"""Tests for fabric-native usage tracker."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.fabric_tracker import FabricTracker, UsageEvent, estimate_cost


# Use the actual binary for integration tests
FABRIC_BINARY = str(Path.home() / "projects" / "ecphory" / "target" / "release" / "intent")
TEST_PROJECT = "_test_fabric_tracker"


def cleanup_test_project():
    """Remove test project data."""
    test_dir = Path.home() / ".ecphory" / TEST_PROJECT
    if test_dir.exists():
        import shutil
        shutil.rmtree(test_dir)


class TestEstimateCost:
    def test_haiku_cost(self):
        cost = estimate_cost("haiku", 1_000_000, 1_000_000)
        assert abs(cost - 1.50) < 0.01  # $0.25 input + $1.25 output

    def test_sonnet_cost(self):
        cost = estimate_cost("sonnet", 1_000_000, 1_000_000)
        assert abs(cost - 18.0) < 0.01  # $3 input + $15 output

    def test_unknown_model_cost(self):
        cost = estimate_cost("unknown_model", 1000, 1000)
        assert cost == 0.0

    def test_substring_matching(self):
        cost = estimate_cost("anthropic/claude-sonnet-4-20250514", 1_000_000, 0)
        assert cost > 0


class TestUsageEvent:
    def test_default_event(self):
        event = UsageEvent()
        assert event.cost_usd == 0.0
        assert event.success is True

    def test_event_with_data(self):
        event = UsageEvent(
            project="reallycoons",
            agent="marketing",
            model="sonnet",
            operation="research",
            input_tokens=500,
            output_tokens=1000,
        )
        assert event.project == "reallycoons"
        assert event.agent == "marketing"


class TestFabricTracker:
    """Integration tests using the real fabric CLI."""

    def setup_method(self):
        cleanup_test_project()
        if not Path(FABRIC_BINARY).exists():
            import pytest
            pytest.skip(f"Fabric binary not found at {FABRIC_BINARY}")

    def teardown_method(self):
        cleanup_test_project()

    def test_log_event_creates_node(self):
        tracker = FabricTracker(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        event = UsageEvent(
            project="reallycoons",
            agent="marketing",
            model="sonnet",
            operation="research",
            input_tokens=500,
            output_tokens=1000,
            cost_usd=0.018,
        )
        event_id = tracker.log(event)
        assert event_id  # Should return non-empty event ID

        # Verify the node exists in the fabric
        result = subprocess.run(
            [FABRIC_BINARY, "fabric", "search",
             "--where", "domain=system_telemetry",
             "--project", TEST_PROJECT],
            capture_output=True, text=True,
        )
        assert "marketing" in result.stdout
        assert "sonnet" in result.stdout

    def test_query_events(self):
        tracker = FabricTracker(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        # Log two events
        tracker.log(UsageEvent(
            project="reallycoons", agent="marketing",
            model="sonnet", operation="research", cost_usd=0.05,
        ))
        tracker.log(UsageEvent(
            project="reallycoons", agent="engineer",
            model="haiku", operation="code_review", cost_usd=0.01,
        ))
        events = tracker.query(project="reallycoons")
        assert len(events) > 0

    def test_aggregate_cost(self):
        tracker = FabricTracker(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        tracker.log(UsageEvent(
            project="reallycoons", agent="marketing",
            model="sonnet", cost_usd=0.05,
        ))
        tracker.log(UsageEvent(
            project="reallycoons", agent="engineer",
            model="haiku", cost_usd=0.02,
        ))
        total = tracker.total_cost()
        assert total > 0

    def test_summary_by_model(self):
        tracker = FabricTracker(binary_path=FABRIC_BINARY, project=TEST_PROJECT)
        tracker.log(UsageEvent(
            project="test", agent="a", model="sonnet", cost_usd=0.1,
        ))
        tracker.log(UsageEvent(
            project="test", agent="b", model="haiku", cost_usd=0.02,
        ))
        summary = tracker.summary(group_by="model")
        assert "sonnet" in summary or "haiku" in summary or "groups" in summary


class TestOldSQLiteRemoved:
    """Verify SQLite tracker is no longer the default path."""

    def test_main_uses_fabric_tracker(self):
        """main.py should import FabricTracker, not UsageTracker for run tracking."""
        main_py = Path(__file__).parent.parent / "main.py"
        content = main_py.read_text()
        assert "from tracking.fabric_tracker import FabricTracker" in content
        # The old import should not be used for tracking
        assert "tracker = UsageTracker()" not in content
