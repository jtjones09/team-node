"""Crew assembly — wires up all agents, lenses, memory, and process config.

DECISION: Using Process.sequential with a Python routing function instead of
Process.hierarchical with manager_agent. CrewAI's hierarchical delegation has
a known bug where the manager can only see itself as a coworker. The routing
function classifies the goal and assigns tasks to the right agents directly.
This is actually better — no LLM tokens wasted on routing decisions.
"""

from crewai import Crew, Task, Process, LLM

from config import (
    LOG_DIR, FABRIC_BINARY, TEMPERATURES,
    OLLAMA_BASE_URL, OLLAMA_MODEL, get_project_paths,
    AGENT_MODEL,
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
        "social media", "campaign", "newsletter",
    ],
    "sales": [
        "outreach", "pipeline", "partnership", "prospect", "deal", "pitch",
        "proposal", "lead", "revenue", "pricing", "contract", "client",
    ],
    "engineer": [
        "code", "build", "implement", "debug", "script", "function", "api",
        "test", "deploy", "refactor", "fix", "bug", "compile", "run", "install",
        "rust", "python", "typescript", "docker", "cli",
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
    "planner_researcher": [
        "research", "plan", "strategy", "roadmap", "compare", "evaluate",
        "synthesize", "summary", "overview", "investigate", "explore",
    ],
}


def route_goal(goal: str) -> list[str]:
    """Route a goal to the appropriate agent domain(s) using keyword matching."""
    goal_lower = goal.lower()
    scores = {}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in goal_lower)
        if score > 0:
            scores[domain] = score

    if not scores:
        return ["planner_researcher"]

    sorted_domains = sorted(scores, key=scores.get, reverse=True)
    result = [sorted_domains[0]]
    if "planner_researcher" not in result:
        result.append("planner_researcher")

    return result


def build_crew(
    goal: str,
    verbose: bool = True,
    use_ollama: bool = False,
    ollama_model: str | None = None,
    project: str | None = None,
) -> Crew:
    """Assemble the team with Python-routed task assignment."""
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

    lenses = {
        "marketing": PerspectiveLens(memory_backend, "marketing"),
        "sales": PerspectiveLens(memory_backend, "sales"),
        "engineer": PerspectiveLens(memory_backend, "engineer"),
        "architect": PerspectiveLens(memory_backend, "architect"),
        "planner_researcher": PerspectiveLens(memory_backend, "planner_researcher"),
        "security": PerspectiveLens(memory_backend, "security"),
        "data_analytics": PerspectiveLens(memory_backend, "data_analytics"),
    }

    agents = {
        "marketing": create_marketing_agent(lenses["marketing"], logger, llm_override=llms.get("marketing")),
        "sales": create_sales_agent(lenses["sales"], logger, llm_override=llms.get("sales")),
        "engineer": create_engineer_agent(lenses["engineer"], logger, llm_override=llms.get("engineer")),
        "architect": create_architect_agent(lenses["architect"], logger, llm_override=llms.get("architect")),
        "planner_researcher": create_planner_researcher_agent(lenses["planner_researcher"], logger, llm_override=llms.get("planner_researcher")),
        "security": create_security_agent(lenses["security"], logger, llm_override=llms.get("security")),
        "data_analytics": create_data_analytics_agent(lenses["data_analytics"], logger, llm_override=llms.get("data_analytics")),
    }

    routed_domains = route_goal(goal)

    if verbose:
        print(f"\n  Routing: {goal[:80]}...")
        print(f"  Assigned to: {', '.join(routed_domains)}\n")

    tasks = []

    if "planner_researcher" in routed_domains:
        research_task = Task(
            description=(
                f"Research and gather relevant context for the following goal. "
                f"Search the team's shared memory fabric for any prior knowledge, "
                f"decisions, or related work. Provide a context briefing for the "
                f"primary agent.\n\nGoal: {goal}"
            ),
            expected_output="A context briefing with relevant prior knowledge, research findings, and any related team history.",
            agent=agents["planner_researcher"],
        )
        tasks.append(research_task)

    primary_domain = routed_domains[0]
    if primary_domain != "planner_researcher":
        primary_task = Task(
            description=(
                f"Execute the following goal using your domain expertise. "
                f"Use the context provided by the Planner/Researcher. "
                f"Store your output and any decisions in the team's shared memory.\n\n"
                f"Goal: {goal}"
            ),
            expected_output="A complete, high-quality deliverable addressing the goal.",
            agent=agents[primary_domain],
        )
        tasks.append(primary_task)

    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=verbose,
    )

    return crew
