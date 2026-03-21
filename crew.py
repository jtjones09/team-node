"""Crew assembly — wires up all agents, lenses, memory, and process config."""

from crewai import Crew, Task, Process, LLM

from config import (
    LOG_DIR, FABRIC_DATA_FILE, TEMPERATURES,
    OLLAMA_BASE_URL, OLLAMA_MODEL, get_project_paths,
)
from memory.fabric_bridge import FabricBridge
from memory.markdown_log import MarkdownLog
from lenses.perspective import PerspectiveLens
from agents.orchestrator import create_orchestrator
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


def build_crew(
    goal: str,
    verbose: bool = True,
    use_ollama: bool = False,
    ollama_model: str | None = None,
    project: str | None = None,
) -> Crew:
    """Assemble the full 7-agent team with shared memory fabric.

    Args:
        goal: The task/goal to accomplish.
        verbose: Whether to enable verbose agent output.
        use_ollama: Use local Ollama inference instead of Anthropic.
        ollama_model: Override Ollama model name (default from config).
        project: Project name for scoped memory/logs. Uses flat paths if None.
    """
    # --- LLM backend ---
    llms = {}
    if use_ollama:
        llms = _make_ollama_llms(ollama_model or OLLAMA_MODEL)

    # --- Memory backend (project-scoped or flat) ---
    if project:
        paths = get_project_paths(project)
        fabric_file = str(paths["fabric_file"])
        log_dir = str(paths["log_dir"])
    else:
        fabric_file = str(FABRIC_DATA_FILE)
        log_dir = str(LOG_DIR)

    memory_backend = FabricBridge(fabric_file)
    logger = MarkdownLog(log_dir)

    # --- Perspective lenses (one per domain agent) ---
    lenses = {
        "marketing": PerspectiveLens(memory_backend, "marketing"),
        "sales": PerspectiveLens(memory_backend, "sales"),
        "engineer": PerspectiveLens(memory_backend, "engineer"),
        "architect": PerspectiveLens(memory_backend, "architect"),
        "planner_researcher": PerspectiveLens(memory_backend, "planner_researcher"),
        "security": PerspectiveLens(memory_backend, "security"),
        "data_analytics": PerspectiveLens(memory_backend, "data_analytics"),
    }

    # --- Create agents ---
    orchestrator = create_orchestrator(llm_override=llms.get("orchestrator"))
    marketing = create_marketing_agent(lenses["marketing"], logger, llm_override=llms.get("marketing"))
    sales = create_sales_agent(lenses["sales"], logger, llm_override=llms.get("sales"))
    engineer = create_engineer_agent(lenses["engineer"], logger, llm_override=llms.get("engineer"))
    architect = create_architect_agent(lenses["architect"], logger, llm_override=llms.get("architect"))
    planner = create_planner_researcher_agent(lenses["planner_researcher"], logger, llm_override=llms.get("planner_researcher"))
    security = create_security_agent(lenses["security"], logger, llm_override=llms.get("security"))
    data_analytics = create_data_analytics_agent(lenses["data_analytics"], logger, llm_override=llms.get("data_analytics"))

    # --- Define the task ---
    routing_task = Task(
        description=(
            f"Analyze the following goal and route it to the appropriate domain agent(s). "
            f"If the goal spans multiple domains, break it into sub-tasks and assign each "
            f"to the right specialist. If unclear, route to the Planner/Researcher.\n\n"
            f"Goal: {goal}"
        ),
        expected_output="A complete response addressing the goal, assembled from domain expert contributions.",
        agent=orchestrator,
    )

    # --- Assemble the crew ---
    # CrewAI requires manager_agent to NOT be in the agents list
    crew = Crew(
        agents=[marketing, sales, engineer, architect, planner, security, data_analytics],
        tasks=[routing_task],
        process=Process.hierarchical,
        manager_agent=orchestrator,
        verbose=verbose,
    )

    return crew
