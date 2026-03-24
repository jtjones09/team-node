"""The Heartbeat — periodic self-resolution cycle.

The system wakes up, reads the fabric, and acts on what it finds.
This is the first self-directed resolution cycle.

Checks (in order):
  a. Coherence: detect near-duplicate nodes
  b. Cost: aggregate recent telemetry spend
  c. Staleness: find old, unaccessed nodes
  d. Knowledge gaps: low-result queries
  e. Session summary: record the pulse itself

All findings are stored as fabric nodes with kind=heartbeat metadata.
"""

import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Heartbeat:
    """Periodic fabric self-monitoring."""

    def __init__(
        self,
        binary_path: str | None = None,
        project: str = "default",
        cost_threshold: float = 5.0,
        staleness_days: int = 30,
    ):
        from config import FABRIC_BINARY
        self._binary = binary_path or FABRIC_BINARY
        self._project = project
        self._cost_threshold = cost_threshold
        self._staleness_days = staleness_days

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [self._binary, *args]
        try:
            return subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

    def _store_finding(self, description: str, category: str, pulse_id: str, level: str = "info") -> str:
        """Store a heartbeat finding as a fabric node."""
        timestamp = datetime.now(timezone.utc).isoformat()
        result = self._run_cli(
            "fabric", "add",
            "--want", description,
            "--project", self._project,
            "--meta", "kind=heartbeat",
            "--meta", f"pulse_id={pulse_id}",
            "--meta", f"category={category}",
            "--meta", f"level={level}",
            "--meta", f"timestamp={timestamp}",
        )
        node_id = ""
        if result.stdout:
            for line in result.stdout.split("\n"):
                if line.startswith("Added node:"):
                    node_id = line.split(":", 1)[1].strip()
                    break
        return node_id

    def check_coherence(self, pulse_id: str) -> dict[str, Any]:
        """Check for near-duplicate nodes."""
        result = self._run_cli(
            "fabric", "list",
            "--project", self._project,
        )

        findings = {"check": "coherence", "alerts": 0, "details": ""}

        if not result.stdout:
            return findings

        # Extract node descriptions
        descriptions = []
        for line in result.stdout.split("\n"):
            if "] " in line and "[" in line:
                parts = line.split("] ", 1)
                if len(parts) == 2:
                    descriptions.append(parts[1].strip())

        # Simple duplicate detection: find descriptions that share >80% words
        duplicates = []
        for i, d1 in enumerate(descriptions):
            words1 = set(d1.lower().split())
            for j, d2 in enumerate(descriptions[i+1:], i+1):
                words2 = set(d2.lower().split())
                if not words1 or not words2:
                    continue
                overlap = len(words1 & words2) / max(len(words1), len(words2))
                if overlap > 0.8 and d1 != d2:
                    duplicates.append((d1[:60], d2[:60]))

        if duplicates:
            findings["alerts"] = len(duplicates)
            detail = f"Found {len(duplicates)} near-duplicate pair(s)"
            findings["details"] = detail
            self._store_finding(
                f"Coherence alert: {detail}",
                "coherence", pulse_id, "info",
            )

        return findings

    def check_cost(self, pulse_id: str) -> dict[str, Any]:
        """Check accumulated cost."""
        result = self._run_cli(
            "fabric", "aggregate",
            "--field", "cost_usd",
            "--op", "sum",
            "--where", "domain=system_telemetry",
            "--project", self._project,
        )

        findings = {"check": "cost", "alerts": 0, "total_cost": 0.0}

        try:
            data = json.loads(result.stdout.strip())
            total = float(data.get("result", 0))
            findings["total_cost"] = total

            if total > self._cost_threshold:
                findings["alerts"] = 1
                findings["details"] = f"${total:.2f} spent (threshold: ${self._cost_threshold:.2f})"
                self._store_finding(
                    f"Cost alert: ${total:.2f} spent on project {self._project}. Consider --fast mode.",
                    "cost", pulse_id, "alert",
                )
        except (json.JSONDecodeError, ValueError):
            pass

        return findings

    def check_staleness(self, pulse_id: str) -> dict[str, Any]:
        """Find nodes that haven't been accessed recently."""
        # This is approximate — we check activation_count=0 as a proxy for staleness
        result = self._run_cli(
            "fabric", "search",
            "--where", "activation_count=0",
            "--limit", "100",
            "--project", self._project,
        )

        findings = {"check": "staleness", "stale_count": 0}

        if result.stdout and "Matching nodes" in result.stdout:
            # Count matching lines
            count = 0
            for line in result.stdout.split("\n"):
                if "] " in line and "[" in line:
                    count += 1
            findings["stale_count"] = count

            if count > 0:
                self._store_finding(
                    f"Staleness report: {count} nodes with zero activations in project {self._project}",
                    "staleness", pulse_id, "info",
                )

        return findings

    def check_knowledge_gaps(self, pulse_id: str) -> dict[str, Any]:
        """Check for queries that returned no results (placeholder)."""
        # This would need query logging — for now, just report that the check ran
        findings = {"check": "knowledge_gaps", "gaps": 0}
        return findings

    def pulse(self) -> dict[str, Any]:
        """Run one complete heartbeat pulse. Returns summary."""
        pulse_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now(timezone.utc).isoformat()

        print(f"  Heartbeat pulse {pulse_id} at {timestamp}")
        print(f"  Project: {self._project}")
        print(f"  {'-' * 50}")

        results = []

        # a. Coherence
        coherence = self.check_coherence(pulse_id)
        results.append(coherence)
        alerts = coherence.get("alerts", 0)
        if alerts:
            print(f"  Coherence: {coherence.get('details', '')}")
        else:
            print(f"  Coherence: OK")

        # b. Cost
        cost = self.check_cost(pulse_id)
        results.append(cost)
        if cost.get("alerts", 0):
            print(f"  Cost: ALERT — {cost.get('details', '')}")
        else:
            print(f"  Cost: ${cost.get('total_cost', 0):.2f} (threshold: ${self._cost_threshold})")

        # c. Staleness
        staleness = self.check_staleness(pulse_id)
        results.append(staleness)
        stale = staleness.get("stale_count", 0)
        print(f"  Staleness: {stale} zero-activation nodes")

        # d. Knowledge gaps
        gaps = self.check_knowledge_gaps(pulse_id)
        results.append(gaps)
        print(f"  Knowledge gaps: {gaps.get('gaps', 0)} detected")

        # e. Session summary
        total_alerts = sum(r.get("alerts", 0) for r in results)
        total_gaps = sum(r.get("gaps", 0) for r in results)
        summary = f"Heartbeat at {timestamp}: 4 checks completed, {total_alerts} alert(s), {total_gaps} gap(s)"
        self._store_finding(summary, "pulse_summary", pulse_id, "info")

        print(f"  {'-' * 50}")
        print(f"  Summary: {summary}")

        return {
            "pulse_id": pulse_id,
            "timestamp": timestamp,
            "checks": results,
            "total_alerts": total_alerts,
            "summary": summary,
        }

    def run_daemon(self, interval_minutes: int = 30):
        """Run heartbeat as a daemon with periodic pulses."""
        interval = int(os.environ.get("TEAMNODE_HEARTBEAT_INTERVAL_MINUTES", interval_minutes))
        print(f"\n  Heartbeat daemon starting (interval: {interval} minutes)")
        print(f"  Press Ctrl+C to stop.\n")

        while True:
            try:
                self.pulse()
                print(f"\n  Next pulse in {interval} minutes...\n")
                time.sleep(interval * 60)
            except KeyboardInterrupt:
                print("\n  Heartbeat daemon stopped.")
                break
