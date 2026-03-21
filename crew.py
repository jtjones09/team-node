"""Crew assembly — wires up all agents, lenses, memory, and process config."""

from crewai import Crew, Task, Process

from config import CHROMA_PERSIST_DIR, LOG_DIR
from memory.chroma_fallback import ChromaFallback
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

# DECISION: Using ChromaDB fallback until Ecphory fabric CLI is ready.
# Swap to FabricBridge by uncommenting the import and changing `memory_backend` below.
# from memory.fabric_bridge import FabricBridge


def build_crew(goal: str, verbose: bool = True) -> Crew:
    """Assemble the full 7-agent team with shared memory fabric.

    Args:
        goal: The task/goal to accomplish.
        verbose: Whether to enable verbose agent output.
    """
    # --- Memory backend ---
    memory_backend = ChromaFallback(str(CHROMA_PERSIST_DIR))
    # memory_backend = FabricBridge(FABRIC_BINARY, str(FABRIC_DATA_FILE))

    logger = MarkdownLog(str(LOG_DIR))

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
    orchestrator = create_orchestrator()
    marketing = create_marketing_agent(lenses["marketing"], logger)
    sales = create_sales_agent(lenses["sales"], logger)
    engineer = create_engineer_agent(lenses["engineer"], logger)
    architect = create_architect_agent(lenses["architect"], logger)
    planner = create_planner_researcher_agent(lenses["planner_researcher"], logger)
    security = create_security_agent(lenses["security"], logger)
    data_analytics = create_data_analytics_agent(lenses["data_analytics"], logger)

    # --- Define the task ---
    # The orchestrator gets the initial task and delegates to domain agents
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
