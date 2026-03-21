# TeamNode

**A heterogeneous multi-agent team where all agents are equal peers.**

No hierarchy. No boss. An orchestrator routes tasks but holds no authority over domain decisions. Inspired by non-hierarchical organizational design.

## Philosophy

- All 7 domain agents are equal peers
- The orchestrator is a traffic cop, not a manager
- Agents are **perspective lenses** on a shared semantic fabric, not containerized processes
- Each agent sees the same knowledge through different resonance profiles
- The Planner/Researcher holds the full knowledge graph and synthesizes across domains
- Voice constraints ensure all outward-facing content sounds human, not AI

## The Team

| Agent | Domain | Role |
|---|---|---|
| Marketing | Positioning, content, LinkedIn | Voice-constrained thought leadership |
| Sales | Outreach, partnerships, pipeline | Relationship strategy |
| Engineer | Code, scripts, hardware | Implementation |
| Architect | System design, specs, trade-offs | Design (doesn't write code) |
| Planner/Researcher | Research, synthesis, memory | Cross-domain knowledge custodian |
| Security | Code review, CVE, threat modeling | Reviews agent outputs for data leaks |
| Data/Analytics | Metrics, evidence, benchmarks | Evidence-based recommendations |

## Architecture

- **Framework**: CrewAI with `Process.hierarchical`
- **LLM**: Anthropic Claude (Sonnet for agents, Opus for synthesis)
- **Memory**: Ecphory Fabric (with ChromaDB fallback)
- **Routing**: Built-in CrewAI manager (not a full LLM agent)

### Perspective Lenses

Agents don't live in separate containers. They view the SAME fabric through different resonance profiles:

- Marketing lens amplifies positioning, messaging, audience nodes
- Security lens amplifies vulnerability, compliance, threat nodes
- Engineer lens amplifies implementation, dependency, performance nodes
- Planner/Researcher has the widest aperture — sees everything

### Domain Isolation

- Each agent writes to its own namespace (no bottleneck)
- Planner/Researcher reads ALL domains and synthesizes
- Security domain is isolated by default (DomainOnly access)
- Cross-domain reads gated by immune assessment

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key"
python main.py --goal "Draft a LinkedIn article about enterprise AI operating systems"
```

## Relationship to Ecphory

TeamNode uses the [Ecphory Fabric](https://github.com/jtjones09/ecphory) as its shared memory backend. When the fabric's CLI supports add/resonate commands, TeamNode swaps from ChromaDB to fabric-native memory — gaining confidence surfaces, temporal decay, provenance chains, and immune assessment on every retrieval.

## License

Apache License 2.0
