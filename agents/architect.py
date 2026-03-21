"""Architect agent — system design, specs, trade-off analysis."""

from crewai import Agent
from langchain_anthropic import ChatAnthropic

from config import AGENT_MODEL, TEMPERATURES, ANTHROPIC_API_KEY
from lenses.perspective import PerspectiveLens
from memory.markdown_log import MarkdownLog
from tools.memory_tools import create_memory_tools
from tools.file_tools import read_file, list_directory

ARCHITECT_BACKSTORY = """You are the Architect on a non-hierarchical team.
Your domain covers: system design, technical specifications, architecture trade-off analysis,
scalability planning, integration patterns, and technology selection. You own architecture decisions.

You think in systems. You identify constraints, dependencies, and failure modes before proposing
solutions. You produce clear specs that an engineer can implement without ambiguity.

You document architectural decisions as ADRs (Architecture Decision Records) in the shared
memory fabric under the "architect" domain namespace.
"""


def create_architect_agent(lens: PerspectiveLens, logger: MarkdownLog) -> Agent:
    llm = ChatAnthropic(
        model=AGENT_MODEL,
        temperature=TEMPERATURES["architect"],
        api_key=ANTHROPIC_API_KEY,
    )
    memory_tools = create_memory_tools(lens, logger)
    return Agent(
        role="Architect",
        goal="Design robust systems and produce clear specifications with explicit trade-offs.",
        backstory=ARCHITECT_BACKSTORY,
        llm=llm,
        tools=[*memory_tools, read_file, list_directory],
        verbose=True,
    )
