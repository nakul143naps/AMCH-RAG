"""Local cross-encoder reranker using FlashRank ONNX models."""

import asyncio
from typing import Optional

from flashrank import Ranker, RerankRequest

from app.config import get_settings
from app.retrieval.models import RetrievedChunk


class RerankerService:
    """Provides high-precision local cross-encoder reranking over retrieved candidate chunks."""

    _instance: Optional["RerankerService"] = None

    @classmethod
    def get_instance(cls, model_name: str | None = None) -> "RerankerService":
        """Return singleton instance of RerankerService."""
        if cls._instance is None:
            cls._instance = RerankerService(model_name=model_name)
        return cls._instance

    def __init__(self, model_name: str | None = None) -> None:
        """Initialize FlashRank cross-encoder model."""
        settings = get_settings()
        self.model_name = model_name or settings.RERANKER_MODEL
        self._ranker: Ranker | None = None

    @property
    def ranker(self) -> Ranker:
        """Lazy-load Ranker with fallback to avoid unnecessary startup overhead or download failures."""
        if self._ranker is None:
            try:
                self._ranker = Ranker(model_name=self.model_name)
            except Exception:  # noqa: BLE001
                self.model_name = "ms-marco-TinyBERT-L-2-v2"
                self._ranker = Ranker(model_name=self.model_name)
        return self._ranker

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Rerank candidates using cross-attention over query-document pairs.

        Args:
            query: The user query string.
            chunks: Initial candidate chunks from hybrid retrieval (top-N).
            top_k: Optional limit on the number of reranked chunks to return.

        Returns:
            List of RetrievedChunk instances re-ordered by cross-encoder relevance score.
        """
        if not chunks:
            return []

        # Prepare passages for FlashRank (maintaining original index reference)
        passages = [
            {"id": idx, "text": chunk.content} for idx, chunk in enumerate(chunks)
        ]

        rerank_req = RerankRequest(query=query, passages=passages)
        results = self.ranker.rerank(rerank_req)

        # Build reranked list with updated cross-encoder scores
        reranked_chunks: list[RetrievedChunk] = []
        for item in results:
            orig_idx = int(item["id"])
            chunk = chunks[orig_idx].model_copy(deep=True)
            chunk.score = float(item["score"])
            reranked_chunks.append(chunk)

        # Sort by score descending
        reranked_chunks.sort(key=lambda x: x.score, reverse=True)

        if top_k is not None:
            reranked_chunks = reranked_chunks[:top_k]

        return reranked_chunks

    async def async_rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Asynchronously offload CPU-bound cross-encoder reranking to thread pool per Rule §3."""
        return await asyncio.to_thread(self.rerank, query, chunks, top_k)
