"""Crew assembly — wires up agents, lenses, memory, and process config.

Token optimization:
- Only instantiate agents that will actually run (not all 7)
- Planner uses Haiku (cheap) for research/fetch tasks
- Domain agents use Sonnet for quality output
- MAX_ITER caps runaway tool retry loops
"""

from crewai import Crew, Task, Process, LLM

from config import (
    LOG_DIR, FABRIC_BINARY, TEMPERATURES,
    OLLAMA_BASE_URL, OLLAMA_MODEL, get_project_paths,
    AGENT_MODEL, MAX_ITER, MAX_RPM,
)
from memory.fabric_bridge import FabricBridge
from memory.markdown_log import MarkdownLog
from lenses.perspective import PerspectiveLens
from agents.marketing import create_marketing_agent
from agents.sales import create_sales_agent
from agents.engineer import create_engineer_agent
from agents.architect import create_architect_agent
from agents.planner_researcher import create_planner_researcher_agent
from agents.security import create_security_agent
from agents.data_analytics import create_data_analytics_agent


def _make_ollama_llms(model_name: str) -> dict[str, LLM]:
    """Create per-agent Ollama LLM instances with correct temperatures."""
    llms = {}
    for agent_name, temp in TEMPERATURES.items():
        llms[agent_name] = LLM(
            model=f"ollama/{model_name}",
            base_url=OLLAMA_BASE_URL,
            temperature=temp,
        )
    return llms


DOMAIN_KEYWORDS = {
    "marketing": [
        "linkedin", "article", "post", "comment", "content", "brand", "positioning",
        "audience", "messaging", "thought leadership", "blog", "draft", "write",
        "social media", "campaign", "newsletter", "website", "mockup", "redesign",
        "seo", "site",
    ],
    "sales": [
        "outreach", "pipeline", "partnership", "prospect", "deal", "pitch",
        "proposal", "lead", "revenue", "pricing", "contract", "client",
    ],
    "engineer": [
        "code", "build", "implement", "debug", "script", "function", "api",
        "test", "deploy", "refactor", "fix", "bug", "compile", "run", "install",
        "rust", "python", "typescript", "docker", "cli", "technical",
    ],
    "architect": [
        "design", "architecture", "system", "spec", "specification", "trade-off",
        "scalability", "integration", "pattern", "diagram", "schema", "rfc",
    ],
    "security": [
        "security", "vulnerability", "cve", "threat", "audit", "compliance",
        "penetration", "encryption", "authentication", "authorization", "review code",
    ],
    "data_analytics": [
        "metric", "data", "analysis", "benchmark", "evidence", "competitive",
        "research data", "statistics", "trend", "performance", "dashboard",
    ],
}


def route_goal(goal: str) -> list[str]:
    """Route a goal to the appropriate agent domain(s) using keyword matching.

    Always includes planner_researcher for context gathering.
    Returns: list of domain names, planner_researcher always last (runs first in sequential).
    """
    goal_lower = goal.lower()
    scores = {}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in goal_lower)
        if score > 0:
            scores[domain] = score

    if not scores:
        return ["planner_researcher"]

    sorted_domains = sorted(scores, key=scores.get, reverse=True)
    primary = sorted_domains[0]
    return ["planner_researcher", primary]


# Agent factory lookup
AGENT_FACTORIES = {
    "marketing": create_marketing_agent,
    "sales": create_sales_agent,
    "engineer": create_engineer_agent,
    "architect": create_architect_agent,
    "planner_researcher": create_planner_researcher_agent,
    "security": create_security_agent,
    "data_analytics": create_data_analytics_agent,
}


def build_crew(
    goal: str,
    verbose: bool = True,
    use_ollama: bool = False,
    ollama_model: str | None = None,
    project: str | None = None,
) -> Crew:
    """Assemble the team with only the agents that will actually run."""
    llms = {}
    if use_ollama:
        llms = _make_ollama_llms(ollama_model or OLLAMA_MODEL)

    if project:
        paths = get_project_paths(project)
        log_dir = str(paths["log_dir"])
    else:
        log_dir = str(LOG_DIR)

    memory_backend = FabricBridge(FABRIC_BINARY, project=project)
    logger = MarkdownLog(log_dir)

    routed_domains = route_goal(goal)

    if verbose:
        print(f"\n  Routing: {goal[:80]}...")
        print(f"  Assigned to: {', '.join(routed_domains)}")
        print(f"  Max iterations per agent: {MAX_ITER}\n")

    # Only create the agents we actually need
    active_agents = {}
    for domain in routed_domains:
        lens = PerspectiveLens(memory_backend, domain)
        factory = AGENT_FACTORIES[domain]
        active_agents[domain] = factory(lens, logger, llm_override=llms.get(domain))

    tasks = []

    # Planner always runs first for context
    if "planner_researcher" in active_agents:
        research_task = Task(
            description=(
                f"Research and gather relevant context for the following goal. "
                f"Search the team's shared memory fabric FIRST for any prior knowledge. "
                f"If you find existing analysis, use it instead of re-fetching. "
                f"Only fetch URLs or search the web if needed.\n\nGoal: {goal}"
            ),
            expected_output="A context briefing with relevant prior knowledge and research findings.",
            agent=active_agents["planner_researcher"],
        )
        tasks.append(research_task)

    # Primary domain agent runs second
    for domain in routed_domains:
        if domain != "planner_researcher":
            primary_task = Task(
                description=(
                    f"Execute the following goal using your domain expertise. "
                    f"Use the context provided by the Planner/Researcher. "
                    f"Store your output and any decisions in the team's shared memory. "
                    f"If asked to create HTML, include it directly in your response.\n\n"
                    f"Goal: {goal}"
                ),
                expected_output="A complete, high-quality deliverable addressing the goal.",
                agent=active_agents[domain],
            )
            tasks.append(primary_task)

    crew = Crew(
        agents=list(active_agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=verbose,
        max_iter=MAX_ITER,
        max_rpm=MAX_RPM,
    )

    return crew
