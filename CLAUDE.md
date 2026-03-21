# CLAUDE.md — TeamNode: 7-Agent Heterogeneous Fabric Team

## What This Is

A heterogeneous multi-agent team where all agents are equal peers. No hierarchy. No boss. An orchestrator routes tasks but holds no authority over domain decisions. The team shares a single semantic memory fabric (Ecphory / ChromaDB fallback) instead of isolated vector databases.

**Philosophy**: Inspired by non-hierarchical organizational design. The orchestrator is a traffic cop, not a manager. Domain expertise lives with domain agents. The Planner/Researcher holds the full knowledge graph and synthesizes across domains.

**Architecture**: Agents are **perspective lenses** on a shared fabric, not containerized processes. Each agent sees the same nodes but through different resonance profiles that amplify their domain.

---

## Stack

- **Language**: Python 3.11+
- **Agent Framework**: CrewAI (latest stable)
- **LLM**: Anthropic Claude via `langchain-anthropic` (`ChatAnthropic`)
  - Orchestrator routing: `claude-sonnet-4-20250514` (fast, cheap, routing only)
  - All domain agents: `claude-sonnet-4-20250514`
  - Complex synthesis: `claude-opus-4-20250514` (Planner/Researcher deep reasoning)
- **Memory Backend**: Ecphory fabric (Rust binary) via Python subprocess wrapper
  - Fallback: ChromaDB if fabric integration isn't ready
- **Structured Logs**: Markdown files (decisions, research, task history)
- **Web Search**: `DuckDuckGoSearchRun` (free) — upgrade to Serper later

---

## Project Structure

```
team-node/
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py       # Pure router — NO domain tools, NO opinions
│   ├── marketing.py          # LinkedIn voice, content strategy, positioning
│   ├── sales.py              # Outreach, partnerships, pipeline
│   ├── engineer.py           # Code, scripts, hardware, implementation
│   ├── architect.py          # System design, specs, trade-off analysis
│   ├── planner_researcher.py # Research, cross-domain synthesis, memory custodian
│   ├── security.py           # Code review, CVE, threat modeling
│   └── data_analytics.py     # Metrics, evidence, competitive intel
├── lenses/
│   ├── __init__.py
│   └── perspective.py        # PerspectiveLens class
├── memory/
│   ├── __init__.py
│   ├── fabric_bridge.py      # Python wrapper around Ecphory binary
│   ├── chroma_fallback.py    # ChromaDB fallback
│   ├── memory_interface.py   # Abstract interface both backends implement
│   └── markdown_log.py       # Structured markdown logging
├── tools/
│   ├── __init__.py
│   ├── memory_tools.py       # CrewAI tool wrappers for memory operations
│   ├── web_tools.py          # DuckDuckGo search wrapper
│   ├── code_tools.py         # Code execution, file I/O
│   └── file_tools.py         # File system operations
├── voice/
│   ├── __init__.py
│   └── jeremy_voice.py       # Voice constraints for ALL outward-facing agents
├── crew.py                   # Crew assembly + process config
├── config.py                 # API keys, model settings, paths
├── main.py                   # CLI entry point
├── requirements.txt
└── tests/
    ├── test_agents.py        # Each agent stays in its lane
    ├── test_routing.py       # Orchestrator routes, doesn't answer
    ├── test_memory.py        # Memory round-trip across agents
    └── test_e2e.py           # Full team end-to-end
```

---

## Agent Definitions

### Temperature Reference

| Agent | Temperature | Model | Rationale |
|---|---|---|---|
| Orchestrator | 0.1 | Sonnet | Routing only, no creativity needed |
| Engineer | 0.2 | Sonnet | Precision, determinism |
| Architect | 0.2 | Sonnet | Precision, system design |
| Security | 0.2 | Sonnet | Threat analysis, no ambiguity |
| Data/Analytics | 0.2 | Sonnet | Evidence-based, factual |
| Marketing | 0.3 | Sonnet | Voice-constrained, NOT random creative |
| Sales | 0.3 | Sonnet | Voice-constrained |
| Planner/Researcher | 0.5 | Opus | Needs deep reasoning for synthesis |

### Voice Constraints (MANDATORY for outward-facing agents)

All agents producing content that a human will see must include the Jeremy Voice constraints in their system prompt. Key rules:
- Direct, conversational, slightly informal
- No em dashes, no polished transitions, no AI filler
- LinkedIn comments: validate briefly, extend with original perspective, end with question
- If it sounds like AI wrote it, rewrite it

### Perspective Lenses

Each agent views the fabric through a different resonance profile:
- Marketing: amplifies positioning, messaging, audience, brand nodes
- Security: amplifies vulnerability, compliance, threat, attack surface nodes
- Engineer: amplifies implementation, dependency, performance, testing nodes
- Planner/Researcher: widest aperture — amplifies cross-domain connections

### Domain Isolation

- `FullFabric` — Planner/Researcher only. Sees everything.
- `DomainPlusShared` — Most agents. Own domain + explicitly shared nodes.
- `DomainOnly` — Security. Threat analysis is isolated by default.

---

## Key Design Decisions

1. **No hierarchy.** Orchestrator routes. Does not command.
2. **Orchestrator uses Sonnet, not Opus.** Routing doesn't need deep reasoning.
3. **Temperature 0.3 for Marketing/Sales, not 0.7.** Voice is constrained.
4. **Each agent writes to its own domain namespace.** No single-writer bottleneck.
5. **Security domain isolated by default.** DomainOnly access policy.
6. **JEREMY_VOICE injected into every outward-facing agent.** Non-negotiable.
7. **ChromaDB is the fallback.** Ecphory fabric is the target memory backend.
8. **7 domain agents + 1 router = 8 total.** Router is infrastructure, not a peer.

---

## Build Order

Execute in order. Run tests after each phase. Do not proceed if tests fail.

1. Phase 1 — Scaffold (directory structure, requirements.txt, config.py)
2. Phase 2 — Voice constraints (voice/jeremy_voice.py)
3. Phase 3 — Memory layer + tools (memory/, tools/memory_tools.py)
4. Phase 4 — Agent definitions (agents/)
5. Phase 5 — Crew assembly (crew.py, main.py)
6. Phase 6 — Test suite (tests/)

**If you encounter a design decision not covered by this spec, make the best available choice, document it clearly in a comment, and flag it with `# DECISION:` for review.**

---

## Environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key"
python main.py --goal "your task here"
```

---

## Relationship to Ecphory

TeamNode uses the Ecphory Fabric as its shared memory backend. The fabric_bridge.py wrapper calls the Ecphory Rust binary via subprocess. When fabric CLI supports add/resonate commands, swap one line in crew.py:

```python
# memory = ChromaFallback(CHROMA_PERSIST_DIR)
memory = FabricBridge(FABRIC_BINARY, "./data/fabric.json")
```

This gives: confidence surfaces, temporal decay, provenance chains, activation weights, and immune assessment on every retrieval. ChromaDB gives cosine similarity. The fabric gives living memory.
