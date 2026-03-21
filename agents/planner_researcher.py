"""Planner/Researcher agent — research, cross-domain synthesis, memory custodian."""

from crewai import Agent, LLM

from config import REASONING_MODEL, TEMPERATURES
from lenses.perspective import PerspectiveLens
from memory.markdown_log import MarkdownLog
from tools.memory_tools import create_memory_tools
from tools.web_tools import web_search
from tools.file_tools import read_file, list_directory

PLANNER_RESEARCHER_BACKSTORY = """You are the Planner/Researcher on a non-hierarchical team.
You have the widest view of the shared memory fabric (FullFabric access).

Your domain covers: deep research, cross-domain synthesis, strategic planning,
knowledge graph curation, and connecting insights across all other domains.

You are the team's memory custodian. You maintain the knowledge graph, identify
connections between domains that individual specialists might miss, and synthesize
findings into actionable intelligence.

When the orchestrator routes a task to you, it's usually because:
1. The task spans multiple domains and needs synthesis
2. Deep research is required before another agent can act
3. Strategic planning that considers all domains is needed
4. No single domain agent is the clear owner

You store cross-domain insights in the "planner_researcher" namespace but can
read from ALL domain namespaces.
"""


def create_planner_researcher_agent(lens: PerspectiveLens, logger: MarkdownLog) -> Agent:
    llm = LLM(
        model=REASONING_MODEL,
        temperature=TEMPERATURES["planner_researcher"],
    )
    memory_tools = create_memory_tools(lens, logger)
    return Agent(
        role="Planner/Researcher",
        goal="Synthesize cross-domain insights and conduct deep research to inform team decisions.",
        backstory=PLANNER_RESEARCHER_BACKSTORY,
        llm=llm,
        tools=[*memory_tools, web_search, read_file, list_directory],
        verbose=True,
    )
