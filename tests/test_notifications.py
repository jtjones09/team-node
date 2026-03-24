"""Tests for notification channels."""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from notifications.channels import (
    ConsoleChannel,
    FileChannel,
    SlackChannel,
    NotificationLevel,
    NotificationManager,
    build_manager,
    load_config,
)

FABRIC_BINARY = str(Path.home() / "projects" / "ecphory" / "target" / "release" / "intent")
TEST_PROJECT = "_test_notifications"


def cleanup():
    test_dir = Path.home() / ".ecphory" / TEST_PROJECT
    if test_dir.exists():
        shutil.rmtree(test_dir)


class TestConsoleChannel:
    def test_prints_info(self, capsys):
        ch = ConsoleChannel()
        assert ch.send(NotificationLevel.INFO, "test message") is True
        out = capsys.readouterr().out
        assert "[INFO]" in out
        assert "test message" in out

    def test_prints_alert(self, capsys):
        ch = ConsoleChannel()
        ch.send(NotificationLevel.ALERT, "cost exceeded")
        out = capsys.readouterr().out
        assert "[ALERT]" in out
        assert "!" in out

    def test_prints_critical(self, capsys):
        ch = ConsoleChannel()
        ch.send(NotificationLevel.CRITICAL, "multiple alerts")
        out = capsys.readouterr().out
        assert "[CRITICAL]" in out
        assert "***" in out


class TestFileChannel:
    def test_writes_to_log(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            path = f.name

        try:
            ch = FileChannel(path=path)
            assert ch.send(NotificationLevel.ALERT, "disk full") is True
            content = Path(path).read_text()
            assert "[ALERT]" in content
            assert "disk full" in content
        finally:
            os.unlink(path)

    def test_appends_multiple(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            path = f.name

        try:
            ch = FileChannel(path=path)
            ch.send(NotificationLevel.INFO, "first")
            ch.send(NotificationLevel.ALERT, "second")
            lines = Path(path).read_text().strip().split("\n")
            assert len(lines) == 2
        finally:
            os.unlink(path)


class TestSlackChannel:
    def test_no_webhook_returns_false(self):
        ch = SlackChannel(webhook_url="")
        assert ch.send(NotificationLevel.INFO, "test") is False

    def test_sends_webhook(self):
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = ch.send(NotificationLevel.ALERT, "cost alert")
            assert result is True
            mock_urlopen.assert_called_once()

            # Verify payload
            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            payload = json.loads(req.data.decode("utf-8"))
            assert ":warning:" in payload["text"]
            assert "cost alert" in payload["text"]


class TestNotificationManager:
    def setup_method(self):
        cleanup()

    def teardown_method(self):
        cleanup()

    def test_dispatches_to_multiple_channels(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_path = f.name

        try:
            console = ConsoleChannel()
            file_ch = FileChannel(path=log_path)
            manager = NotificationManager(
                channels=[console, file_ch],
                binary_path="/dev/null",  # won't store to fabric in this test
                project=TEST_PROJECT,
            )
            succeeded = manager.notify(NotificationLevel.ALERT, "test multi-channel")
            assert "ConsoleChannel" in succeeded
            assert "FileChannel" in succeeded

            out = capsys.readouterr().out
            assert "test multi-channel" in out

            content = Path(log_path).read_text()
            assert "test multi-channel" in content
        finally:
            os.unlink(log_path)

    def test_stores_notification_as_fabric_node(self):
        if not Path(FABRIC_BINARY).exists():
            import pytest
            pytest.skip("Fabric binary not found")

        manager = NotificationManager(
            channels=[ConsoleChannel()],
            binary_path=FABRIC_BINARY,
            project=TEST_PROJECT,
        )
        manager.notify(NotificationLevel.ALERT, "cost threshold exceeded")

        # Verify stored in fabric
        import subprocess
        result = subprocess.run(
            [FABRIC_BINARY, "fabric", "search",
             "--where", "kind=notification",
             "--project", TEST_PROJECT],
            capture_output=True, text=True, timeout=30,
        )
        assert "notification" in result.stdout.lower() or "Notification" in result.stdout

    def test_notifications_command(self):
        if not Path(FABRIC_BINARY).exists():
            import pytest
            pytest.skip("Fabric binary not found")

        # Store a notification
        manager = NotificationManager(
            channels=[],
            binary_path=FABRIC_BINARY,
            project=TEST_PROJECT,
        )
        manager.notify(NotificationLevel.INFO, "test notification for CLI")

        # Query it back via CLI search
        import subprocess
        result = subprocess.run(
            [FABRIC_BINARY, "fabric", "search",
             "--where", "kind=notification",
             "--project", TEST_PROJECT],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0


class TestBuildManager:
    def test_default_has_console_and_file(self):
        manager = build_manager(project="test", binary_path="/dev/null")
        channel_types = [type(c).__name__ for c in manager._channels]
        assert "ConsoleChannel" in channel_types
        assert "FileChannel" in channel_types

    def test_slack_disabled_by_default(self):
        manager = build_manager(project="test", binary_path="/dev/null")
        channel_types = [type(c).__name__ for c in manager._channels]
        assert "SlackChannel" not in channel_types

    def test_config_loading(self):
        config = load_config()
        # Default: empty config if file doesn't exist
        assert isinstance(config, dict)


class TestHeartbeatWithNotifications:
    """Integration: heartbeat sends notifications."""

    def setup_method(self):
        cleanup()

    def teardown_method(self):
        cleanup()

    def test_heartbeat_sends_notifications(self, capsys):
        if not Path(FABRIC_BINARY).exists():
            import pytest
            pytest.skip("Fabric binary not found")

        from heartbeat.pulse import Heartbeat
        from notifications.channels import NotificationManager, ConsoleChannel

        manager = NotificationManager(
            channels=[ConsoleChannel()],
            binary_path=FABRIC_BINARY,
            project=TEST_PROJECT,
        )
        hb = Heartbeat(
            binary_path=FABRIC_BINARY,
            project=TEST_PROJECT,
            notification_manager=manager,
        )
        result = hb.pulse()
        assert "pulse_id" in result
        # Output captured — heartbeat printed its checks
        out = capsys.readouterr().out
        assert "Heartbeat pulse" in out
