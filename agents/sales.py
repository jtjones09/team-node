"""Sales agent — outreach, partnerships, pipeline."""

from crewai import Agent, LLM

from config import AGENT_MODEL, TEMPERATURES
from voice.jeremy_voice import get_voice_prompt
from lenses.perspective import PerspectiveLens
from memory.markdown_log import MarkdownLog
from tools.memory_tools import create_memory_tools
from tools.web_tools import web_search

SALES_BACKSTORY = """You are the Sales specialist on a non-hierarchical team.
Your domain covers: outreach strategy, partnership development, pipeline management,
prospect research, and deal progression. You own sales decisions.

You communicate externally in Jeremy's voice. All outreach, proposals, and prospect-facing
content must pass the voice constraints.

You store insights and pipeline intelligence in the shared memory fabric under the
"sales" domain namespace.

{voice_constraints}
""".format(voice_constraints=get_voice_prompt())


def create_sales_agent(lens: PerspectiveLens, logger: MarkdownLog) -> Agent:
    llm = LLM(
        model=AGENT_MODEL,
        temperature=TEMPERATURES["sales"],
    )
    memory_tools = create_memory_tools(lens, logger)
    return Agent(
        role="Sales Specialist",
        goal="Drive outreach and partnerships with authentic, direct communication.",
        backstory=SALES_BACKSTORY,
        llm=llm,
        tools=[*memory_tools, web_search],
        verbose=True,
    )
