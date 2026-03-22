"""Web search tool using Brave Search API.

Brave has its own independent search index (not scraping Google).
Free tier: 2,000 queries/month. No credit card required.
Get your API key at: https://brave.com/search/api/

Set BRAVE_SEARCH_API_KEY in environment or ~/.config/teamnode/config.json
"""

import json
import os
from pathlib import Path

import requests
from crewai.tools import tool

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"


def _get_brave_key() -> str:
    """Get Brave Search API key from environment or config file."""
    key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if key:
        return key
    config_file = Path.home() / ".config" / "teamnode" / "config.json"
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
        return config.get("brave_search_api_key", "")
    return ""


@tool("Web Search")
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using Brave Search.

    Args:
        query: The search query.
        max_results: Maximum number of results to return.
    """
    api_key = _get_brave_key()
    if not api_key:
        return "Web search unavailable: BRAVE_SEARCH_API_KEY not set. Get a free key at brave.com/search/api/"

    try:
        response = requests.get(
            BRAVE_API_URL,
            headers={
                "X-Subscription-Token": api_key,
                "Accept": "application/json",
            },
            params={
                "q": query,
                "count": min(max_results, 20),
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("web", {}).get("results", [])
        if not results:
            return "No results found."

        lines = []
        for r in results[:max_results]:
            title = r.get("title", "No title")
            url = r.get("url", "")
            description = r.get("description", "")
            lines.append(f"**{title}**\n{url}\n{description}\n")
        return "\n".join(lines)

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return "Web search failed: Invalid BRAVE_SEARCH_API_KEY."
        elif e.response.status_code == 429:
            return "Web search failed: Rate limit exceeded. Free tier allows 2,000 queries/month."
        return f"Web search failed: {e}"
    except Exception as e:
        return f"Web search failed: {e}"
