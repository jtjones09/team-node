# Fabric CLI Spec — Intent-Node Commands for TeamNode Integration

This document describes the CLI commands that intent-node needs to support
for TeamNode to replace its temporary JSON bridge with real fabric operations.

## Overview

TeamNode's `fabric_bridge.py` currently reads/writes a JSON file directly.
When these CLI commands are implemented in intent-node, the bridge will call
them via subprocess instead, getting real resonance scoring, temporal decay,
confidence surfaces, and immune assessment on every retrieval.

All commands output JSON when `--json` flag is set (for machine consumption).
Without `--json`, output is human-readable.

---

## Commands

### `intent fabric add`

Store a node in the fabric.

```bash
intent fabric add \
  --want "text content to store" \
  --domain "marketing" \
  --project "ecphory" \
  --json
```

**Required flags**:
- `--want` — The text content to store as a fabric node

**Optional flags**:
- `--domain` — Domain namespace (e.g., "marketing", "security", "engineer")
- `--project` — Project scope for multi-project isolation
- `--json` — Output structured JSON response

**JSON output**:
```json
{
  "id": "uuid-of-new-node",
  "status": "stored",
  "confidence": 1.0,
  "timestamp": "2026-03-21T12:00:00Z"
}
```

---

### `intent fabric search`

Search the fabric using resonance matching.

```bash
intent fabric search \
  --query "positioning strategy" \
  --top-k 5 \
  --project "ecphory" \
  --domain "marketing" \
  --json
```

**Required flags**:
- `--query` — The search query text

**Optional flags**:
- `--top-k` — Maximum number of results (default: 5)
- `--project` — Project scope
- `--domain` — Filter results to a specific domain
- `--json` — Output structured JSON response

**JSON output**:
```json
{
  "nodes": [
    {
      "id": "uuid",
      "content": "node text content",
      "score": 0.92,
      "confidence": 0.85,
      "domain": "marketing",
      "metadata": {},
      "created_at": "2026-03-20T10:00:00Z",
      "last_activated": "2026-03-21T11:00:00Z"
    }
  ],
  "query": "positioning strategy",
  "total_matches": 12
}
```

**Notes**:
- Score should incorporate resonance matching, not just cosine similarity
- Confidence surfaces from the immune system should be included
- Temporal decay should affect scoring (recently activated nodes rank higher)

---

### `intent fabric list`

List all nodes in a project's fabric.

```bash
intent fabric list \
  --project "ecphory" \
  --domain "security" \
  --json
```

**Optional flags**:
- `--project` — Project scope
- `--domain` — Filter to a specific domain
- `--json` — Output structured JSON response

**JSON output**:
```json
{
  "nodes": [
    {
      "id": "uuid",
      "content": "first 200 chars...",
      "domain": "security",
      "created_at": "2026-03-20T10:00:00Z"
    }
  ],
  "total": 42
}
```

---

### `intent fabric history`

Show recent activity in a project's fabric.

```bash
intent fabric history \
  --project "ecphory" \
  --limit 20 \
  --json
```

**Optional flags**:
- `--project` — Project scope
- `--limit` — Number of entries (default: 20)
- `--json` — Output structured JSON response

**JSON output**:
```json
{
  "entries": [
    {
      "action": "add",
      "node_id": "uuid",
      "domain": "marketing",
      "timestamp": "2026-03-21T12:00:00Z",
      "content_preview": "first 100 chars..."
    }
  ]
}
```

---

### `intent fabric save`

Persist the current fabric state to disk.

```bash
intent fabric save --project "ecphory"
```

**Optional flags**:
- `--project` — Project scope

**JSON output**:
```json
{
  "status": "saved",
  "path": "data/projects/ecphory/fabric.json",
  "node_count": 42
}
```

---

### `intent fabric load`

Load a fabric from disk.

```bash
intent fabric load --project "ecphory"
```

**Optional flags**:
- `--project` — Project scope

**JSON output**:
```json
{
  "status": "loaded",
  "path": "data/projects/ecphory/fabric.json",
  "node_count": 42
}
```

---

## Integration Path

When these commands are ready in intent-node, update `team-node/memory/fabric_bridge.py`:

```python
# Replace JSON file reads with:
result = subprocess.run(
    ["intent", "fabric", "search", "--query", query, "--top-k", str(top_k),
     "--project", self._project, "--json"],
    capture_output=True, text=True, timeout=30,
)
nodes = json.loads(result.stdout)["nodes"]
```

The `FabricBridge.__init__` should accept a binary path and project name
instead of a fabric file path once CLI commands are available.
