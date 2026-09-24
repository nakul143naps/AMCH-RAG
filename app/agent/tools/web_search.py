"""Web Search tool using DuckDuckGo search for zero-cost open-web fallback."""

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WebSearchResult(BaseModel):
    """Normalized search result model from external web providers."""

    title: str = Field(description="Title of the web page")
    url: str = Field(description="URL link to the web page")
    snippet: str = Field(description="Summary text / snippet of the content")


class WebSearchTool:
    """Wrapper around DuckDuckGo search with robust multi-backend fallback and error handling."""

    def __init__(self, max_results: int = 5) -> None:
        self.default_max_results = max_results

    def _sync_search(self, query: str, max_results: int) -> list[dict[str, str]]:
        """Synchronously execute web search with multi-backend fallback."""
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            logger.error("duckduckgo_search package not installed")
            return []

        ddgs = DDGS()
        results: list[dict[str, Any]] = []

        # Try backend='lite' first (fastest and cleanest)
        try:
            raw = list(ddgs.text(query, backend="lite", max_results=max_results))
            if raw:
                results = raw
        except Exception as e:  # noqa: BLE001
            logger.debug(f"DDGS lite backend search failed for '{query}': {e}")

        # Fallback to backend='html' if lite returned nothing
        if not results:
            try:
                raw = list(ddgs.text(query, backend="html", max_results=max_results))
                if raw:
                    results = raw
            except Exception as e:  # noqa: BLE001
                logger.debug(f"DDGS html backend search failed for '{query}': {e}")

        # Fallback to news if web text was empty
        if not results:
            try:
                raw = list(ddgs.news(query, max_results=max_results))
                if raw:
                    results = raw
            except Exception as e:  # noqa: BLE001
                logger.debug(f"DDGS news search failed for '{query}': {e}")

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
        """Asynchronously search the web offloaded to a worker thread."""
        limit = max_results or self.default_max_results
        clean_query = query.strip()
        if not clean_query:
            return []

        logger.info(f"WebSearchTool searching web for: '{clean_query}' (limit: {limit})")
        try:
            results = await asyncio.to_thread(self._sync_search, clean_query, limit)
            logger.info(f"WebSearchTool retrieved {len(results)} web results for: '{clean_query}'")
            return results
        except Exception as e:  # noqa: BLE001
            logger.warning(f"WebSearchTool encountered unexpected error for '{clean_query}': {e}")
            return []
