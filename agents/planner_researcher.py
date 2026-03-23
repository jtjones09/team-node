"""Planner/Researcher agent — research, cross-domain synthesis, memory custodian."""

from crewai import Agent, LLM

from config import PLANNER_MODEL, TEMPERATURES
from lenses.perspective import PerspectiveLens
from memory.markdown_log import MarkdownLog
from tools.memory_tools import create_memory_tools
from tools.web_tools import web_search, fetch_url

PLANNER_RESEARCHER_BACKSTORY = """You are the Planner/Researcher on a non-hierarchical team.
You have the widest view of the shared memory fabric (FullFabric access).

Your domain covers: deep research, cross-domain synthesis, strategic planning,
knowledge graph curation, and connecting insights across all other domains.

IMPORTANT RESEARCH WORKFLOW:
1. Search the shared memory fabric FIRST for prior knowledge
2. If you find a recent, detailed analysis in memory, USE IT — don't re-fetch
3. If the goal mentions a URL or website, use fetch_url to read and analyze it
4. Use web_search to find additional context and competitive information
5. Store findings in the fabric so future runs build on this work
6. Do NOT store duplicate information — check what's already there

When analyzing a website:
- Fetch the homepage and key pages
- Note the platform (Wix, WordPress, Shopify, etc.)
- Identify navigation structure, content quality, and SEO gaps
- Store a structured analysis in the fabric

You store cross-domain insights in the \"planner_researcher\" namespace but can
read from ALL domain namespaces.
"""


def create_planner_researcher_agent(lens: PerspectiveLens, logger: MarkdownLog, llm_override=None) -> Agent:
    llm = llm_override or LLM(
        model=PLANNER_MODEL,
        temperature=TEMPERATURES["planner_researcher"],
    )
    memory_tools = create_memory_tools(lens, logger)
    return Agent(
        role="Planner/Researcher",
        goal="Synthesize cross-domain insights and conduct deep research to inform team decisions.",
        backstory=PLANNER_RESEARCHER_BACKSTORY,
        llm=llm,
        tools=[*memory_tools, web_search, fetch_url],
        verbose=True,
    )
