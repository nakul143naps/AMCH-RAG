"""Cross-encoder reranking node refining candidate chunks with FlashRank ONNX."""

import logging
import re
from typing import Any

from app.agent.state import AgentState
from app.retrieval.models import RetrievedChunk
from app.retrieval.reranker import RerankerService

logger = logging.getLogger(__name__)

_FILENAME_PATTERN = re.compile(r"\b[\w-]+\.(?:pdf|docx|pptx|csv|txt|md|html?)\b", re.IGNORECASE)
_QUERY_STOP_WORDS = {
    "about", "all", "are", "can", "could", "describe", "does", "find", "from",
    "give", "have", "how", "in", "is", "it", "list", "listed", "me", "of",
    "on", "please", "present", "show", "tell", "the", "there", "this", "what",
    "which", "who", "with", "would",
}


def _find_lexical_miss(
    query: str, candidates: list[RetrievedChunk], reranked: list[RetrievedChunk]
) -> RetrievedChunk | None:
    """Preserve a hybrid candidate whose explicit query terms the cross-encoder missed."""
    query_without_filenames = _FILENAME_PATTERN.sub("", query.lower())
    query_terms = {
        token
        for token in re.findall(r"[a-z0-9]+", query_without_filenames)
        if len(token) >= 4 and token not in _QUERY_STOP_WORDS
    }
    if not query_terms:
        return None

    reranked_ids = {chunk.chunk_id for chunk in reranked}
    lexical_matches = []
    for chunk in candidates:
        if chunk.chunk_id in reranked_ids:
            continue
        normalized_content = re.sub(r"[^a-z0-9]", "", chunk.content.lower())
        matched_terms = sum(
            token[: min(len(token), 8)] in normalized_content for token in query_terms
        )
        if matched_terms:
            lexical_matches.append((matched_terms, chunk.score, chunk))

    if not lexical_matches:
        return None
    return max(lexical_matches, key=lambda item: (item[0], item[1]))[2]


class RerankNode:
    """Reranks retrieved candidate chunks using lightweight local cross-attention."""

    def __init__(self, reranker: RerankerService | None = None) -> None:
        self.reranker = reranker or RerankerService.get_instance()

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Rerank candidates down to top-k high precision chunks."""
        chunks = state.get("retrieved_docs", [])
        query = (state.get("rewritten_query") or state.get("query", "")).strip()

        if not chunks:
            logger.info("RerankNode received 0 chunks, passing through")
            return {"retrieved_docs": []}

        logger.info(f"RerankNode reranking {len(chunks)} chunks for query: '{query}'")
        reranked = await self.reranker.async_rerank(
            query=query,
            chunks=chunks,
            top_k=5,
        )

        lexical_miss = _find_lexical_miss(query, chunks, reranked)
        if lexical_miss is not None:
            reranked.append(lexical_miss)
            logger.info(
                "RerankNode retained hybrid candidate %s with explicit query-term matches",
                lexical_miss.chunk_id,
            )

        logger.info(
            f"RerankNode selected {len(reranked)} top chunks after cross-encoder scoring"
        )
        return {"retrieved_docs": reranked}
