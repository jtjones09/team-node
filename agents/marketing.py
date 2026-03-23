"""Marketing agent — LinkedIn voice, content strategy, positioning, site design."""

from crewai import Agent, LLM

from config import AGENT_MODEL, TEMPERATURES
from voice.jeremy_voice import get_voice_prompt
from lenses.perspective import PerspectiveLens
from memory.markdown_log import MarkdownLog
from tools.memory_tools import create_memory_tools
from tools.web_tools import web_search, fetch_url

MARKETING_BACKSTORY = """You are the Marketing specialist on a non-hierarchical team.
Your domain covers: LinkedIn content, content strategy, brand positioning, audience engagement,
messaging, and website design/UX recommendations.

You write in Jeremy's voice. Every piece of content you produce must pass the voice constraints.
You validate LinkedIn posts and comments against the voice rules before delivering them.

When asked to create a website mockup or redesign plan, include the full HTML/CSS code
directly in your final answer. Do NOT try to save files — the system handles that
automatically. Just include the HTML in your response.

You store your insights, decisions, and research in the shared memory fabric under the
\"marketing\" domain namespace. You can read shared memories from other domains but you
write only to your own namespace.

{voice_constraints}
""".format(voice_constraints=get_voice_prompt())


def create_marketing_agent(lens: PerspectiveLens, logger: MarkdownLog, llm_override=None) -> Agent:
    llm = llm_override or LLM(
        model=AGENT_MODEL,
        temperature=TEMPERATURES["marketing"],
    )
    memory_tools = create_memory_tools(lens, logger)
    return Agent(
        role="Marketing Specialist",
        goal="Create compelling content and positioning strategy using Jeremy's authentic voice.",
        backstory=MARKETING_BACKSTORY,
        llm=llm,
        tools=[*memory_tools, web_search, fetch_url],
        verbose=True,
    )
