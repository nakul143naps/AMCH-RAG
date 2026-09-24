"""Hybrid retrieval node executing dense + sparse search with native Qdrant RRF."""

import logging
from typing import Any

from app.agent.state import AgentState
from app.retrieval.retriever import HybridRetriever

logger = logging.getLogger(__name__)


class RetrieveNode:
    """Executes single-roundtrip hybrid retrieval across dense and sparse vectors."""

    def __init__(self, retriever: HybridRetriever | None = None) -> None:
        self.retriever = retriever or HybridRetriever()

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Retrieve candidate document chunks matching the query and tenant filters."""
        query = (state.get("rewritten_query") or state.get("query", "")).strip()
        access_level = state.get("access_level", "default")

        logger.info(f"RetrieveNode searching for: '{query}' (tenant: {access_level})")

        # Retrieve candidates for downstream reranking (rerank=False here so rerank node handles it)
        chunks = await self.retriever.async_retrieve(
            query=query,
            limit=10,
            mode="hybrid",
            access_levels=access_level,
            rerank=False,
        )

        logger.info(f"RetrieveNode retrieved {len(chunks)} candidate chunks")
        return {"retrieved_docs": chunks}
