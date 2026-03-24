"""Notification channels — the fabric speaks.

Pluggable notification backends that give the heartbeat a voice.
When the fabric notices something important, it can tell you.

Channels:
  - ConsoleChannel: prints to stdout (always available)
  - FileChannel: writes to ~/.ecphory/notifications.log
  - SlackChannel: sends via Slack webhook

All notifications are also stored as fabric nodes (kind=notification).
"""

import json
import os
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any


class NotificationLevel(IntEnum):
    INFO = 0
    ALERT = 1
    CRITICAL = 2


LEVEL_LABELS = {
    NotificationLevel.INFO: "INFO",
    NotificationLevel.ALERT: "ALERT",
    NotificationLevel.CRITICAL: "CRITICAL",
}


class NotificationChannel(ABC):
    """Base class for notification channels."""

    @abstractmethod
    def send(self, level: NotificationLevel, message: str, context: dict[str, Any] | None = None) -> bool:
        """Send a notification. Returns True on success."""
        ...


class ConsoleChannel(NotificationChannel):
    """Prints notifications to stdout."""

    def send(self, level: NotificationLevel, message: str, context: dict[str, Any] | None = None) -> bool:
        label = LEVEL_LABELS.get(level, "INFO")
        prefix = f"  [{label}]"
        if level >= NotificationLevel.CRITICAL:
            prefix = f"  *** [{label}] ***"
        elif level >= NotificationLevel.ALERT:
            prefix = f"  ! [{label}]"
        print(f"{prefix} {message}")
        return True


class FileChannel(NotificationChannel):
    """Appends notifications to a log file."""

    def __init__(self, path: str | Path | None = None):
        self._path = Path(path) if path else Path.home() / ".ecphory" / "notifications.log"

    def send(self, level: NotificationLevel, message: str, context: dict[str, Any] | None = None) -> bool:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).isoformat()
            label = LEVEL_LABELS.get(level, "INFO")
            entry = f"[{timestamp}] [{label}] {message}\n"
            with open(self._path, "a") as f:
                f.write(entry)
            return True
        except OSError:
            return False


class SlackChannel(NotificationChannel):
    """Sends notifications via Slack incoming webhook."""

    def __init__(self, webhook_url: str | None = None):
        self._webhook_url = webhook_url or os.environ.get("TEAMNODE_SLACK_WEBHOOK", "")

    def send(self, level: NotificationLevel, message: str, context: dict[str, Any] | None = None) -> bool:
        if not self._webhook_url:
            return False

        label = LEVEL_LABELS.get(level, "INFO")
        emoji = ":information_source:"
        if level >= NotificationLevel.CRITICAL:
            emoji = ":rotating_light:"
        elif level >= NotificationLevel.ALERT:
            emoji = ":warning:"

        payload = {
            "text": f"{emoji} *[{label}]* {message}",
        }

        try:
            import urllib.request
            req = urllib.request.Request(
                self._webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False


class NotificationManager:
    """Dispatches notifications to configured channels and stores them as fabric nodes."""

    def __init__(
        self,
        channels: list[NotificationChannel] | None = None,
        binary_path: str | None = None,
        project: str = "default",
    ):
        from config import FABRIC_BINARY
        self._channels = channels or []
        self._binary = binary_path or FABRIC_BINARY
        self._project = project

    def add_channel(self, channel: NotificationChannel):
        self._channels.append(channel)

    def notify(self, level: NotificationLevel, message: str, context: dict[str, Any] | None = None) -> list[str]:
        """Send notification through all channels and store as fabric node.

        Returns list of channel names that succeeded.
        """
        succeeded = []

        for channel in self._channels:
            try:
                if channel.send(level, message, context):
                    succeeded.append(type(channel).__name__)
            except Exception:
                pass

        # Store as fabric node
        self._store_notification(level, message, succeeded, context)

        return succeeded

    def _store_notification(
        self,
        level: NotificationLevel,
        message: str,
        channels_sent: list[str],
        context: dict[str, Any] | None = None,
    ):
        """Store the notification as a fabric node."""
        timestamp = datetime.now(timezone.utc).isoformat()
        label = LEVEL_LABELS.get(level, "INFO")

        args = [
            self._binary,
            "fabric", "add",
            "--want", f"Notification [{label}]: {message}",
            "--project", self._project,
            "--meta", "kind=notification",
            "--meta", f"level={label.lower()}",
            "--meta", f"channels={','.join(channels_sent)}",
            "--meta", f"timestamp={timestamp}",
        ]

        if context:
            for key, val in context.items():
                args.extend(["--meta", f"notification_{key}={val}"])

        try:
            subprocess.run(args, capture_output=True, text=True, timeout=30)
        except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError, OSError):
            pass


def load_config() -> dict[str, Any]:
    """Load notification config from ~/.config/teamnode/notifications.json."""
    config_path = Path.home() / ".config" / "teamnode" / "notifications.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def build_manager(
    project: str = "default",
    binary_path: str | None = None,
) -> NotificationManager:
    """Build a NotificationManager from config and environment."""
    config = load_config()

    manager = NotificationManager(
        binary_path=binary_path,
        project=project,
    )

    # Console is always enabled
    if config.get("console", {}).get("enabled", True):
        manager.add_channel(ConsoleChannel())

    # File channel
    file_cfg = config.get("file", {})
    if file_cfg.get("enabled", True):
        path = file_cfg.get("path")
        manager.add_channel(FileChannel(path=path))

    # Slack channel
    slack_cfg = config.get("slack", {})
    slack_url = slack_cfg.get("webhook_url") or os.environ.get("TEAMNODE_SLACK_WEBHOOK", "")
    if slack_cfg.get("enabled", False) and slack_url:
        manager.add_channel(SlackChannel(webhook_url=slack_url))

    return manager
