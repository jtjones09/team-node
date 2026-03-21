"""Structured markdown logging for decisions, research, and task history."""

from datetime import datetime, timezone
from pathlib import Path


class MarkdownLog:
    """Appends structured entries to domain-specific markdown log files."""

    def __init__(self, log_dir: str | Path):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_path(self, domain: str) -> Path:
        return self._log_dir / f"{domain}.md"

    def log(self, domain: str, entry_type: str, title: str, content: str) -> Path:
        """Append a structured log entry.

        Args:
            domain: Agent domain (e.g., "marketing", "security").
            entry_type: Type of entry (e.g., "decision", "research", "task").
            title: Short title for the entry.
            content: Full content body.

        Returns:
            Path to the log file.
        """
        log_path = self._get_log_path(domain)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        entry = f"\n## [{entry_type.upper()}] {title}\n"
        entry += f"**Timestamp**: {timestamp}\n\n"
        entry += f"{content}\n"
        entry += "\n---\n"

        with open(log_path, "a") as f:
            if log_path.stat().st_size == 0 if log_path.exists() else True:
                f.write(f"# {domain.title()} Log\n\n---\n")
            f.write(entry)

        return log_path

    def read_log(self, domain: str) -> str:
        """Read the full log for a domain."""
        log_path = self._get_log_path(domain)
        if log_path.exists():
            return log_path.read_text()
        return ""
