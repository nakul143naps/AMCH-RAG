"""Cross-encoder reranking node refining candidate chunks with FlashRank ONNX."""

import logging
from typing import Any

from app.agent.state import AgentState
from app.retrieval.reranker import RerankerService

logger = logging.getLogger(__name__)


class RerankNode:
    """Reranks retrieved candidate chunks using lightweight local cross-attention."""

    def __init__(self, reranker: RerankerService | None = None) -> None:
        self.reranker = reranker or RerankerService.get_instance()

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Rerank candidates down to top-k high precision chunks."""
        chunks = state.get("retrieved_docs", [])
        query = state.get("query", "").strip()

        if not chunks:
            logger.info("RerankNode received 0 chunks, passing through")
            return {"retrieved_docs": []}

        logger.info(f"RerankNode reranking {len(chunks)} chunks for query: '{query}'")
        reranked = await self.reranker.async_rerank(
            query=query,
            chunks=chunks,
            top_k=5,
        )

        logger.info(
            f"RerankNode selected {len(reranked)} top chunks after cross-encoder scoring"
        )
        return {"retrieved_docs": reranked}
