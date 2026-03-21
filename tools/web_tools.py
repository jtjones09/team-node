"""Web search tool wrapper using DuckDuckGo."""

from crewai.tools import tool
from duckduckgo_search import DDGS


@tool("Web Search")
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo.

    Args:
        query: The search query.
        max_results: Maximum number of results to return.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        lines = []
        for r in results:
            lines.append(f"**{r.get('title', 'No title')}**\n{r.get('href', '')}\n{r.get('body', '')}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"Search failed: {e}"
