# TASKS.md — Priority Updates for Claude Code

Read this file FIRST, then CLAUDE.md. These tasks override or extend the original spec.

---

## TASK 1: Remove ChromaDB, Use Ecphory Fabric Directly

**Why**: ChromaDB was a fallback. The fabric is ready. Don't build throwaway integrations.

**What to do**:
1. Remove `chromadb` from `requirements.txt`
2. Delete `memory/chroma_fallback.py`
3. Update `crew.py` to use `FabricBridge` as the sole memory backend
4. Update `memory/fabric_bridge.py` to call the Ecphory binary

**The fabric binary is at**: `~/intent-node/target/release/intent`
(Build it first: `cd ~/intent-node && cargo build --release`)

**The fabric bridge needs the intent-node CLI to support these commands** (which don't exist yet — see TASK 5). Until those commands exist, implement `fabric_bridge.py` using the Rust library directly via a thin Python wrapper that:
- Serializes nodes to JSON and writes to a fabric JSON file
- Reads the fabric JSON file and searches by text similarity
- This is a TEMPORARY bridge until the CLI commands are built

```python
# fabric_bridge.py approach: direct JSON file interaction
# The fabric uses JsonFileStore for persistence (src/persist/)
# Read/write the same JSON format the Rust library uses
# Search by simple text matching as bootstrap until CLI resonance works
```

---

## TASK 2: Multi-Project Support

**Why**: Jeremy works on multiple projects simultaneously (Ecphory, AI OS articles, LinkedIn, client work). A single flat memory space doesn't work.

**What to do**:
1. Add `--project` flag to `main.py` (required argument)
2. Each project gets its own:
   - Fabric JSON file: `data/projects/{project}/fabric.json`
   - Markdown log directory: `data/projects/{project}/logs/`
   - Lens configuration (same agents, different resonance weights per project)
3. Add a `--list-projects` flag that shows available projects
4. Update `crew.py` to accept project name and scope memory/logs accordingly

```bash
python main.py --project ecphory --goal "Draft immune system hardening tasks"
python main.py --project aios-article --goal "Write Article 2 outline"
python main.py --list-projects
```

---

## TASK 3: Provenance Nodes — Track Everything the Team Does

**Why**: We need to know what the team did, why, and what led to what. Every agent action should be traceable.

**What to do**:
1. Create `memory/provenance.py` with a `ProvenanceTracker` class
2. After every agent produces output, create a provenance entry:
   ```python
   {
       "type": "agent_output",
       "agent": "marketing",
       "project": "aios-article",
       "goal": "the original goal text",
       "output_summary": "first 500 chars of output",
       "timestamp": "ISO 8601",
       "context_used": ["list of memory IDs that were retrieved for this task"],
       "confidence": 0.85
   }
   ```
3. After every decision, create a decision entry:
   ```python
   {
       "type": "decision",
       "agent": "architect",
       "project": "ecphory",
       "decision": "Use perspective lenses instead of containers",
       "reasoning": "Containers fragment what the fabric unifies",
       "alternatives_considered": ["Docker containers", "VM isolation"],
       "timestamp": "ISO 8601"
   }
   ```
4. Store provenance entries in the project's fabric AND in a `provenance.md` markdown log
5. Add `--history` flag to `main.py` that shows recent provenance for a project:
   ```bash
   python main.py --project ecphory --history
   ```

---

## TASK 4: Ollama Backend Support

**Why**: Local inference, no API key needed, no token cost for development/testing.

**What to do**:
1. Add `--ollama` flag to `main.py` with optional `--model` (default: `llama3.2:3b`)
2. When `--ollama` is set, configure all agents to use Ollama instead of Anthropic
3. CrewAI supports Ollama via `LLM(model="ollama/llama3.2:3b", base_url="http://localhost:11434")`
4. Temperature settings stay the same regardless of backend
5. Update config.py:
   ```python
   OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
   OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
   ```

---

## TASK 5: Intent-Node CLI Commands for Fabric Interaction

**NOTE**: This task is for the intent-node repo, NOT team-node. Create a spec file that describes what CLI commands the fabric needs to support for TeamNode integration.

Create `docs/fabric-cli-spec.md` in THIS repo (team-node) describing:
```
intent fabric add --want "text" --domain "marketing" --project "ecphory" --json
intent fabric search --query "positioning strategy" --top-k 5 --project "ecphory" --json
intent fabric list --project "ecphory" --json
intent fabric history --project "ecphory" --limit 20 --json
intent fabric save --project "ecphory"
intent fabric load --project "ecphory"
```

All commands output JSON when `--json` flag is set (for machine consumption by fabric_bridge.py).

---

## TASK 6: Persistent API Key Configuration

**What to do**:
1. Update `config.py` to check multiple sources in order:
   ```python
   def get_api_key():
       # 1. Environment variable (highest priority)
       key = os.environ.get("ANTHROPIC_API_KEY")
       if key:
           return key
       # 2. Config file in user's home dir
       config_path = Path.home() / ".config" / "teamnode" / "config.json"
       if config_path.exists():
           import json
           with open(config_path) as f:
               config = json.load(f)
           return config.get("anthropic_api_key", "")
       # 3. Not found
       return ""
   ```
2. Add `--setup` command to `main.py` that prompts for the API key and saves to `~/.config/teamnode/config.json` with file permissions 0600
3. The config file is gitignored, encrypted at rest by the OS, and lives outside any repo

---

## Build Order

Execute these tasks in order:
1. TASK 6 (persistent config) — so you can test without pasting keys
2. TASK 4 (Ollama) — so you can test without ANY keys
3. TASK 1 (remove ChromaDB, fabric bridge) — swap memory backend
4. TASK 2 (multi-project) — scope memory by project
5. TASK 3 (provenance) — track what the team does
6. TASK 5 (CLI spec) — document what intent-node needs to build

**After each task**: run tests, commit, push. Flag decisions with `# DECISION:`.
