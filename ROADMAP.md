# ROADMAP.md — TeamNode Future Vision

Ideas and features to think about. Not prioritized yet — just captured.

---

## Agent Observer UI

**Updated interface while agents are working.** Something modern that lets you view and navigate what the agents are doing in real time.

- Quick filter by agent (Marketing, Engineer, Architect, etc.)
- See which tools each agent is calling and what they're returning
- Visual timeline of the execution flow
- Expandable/collapsible sections for each agent's work
- Color-coded by agent domain (matches the perspective lens colors)

**This could layer on top of the visual fabric graph we discussed** — a real-time visualization where you see nodes being created and connections forming as the agents work. The graph IS the interface. You're not reading logs, you're watching the fabric come alive.

Potential implementations:
- WebSocket-based dashboard (Python backend pushes events, React frontend renders)
- Terminal UI using `rich` or `textual` (simpler, stays in the terminal)
- Standalone Electron/Tauri app that connects to the agent runtime

---

## Retrieval Quality

- Replace TF-IDF keyword overlap with real embeddings (Phase 4 of Ecphory)
- Temporal weighting — recent nodes score higher
- Planner should check fabric first and skip re-fetching if recent analysis exists
- Deduplication — don't store the same insight 5 times across runs

## CrewAI Replacement

- CrewAI's tool argument handling is broken for large content (can't write files)
- Hierarchical delegation is broken (known bug, months unfixed)
- Build lightweight agent runner (~200-300 lines Python)
- Direct Anthropic SDK calls, our own tool loop, our own routing
- No framework dependency in the critical path

## Mockup Generation

- Agents should be able to produce visual deliverables (HTML mockups, diagrams)
- Current workaround: agent includes HTML in final answer, main.py auto-extracts
- Proper fix: custom tool that handles large content or streaming file writes

## Multi-Project Management

- Dashboard showing all projects, their fabric node counts, recent activity
- Cross-project knowledge sharing (some insights apply everywhere)
- Project templates (cattery site, SaaS landing page, etc.)

## LinkedIn Integration

- Post/comment directly from agent output
- Scheduling via Buffer or Typefully API
- Or direct LinkedIn API with w_member_social permission

## Home Lab Services

- Infisical (secrets vault) on Raspberry Pi
- SearXNG (self-hosted search) on Beelink behind VPN — enables cross-validated search
- Ollama with large models on Beelink for local inference

## Client Deliverable Templates

- Recommendations sheet (PDF/docx) for Plan 1 type engagements
- Site audit reports with screenshots and scores
- SEO gap analysis with keyword research
