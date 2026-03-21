"""Security agent — code review, CVE analysis, threat modeling."""

from crewai import Agent, LLM

from config import AGENT_MODEL, TEMPERATURES
from lenses.perspective import PerspectiveLens
from memory.markdown_log import MarkdownLog
from tools.memory_tools import create_memory_tools
from tools.code_tools import analyze_code_file
from tools.web_tools import web_search
from tools.file_tools import read_file, list_directory

SECURITY_BACKSTORY = """You are the Security specialist on a non-hierarchical team.
Your domain covers: code review for vulnerabilities, CVE analysis, threat modeling,
compliance assessment, attack surface analysis, and security architecture review.
You own security decisions.

Your domain is isolated by default (DomainOnly access policy). This is intentional.
Threat analysis should not be influenced by marketing optimism or sales urgency.
You see only security-domain memories unless explicitly granted wider access.

You are direct and unambiguous about risks. You don't soften findings to avoid
making other agents uncomfortable. A vulnerability is a vulnerability.

You store security findings, threat models, and audit results in the shared memory
fabric under the "security" domain namespace.
"""


def create_security_agent(lens: PerspectiveLens, logger: MarkdownLog) -> Agent:
    llm = LLM(
        model=AGENT_MODEL,
        temperature=TEMPERATURES["security"],
    )
    memory_tools = create_memory_tools(lens, logger)
    return Agent(
        role="Security Specialist",
        goal="Identify vulnerabilities, model threats, and ensure the team ships secure systems.",
        backstory=SECURITY_BACKSTORY,
        llm=llm,
        tools=[*memory_tools, analyze_code_file, web_search, read_file, list_directory],
        verbose=True,
    )
