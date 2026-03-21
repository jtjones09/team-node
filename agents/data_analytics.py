"""Data/Analytics agent — metrics, evidence, competitive intel."""

from crewai import Agent, LLM

from config import AGENT_MODEL, TEMPERATURES
from lenses.perspective import PerspectiveLens
from memory.markdown_log import MarkdownLog
from tools.memory_tools import create_memory_tools
from tools.web_tools import web_search
from tools.code_tools import run_python_code

DATA_ANALYTICS_BACKSTORY = """You are the Data/Analytics specialist on a non-hierarchical team.
Your domain covers: metrics definition and tracking, evidence gathering, competitive intelligence,
market analysis, benchmarking, and data-driven decision support. You own analytics decisions.

You deal in evidence, not opinions. Every claim you make should be backed by data or
clearly labeled as a hypothesis. You distinguish between correlation and causation.

You can run Python code to analyze data, compute statistics, or generate visualizations.

You store analytical findings, competitive intelligence, and metric definitions in the
shared memory fabric under the "data_analytics" domain namespace.
"""


def create_data_analytics_agent(lens: PerspectiveLens, logger: MarkdownLog, llm_override=None) -> Agent:
    llm = llm_override or LLM(
        model=AGENT_MODEL,
        temperature=TEMPERATURES["data_analytics"],
    )
    memory_tools = create_memory_tools(lens, logger)
    return Agent(
        role="Data/Analytics Specialist",
        goal="Provide evidence-based insights, competitive intelligence, and metric-driven analysis.",
        backstory=DATA_ANALYTICS_BACKSTORY,
        llm=llm,
        tools=[*memory_tools, web_search, run_python_code],
        verbose=True,
    )
