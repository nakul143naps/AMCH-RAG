"""Web Search tool using DuckDuckGo search for zero-cost open-web fallback."""

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger(__name__)


class WebSearchResult(BaseModel):
    """Normalized search result model from external web providers."""

    title: str = Field(description="Title of the web page")
    url: str = Field(description="URL link to the web page")
    snippet: str = Field(description="Summary text / snippet of the content")


class WebSearchTool:
    """Wrapper around Tavily AI Search and DuckDuckGo with robust fallback and error handling."""

    def __init__(self, max_results: int = 5) -> None:
        self.default_max_results = max_results
        self.settings = get_settings()

    async def _tavily_search(self, query: str, max_results: int) -> list[dict[str, str]]:
        """Search using Tavily AI Search API when TAVILY_API_KEY is configured."""
        api_key = self.settings.TAVILY_API_KEY.strip()
        if not api_key or api_key == "your_tavily_api_key_here":
            return []

        import httpx

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                        "include_answer": False,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    results: list[dict[str, str]] = []
                    for item in data.get("results", []):
                        title = str(item.get("title", "")).strip()
                        url = str(item.get("url", "")).strip()
                        snippet = str(item.get("content", "")).strip()
                        if title and (url or snippet):
                            results.append({"title": title, "url": url, "snippet": snippet})
                    if results:
                        logger.info(f"Tavily search retrieved {len(results)} results for: '{query}'")
                        return results
                else:
                    logger.warning(
                        f"Tavily search returned status {response.status_code}: {response.text[:200]}"
                    )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Tavily search failed for '{query}': {e}")

        return []

    def _sync_search(self, query: str, max_results: int) -> list[dict[str, str]]:
        """Synchronously execute DuckDuckGo search with multi-backend fallback."""
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            logger.error("duckduckgo_search package not installed")
            return []

        ddgs = DDGS()
        results: list[dict[str, Any]] = []

        # Try default backend first
        try:
            raw = list(ddgs.text(query, max_results=max_results))
            if raw:
                results = raw
        except Exception as e:  # noqa: BLE001
            logger.debug(f"DDGS default backend search failed for '{query}': {e}")

        # Fallback to backend='lite'
        if not results:
            try:
                raw = list(ddgs.text(query, backend="lite", max_results=max_results))
                if raw:
                    results = raw
            except Exception as e:  # noqa: BLE001
                logger.debug(f"DDGS lite backend search failed for '{query}': {e}")

        # Fallback to backend='html'
        if not results:
            try:
                raw = list(ddgs.text(query, backend="html", max_results=max_results))
                if raw:
                    results = raw
            except Exception as e:  # noqa: BLE001
                logger.debug(f"DDGS html backend search failed for '{query}': {e}")

        normalized: list[dict[str, str]] = []
        for item in results:
            title = str(item.get("title", "")).strip()
            url = str(item.get("href") or item.get("url") or "").strip()
            snippet = str(item.get("body") or item.get("snippet") or "").strip()
            if title and (url or snippet):
                normalized.append(
                    {
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                    }
                )

        return normalized

    async def async_search(
        self, query: str, max_results: int | None = None
    ) -> list[dict[str, str]]:
        """Asynchronously search web using Tavily first, falling back to DuckDuckGo."""
        limit = max_results or self.default_max_results
        clean_query = query.strip()
        if not clean_query:
            return []

        logger.info(f"WebSearchTool searching web for: '{clean_query}' (limit: {limit})")

        # 1. Try Tavily AI Search first if configured
        tavily_results = await self._tavily_search(clean_query, limit)
        if tavily_results:
            return tavily_results

        # 2. Fallback to DuckDuckGo search
        try:
            results = await asyncio.to_thread(self._sync_search, clean_query, limit)
            logger.info(f"WebSearchTool retrieved {len(results)} web results for: '{clean_query}'")
            return results
        except Exception as e:  # noqa: BLE001
            logger.warning(f"WebSearchTool encountered unexpected error for '{clean_query}': {e}")
            return []
