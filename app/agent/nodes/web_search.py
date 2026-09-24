"""Web search fallback node executing external search when knowledge base is insufficient."""

import logging
from typing import Any

from app.agent.state import AgentState
from app.agent.tools.web_search import WebSearchTool
from app.retrieval.models import RetrievedChunk

logger = logging.getLogger(__name__)


class WebSearchNode:
    """Executes live web search fallback when internal documents lack necessary information."""

    def __init__(self, tool: WebSearchTool | None = None) -> None:
        self.tool = tool or WebSearchTool()

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Search the web for the query and format web passages into RetrievedChunks."""
        query = (state.get("rewritten_query") or state.get("query", "")).strip()

        logger.info(f"WebSearchNode initiating fallback web search for: '{query}'")
        raw_results = await self.tool.async_search(query=query, max_results=5)

        web_chunks: list[RetrievedChunk] = []
        for idx, res in enumerate(raw_results, start=1):
            title = res.get("title", f"Web Result {idx}")
            url = res.get("url", "")
            snippet = res.get("snippet", "")
            content = f"[Web Result: {title}]\n{snippet}\nURL: {url}"

            web_chunks.append(
                RetrievedChunk(
                    chunk_id=f"web_chunk_{idx}",
                    doc_id="web_search",
                    content=content,
                    source=url if url else title,
                    source_type="web",
                    score=1.0,
                    section=title,
                    metadata={"source_type": "web", "url": url, "title": title},
                )
            )

        logger.info(
            f"WebSearchNode converted {len(web_chunks)} web results into candidate chunks"
        )

        return {
            "web_results": raw_results,
            "retrieved_docs": web_chunks,
        }
