"""Web search tool with cross-validated results from multiple search engines.

Uses Brave Search (own index) and Bing Web Search (own index) to cross-validate
results. When the same URL or topic appears in both engines, confidence is higher.
Results that only appear in one engine are included but flagged as single-source.

This is the Ecphory pattern applied to search: resonance across multiple signals,
confidence derived from convergence.

API Keys:
  Brave: BRAVE_SEARCH_API_KEY (free tier, 2,000/month, brave.com/search/api)
  Bing:  BING_SEARCH_API_KEY  (Azure Cognitive Services, free tier 1,000/month)

Either engine works standalone if only one key is configured.
"""

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import requests
from crewai.tools import tool

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
BING_API_URL = "https://api.bing.microsoft.com/v7.0/search"


def _get_key(env_var: str, config_key: str) -> str:
    """Get API key from environment or config file."""
    key = os.environ.get(env_var)
    if key:
        return key
    config_file = Path.home() / ".config" / "teamnode" / "config.json"
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
        return config.get(config_key, "")
    return ""


def _search_brave(query: str, count: int) -> list[dict]:
    """Search using Brave Search API."""
    api_key = _get_key("BRAVE_SEARCH_API_KEY", "brave_search_api_key")
    if not api_key:
        return []
    try:
        response = requests.get(
            BRAVE_API_URL,
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            params={"q": query, "count": min(count, 20)},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json().get("web", {}).get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("description", ""),
                "source": "brave",
            }
            for r in results
        ]
    except Exception:
        return []


def _search_bing(query: str, count: int) -> list[dict]:
    """Search using Bing Web Search API."""
    api_key = _get_key("BING_SEARCH_API_KEY", "bing_search_api_key")
    if not api_key:
        return []
    try:
        response = requests.get(
            BING_API_URL,
            headers={"Ocp-Apim-Subscription-Key": api_key},
            params={"q": query, "count": min(count, 50)},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json().get("webPages", {}).get("value", [])
        return [
            {
                "title": r.get("name", ""),
                "url": r.get("url", ""),
                "description": r.get("snippet", ""),
                "source": "bing",
            }
            for r in results
        ]
    except Exception:
        return []


def _normalize_url(url: str) -> str:
    """Normalize URL for comparison (strip www, trailing slash, protocol)."""
    parsed = urlparse(url.lower().rstrip("/"))
    host = parsed.netloc.replace("www.", "")
    return f"{host}{parsed.path}"


def _cross_validate(brave_results: list[dict], bing_results: list[dict]) -> list[dict]:
    """Cross-validate results from both engines. Convergent results get higher confidence."""
    bing_urls = {}
    for r in bing_results:
        norm = _normalize_url(r["url"])
        bing_urls[norm] = r

    validated = []
    seen_urls = set()

    for r in brave_results:
        norm = _normalize_url(r["url"])
        if norm in seen_urls:
            continue
        seen_urls.add(norm)

        if norm in bing_urls:
            r["confidence"] = "high"
            r["sources"] = "brave+bing"
            validated.append(r)
            del bing_urls[norm]
        else:
            r["confidence"] = "single"
            r["sources"] = "brave"
            validated.append(r)

    for norm, r in bing_urls.items():
        if norm in seen_urls:
            continue
        seen_urls.add(norm)
        r["confidence"] = "single"
        r["sources"] = "bing"
        validated.append(r)

    validated.sort(key=lambda x: (0 if x["confidence"] == "high" else 1))
    return validated


@tool("Web Search")
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using cross-validated results from Brave and Bing.

    Results that appear in both search engines are marked as high confidence.
    Single-source results are included but flagged.

    Args:
        query: The search query.
        max_results: Maximum number of results to return.
    """
    brave_results = _search_brave(query, max_results * 2)
    bing_results = _search_bing(query, max_results * 2)

    if not brave_results and not bing_results:
        return "Web search unavailable: No search API keys configured. Set BRAVE_SEARCH_API_KEY and/or BING_SEARCH_API_KEY."

    if not brave_results:
        results = bing_results[:max_results]
    elif not bing_results:
        results = brave_results[:max_results]
    else:
        results = _cross_validate(brave_results, bing_results)[:max_results]

    if not results:
        return "No results found."

    lines = []
    for r in results:
        confidence = r.get("confidence", "")
        sources = r.get("sources", r.get("source", ""))
        tag = f" [verified: {sources}]" if confidence == "high" else f" [{sources}]"
        lines.append(f"**{r['title']}**{tag}\n{r['url']}\n{r['description']}\n")
    return "\n".join(lines)
