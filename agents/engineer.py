"""Engineer agent — code, scripts, hardware, implementation."""

from crewai import Agent
from langchain_anthropic import ChatAnthropic

from config import AGENT_MODEL, TEMPERATURES, ANTHROPIC_API_KEY
from lenses.perspective import PerspectiveLens
from memory.markdown_log import MarkdownLog
from tools.memory_tools import create_memory_tools
from tools.code_tools import run_python_code, analyze_code_file
from tools.file_tools import read_file, write_file, list_directory

ENGINEER_BACKSTORY = """You are the Engineer on a non-hierarchical team.
Your domain covers: code implementation, scripting, debugging, testing, dependency management,
performance optimization, and hardware integration. You own engineering decisions.

You prioritize working, correct code over clever code. You write tests. You document
non-obvious decisions with inline comments. You don't over-engineer.

You store implementation notes, technical decisions, and debugging insights in the shared
memory fabric under the "engineer" domain namespace.
"""


def create_engineer_agent(lens: PerspectiveLens, logger: MarkdownLog) -> Agent:
    llm = ChatAnthropic(
        model=AGENT_MODEL,
        temperature=TEMPERATURES["engineer"],
        api_key=ANTHROPIC_API_KEY,
    )
    memory_tools = create_memory_tools(lens, logger)
    return Agent(
        role="Engineer",
        goal="Build correct, maintainable implementations and solve technical problems.",
        backstory=ENGINEER_BACKSTORY,
        llm=llm,
        tools=[*memory_tools, run_python_code, analyze_code_file, read_file, write_file, list_directory],
        verbose=True,
    )
