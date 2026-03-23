"""Web tools: search (Brave) + fetch (read any URL) + cross-validation.

Primary search: Brave Search API (own independent index)
Secondary: Pluggable — set SECONDARY_SEARCH_URL for SearXNG (future)

fetch_url reads any webpage and returns its text content. This lets agents
analyze websites, read articles, and pull context from URLs mentioned in goals.

API Keys:
  Brave: BRAVE_SEARCH_API_KEY (brave.com/search/api, $5 free credits/month)
"""

import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from crewai.tools import tool

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"


def _get_key(env_var: str, config_key: str) -> str:
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


def _search_secondary(query: str, count: int) -> list[dict]:
    base_url = os.environ.get("SECONDARY_SEARCH_URL", "")
    if not base_url:
        return []
    try:
        response = requests.get(
            f"{base_url}/search",
            params={"q": query, "format": "json"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("content", ""),
                "source": "secondary",
            }
            for r in results[:count]
        ]
    except Exception:
        return []


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.lower().rstrip("/"))
    host = parsed.netloc.replace("www.", "")
    return f"{host}{parsed.path}"


def _cross_validate(primary: list[dict], secondary: list[dict]) -> list[dict]:
    secondary_urls = {}
    for r in secondary:
        norm = _normalize_url(r["url"])
        secondary_urls[norm] = r

    validated = []
    seen = set()

    for r in primary:
        norm = _normalize_url(r["url"])
        if norm in seen:
            continue
        seen.add(norm)
        if norm in secondary_urls:
            r["confidence"] = "verified"
            r["sources"] = "brave+secondary"
            del secondary_urls[norm]
        else:
            r["confidence"] = "single"
            r["sources"] = "brave"
        validated.append(r)

    for norm, r in secondary_urls.items():
        if norm not in seen:
            seen.add(norm)
            r["confidence"] = "single"
            r["sources"] = "secondary"
            validated.append(r)

    validated.sort(key=lambda x: (0 if x["confidence"] == "verified" else 1))
    return validated


def _strip_html(html: str) -> str:
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    return text


@tool("Web Search")
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for current information.

    Uses Brave Search as primary source. If a secondary source is configured
    (SearXNG etc), results are cross-validated for higher confidence.

    Args:
        query: The search query.
        max_results: Maximum number of results to return.
    """
    brave_results = _search_brave(query, max_results * 2)
    secondary_results = _search_secondary(query, max_results * 2)

    if not brave_results and not secondary_results:
        return "Web search unavailable: BRAVE_SEARCH_API_KEY not set. Get a key at brave.com/search/api/"

    if not secondary_results:
        results = brave_results[:max_results]
    elif not brave_results:
        results = secondary_results[:max_results]
    else:
        results = _cross_validate(brave_results, secondary_results)[:max_results]

    if not results:
        return "No results found."

    lines = []
    for r in results:
        confidence = r.get("confidence", "")
        sources = r.get("sources", r.get("source", ""))
        if confidence == "verified":
            tag = f" [verified: {sources}]"
        elif confidence == "single" and secondary_results:
            tag = f" [{sources}]"
        else:
            tag = ""
        lines.append(f"**{r['title']}**{tag}\n{r['url']}\n{r['description']}\n")
    return "\n".join(lines)


@tool("Fetch URL")
def fetch_url(url: str) -> str:
    """Fetch and read the text content of any webpage.

    Use this to analyze a website, read an article, or pull content from
    a URL mentioned in the goal. Returns the page text (HTML stripped).

    Args:
        url: The full URL to fetch (must include https:// or http://).
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; TeamNode/1.0; +https://hotashstudios.com)",
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=15,
            allow_redirects=True,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return f"Cannot read this content type: {content_type}"

        text = _strip_html(response.text)

        if len(text) > 4000:
            text = text[:4000] + "\n\n[...truncated, page continues...]"

        return f"Content from {url}:\n\n{text}"

    except requests.exceptions.ConnectionError:
        return f"Could not connect to {url}"
    except requests.exceptions.Timeout:
        return f"Request to {url} timed out"
    except requests.exceptions.HTTPError as e:
        return f"HTTP error fetching {url}: {e.response.status_code}"
    except Exception as e:
        return f"Error fetching {url}: {e}"
