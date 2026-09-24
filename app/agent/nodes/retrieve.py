"""Hybrid retrieval node executing dense + sparse search with native Qdrant RRF."""

import logging
from typing import Any

from app.agent.guardrails import InputGuardrails
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
        existing_flags = list(state.get("guardrail_flags", []))

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

        # Neutralize any indirect prompt injections lurking inside retrieved document passages
        sanitized_chunks = []
        new_flags = list(existing_flags)
        for chunk in chunks:
            clean_chunk, chunk_flags = InputGuardrails.sanitize_retrieved_chunk(chunk)
            sanitized_chunks.append(clean_chunk)
            new_flags.extend(chunk_flags)

        return {
            "retrieved_docs": sanitized_chunks,
            "guardrail_flags": new_flags,
        }
