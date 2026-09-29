"""Hybrid retriever orchestrating Dense + BM25 sparse retrieval fused with RRF."""

import asyncio
from typing import Any

from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    ScoredPoint,
)

from app.retrieval.embeddings import EmbeddingEngine, SparseVectorData
from app.retrieval.models import RetrievalQuery, RetrievedChunk
from app.retrieval.reranker import RerankerService
from app.retrieval.vector_store import VectorStoreManager


class HybridRetriever:
    """Performs hybrid dense and BM25 sparse retrieval with Reciprocal Rank Fusion (RRF)."""

    def __init__(
        self,
        vector_mgr: VectorStoreManager | None = None,
        embedding_engine: EmbeddingEngine | None = None,
        reranker: RerankerService | None = None,
    ) -> None:
        """Initialize retriever with vector store, embedding engine, and reranker."""
        self.vector_mgr = vector_mgr or VectorStoreManager.get_instance()
        self.embedding_engine = embedding_engine or EmbeddingEngine.get_instance()
        self.reranker = reranker or RerankerService.get_instance()

    ACCESS_HIERARCHY: dict[str, list[str]] = {
        "admin": ["admin", "confidential", "internal", "default", "public"],
        "confidential": ["confidential", "internal", "default", "public"],
        "internal": ["internal", "default", "public"],
        "default": ["default", "public", "internal"],
        "public": ["public", "default"],
    }

    def _build_filter(
        self,
        access_levels: str | list[str] | None = None,
        doc_ids: str | list[str] | None = None,
        source_types: str | list[str] | None = None,
        filter_criteria: dict[str, Any] | None = None,
    ) -> Filter | None:
        """Construct Qdrant Filter with hierarchical access level and metadata isolation."""
        must_conditions = []

        # Access levels filter with role hierarchy expansion
        if access_levels is not None and access_levels != "all":
            if isinstance(access_levels, str):
                allowed_levels = self.ACCESS_HIERARCHY.get(
                    access_levels.lower(), [access_levels]
                )
            elif isinstance(access_levels, list) and access_levels:
                allowed_set: set[str] = set()
                for lvl in access_levels:
                    allowed_set.update(self.ACCESS_HIERARCHY.get(lvl.lower(), [lvl]))
                allowed_levels = list(allowed_set)
            else:
                allowed_levels = []

            if allowed_levels:
                if len(allowed_levels) == 1:
                    must_conditions.append(
                        FieldCondition(
                            key="access_level", match=MatchValue(value=allowed_levels[0])
                        )
                    )
                else:
                    must_conditions.append(
                        FieldCondition(
                            key="access_level", match=MatchAny(any=allowed_levels)
                        )
                    )

        # Document IDs filter
        if doc_ids is not None:
            if isinstance(doc_ids, str):
                must_conditions.append(
                    FieldCondition(key="doc_id", match=MatchValue(value=doc_ids))
                )
            elif isinstance(doc_ids, list) and doc_ids:
                if len(doc_ids) == 1:
                    must_conditions.append(
                        FieldCondition(key="doc_id", match=MatchValue(value=doc_ids[0]))
                    )
                else:
                    must_conditions.append(
                        FieldCondition(key="doc_id", match=MatchAny(any=doc_ids))
                    )

        # Source types filter
        if source_types is not None:
            if isinstance(source_types, str):
                must_conditions.append(
                    FieldCondition(
                        key="source_type", match=MatchValue(value=source_types)
                    )
                )
            elif isinstance(source_types, list) and source_types:
                if len(source_types) == 1:
                    must_conditions.append(
                        FieldCondition(
                            key="source_type", match=MatchValue(value=source_types[0])
                        )
                    )
                else:
                    must_conditions.append(
                        FieldCondition(
                            key="source_type", match=MatchAny(any=source_types)
                        )
                    )

        # Generic arbitrary metadata filters
        if filter_criteria:
            for key, val in filter_criteria.items():
                if isinstance(val, list):
                    must_conditions.append(
                        FieldCondition(key=key, match=MatchAny(any=val))
                    )
                else:
                    must_conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=val))
                    )

        if not must_conditions:
            return None

        return Filter(must=must_conditions)

    def retrieve(
        self,
        query: str | RetrievalQuery,
        limit: int | None = None,
        mode: str | None = None,
        access_levels: str | list[str] | None = None,
        doc_ids: str | list[str] | None = None,
        source_types: str | list[str] | None = None,
        filter_criteria: dict[str, Any] | None = None,
        prefetch_limit: int | None = None,
        score_threshold: float | None = None,
        rerank: bool | None = None,
    ) -> list[RetrievedChunk]:
        """Execute synchronous hybrid/dense/sparse retrieval with optional cross-encoder reranking.

        Args:
            query: Query text string or structured RetrievalQuery object.
            limit: Maximum number of chunks to return (default 10).
            mode: 'hybrid' (dense+BM25 with RRF), 'dense', or 'sparse'.
            access_levels: Allowed access level(s) for tenant filtering.
            doc_ids: Restrict search to specific document IDs.
            source_types: Restrict search to specific file formats.
            filter_criteria: Additional arbitrary payload field match filters.
            prefetch_limit: Number of candidates fetched per vector branch before RRF.
            score_threshold: Minimum score cutoff for returned points.
            rerank: Whether to apply local cross-encoder reranking on top candidates (default True).

        Returns:
            List of RetrievedChunk instances ordered by relevance/RRF or reranked score.
        """
        # Normalize input parameters
        if isinstance(query, RetrievalQuery):
            q_text = query.query
            q_limit = limit if limit is not None else query.limit
            q_mode = mode or query.mode
            q_access = (
                access_levels if access_levels is not None else query.access_levels
            )
            q_doc_ids = doc_ids if doc_ids is not None else query.doc_ids
            q_source_types = (
                source_types if source_types is not None else query.source_types
            )
            q_prefetch = (
                prefetch_limit if prefetch_limit is not None else query.prefetch_limit
            )
            q_threshold = (
                score_threshold
                if score_threshold is not None
                else query.score_threshold
            )
            q_rerank = rerank if rerank is not None else query.rerank
        else:
            q_text = query
            q_limit = limit or 10
            q_mode = mode or "hybrid"
            q_access = access_levels
            q_doc_ids = doc_ids
            q_source_types = source_types
            q_prefetch = prefetch_limit or 40
            q_threshold = score_threshold
            q_rerank = rerank if rerank is not None else False

        query_filter = self._build_filter(
            access_levels=q_access,
            doc_ids=q_doc_ids,
            source_types=q_source_types,
            filter_criteria=filter_criteria,
        )

        dense_vec: list[float] | None = None
        sparse_vec: SparseVectorData | None = None

        if q_mode in ("hybrid", "dense"):
            dense_vec = self.embedding_engine.embed_query_dense(q_text)

        if q_mode in ("hybrid", "sparse"):
            sparse_vec = self.embedding_engine.embed_query_sparse(q_text)

        # Stage 1: Fast candidate retrieval (fetch top-N if reranking, else top-k)
        fetch_limit = max(q_limit * 2, 20) if q_rerank else q_limit

        points: list[ScoredPoint] = self.vector_mgr.query_hybrid(
            dense_vector=dense_vec,
            sparse_vector=sparse_vec,
            limit=fetch_limit,
            prefetch_limit=q_prefetch,
            query_filter=query_filter,
        )

        retrieved: list[RetrievedChunk] = []
        for p in points:
            if q_threshold is not None and p.score < q_threshold:
                continue

            payload = p.payload or {}
            content = payload.get("content", "")
            doc_id = payload.get("doc_id", "")
            source = payload.get("source", "")
            source_type = payload.get("source_type", "txt")
            modality = payload.get("modality", "text")
            section = payload.get("section")
            page = payload.get("page")
            chunk_index = payload.get("chunk_index", 0)
            access_lvl = payload.get("access_level", "default")

            # Store any extra metadata
            meta = {
                k: v
                for k, v in payload.items()
                if k
                not in [
                    "content",
                    "doc_id",
                    "source",
                    "source_type",
                    "modality",
                    "section",
                    "page",
                    "chunk_index",
                    "access_level",
                ]
            }

            retrieved.append(
                RetrievedChunk(
                    chunk_id=str(p.id),
                    score=float(p.score),
                    content=content,
                    doc_id=doc_id,
                    source=source,
                    source_type=source_type,
                    modality=modality,
                    section=section,
                    page=page,
                    chunk_index=chunk_index,
                    access_level=access_lvl,
                    metadata=meta,
                )
            )

        # Stage 2: High-precision cross-encoder reranking
        if q_rerank and retrieved:
            retrieved = self.reranker.rerank(
                query=q_text, chunks=retrieved, top_k=q_limit
            )
        else:
            retrieved = retrieved[:q_limit]

        return retrieved

    async def async_retrieve(
        self,
        query: str | RetrievalQuery,
        limit: int | None = None,
        mode: str | None = None,
        access_levels: str | list[str] | None = None,
        doc_ids: str | list[str] | None = None,
        source_types: str | list[str] | None = None,
        filter_criteria: dict[str, Any] | None = None,
        prefetch_limit: int | None = None,
        score_threshold: float | None = None,
        rerank: bool | None = None,
    ) -> list[RetrievedChunk]:
        """Asynchronous wrapper offloading CPU/blocking IO to worker pool per Rule §3."""
        return await asyncio.to_thread(
            self.retrieve,
            query=query,
            limit=limit,
            mode=mode,
            access_levels=access_levels,
            doc_ids=doc_ids,
            source_types=source_types,
            filter_criteria=filter_criteria,
            prefetch_limit=prefetch_limit,
            score_threshold=score_threshold,
            rerank=rerank,
        )
