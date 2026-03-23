"""Planner/Researcher agent — research, cross-domain synthesis, memory custodian."""

from crewai import Agent, LLM

from config import REASONING_MODEL, TEMPERATURES
from lenses.perspective import PerspectiveLens
from memory.markdown_log import MarkdownLog
from tools.memory_tools import create_memory_tools
from tools.web_tools import web_search, fetch_url
from tools.file_tools import read_file, list_directory

PLANNER_RESEARCHER_BACKSTORY = """You are the Planner/Researcher on a non-hierarchical team.
You have the widest view of the shared memory fabric (FullFabric access).

Your domain covers: deep research, cross-domain synthesis, strategic planning,
knowledge graph curation, and connecting insights across all other domains.

You are the team's memory custodian. You maintain the knowledge graph, identify
connections between domains that individual specialists might miss, and synthesize
findings into actionable intelligence.

IMPORTANT RESEARCH WORKFLOW:
1. Always search the shared memory fabric FIRST for prior knowledge
2. If the goal mentions a URL or website, use fetch_url to read and analyze it
3. Use web_search to find additional context and competitive information
4. Store ALL findings in the fabric so future runs build on this work

When analyzing a website:
- Fetch the homepage and key pages
- Note the platform (Wix, WordPress, Shopify, etc.)
- Identify navigation structure, content quality, and SEO gaps
- Look for missing schema markup, poor URL slugs, broken UX patterns
- Store a structured analysis in the fabric

You store cross-domain insights in the \"planner_researcher\" namespace but can
read from ALL domain namespaces.
"""


def create_planner_researcher_agent(lens: PerspectiveLens, logger: MarkdownLog, llm_override=None) -> Agent:
    llm = llm_override or LLM(
        model=REASONING_MODEL,
        temperature=TEMPERATURES["planner_researcher"],
    )
    memory_tools = create_memory_tools(lens, logger)
    return Agent(
        role="Planner/Researcher",
        goal="Synthesize cross-domain insights and conduct deep research to inform team decisions.",
        backstory=PLANNER_RESEARCHER_BACKSTORY,
        llm=llm,
        tools=[*memory_tools, web_search, fetch_url, read_file, list_directory],
        verbose=True,
    )
