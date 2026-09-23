"""Two-tier caching service: Tier 1 Exact normalized hash + Tier 2 Semantic vector similarity."""

import asyncio
import hashlib
import logging
import re
import time
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

from qdrant_client.models import (
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
)

from app.cache.manager import CacheManager
from app.config import get_settings
from app.retrieval.embeddings import EmbeddingEngine
from app.retrieval.vector_store import VectorStoreManager


def normalize_query(query: str) -> str:
    """Normalize query by lowercasing, stripping extra whitespace, and removing terminal punctuation."""
    q = query.lower().strip()
    q = re.sub(r"[?!.,;:]+$", "", q).strip()
    q = re.sub(r"\s+", " ", q)
    return q


def compute_exact_cache_key(query: str, access_level: str = "default") -> str:
    """Compute deterministic SHA-256 cache key from normalized query and tenant access level."""
    norm = normalize_query(query)
    raw = f"{norm}:{access_level}"
    return f"cache:exact:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


class TwoTierCacheService:
    """Two-tier caching service combining exact normalized matching and semantic vector similarity."""

    _instance: Optional["TwoTierCacheService"] = None

    @classmethod
    def get_instance(
        cls,
        cache_mgr: CacheManager | None = None,
        vector_mgr: VectorStoreManager | None = None,
        embedding_engine: EmbeddingEngine | None = None,
    ) -> "TwoTierCacheService":
        """Return singleton instance of TwoTierCacheService."""
        if cls._instance is None:
            cls._instance = TwoTierCacheService(
                cache_mgr=cache_mgr,
                vector_mgr=vector_mgr,
                embedding_engine=embedding_engine,
            )
        return cls._instance

    def __init__(
        self,
        cache_mgr: CacheManager | None = None,
        vector_mgr: VectorStoreManager | None = None,
        embedding_engine: EmbeddingEngine | None = None,
    ) -> None:
        """Initialize cache manager, Qdrant vector manager, and FastEmbed engine."""
        self.settings = get_settings()
        self.cache_mgr = cache_mgr or CacheManager.get_instance()
        self.vector_mgr = vector_mgr or VectorStoreManager.get_instance()
        self.embedding_engine = embedding_engine or EmbeddingEngine.get_instance()

    def lookup(
        self, query: str, access_level: str = "default"
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Look up answer in cache via Tier 1 (Exact) then Tier 2 (Semantic).

        Returns:
            tuple[entry_data, hit_type] where hit_type is 'exact', 'semantic', or None if miss.
        """
        exact_key = compute_exact_cache_key(query, access_level)

        # 1. Tier 1: Exact Normalized Cache Lookup (<5ms)
        exact_entry = self.cache_mgr.get(exact_key)
        if exact_entry:
            return exact_entry, "exact"

        # 2. Tier 2: Semantic Cache Lookup (<50ms)
        query_vec = self.embedding_engine.embed_query_dense(query)
        self.vector_mgr.ensure_collections()

        try:
            results = self.vector_mgr.client.query_points(
                collection_name=self.settings.QDRANT_SEMANTIC_CACHE_COLLECTION,
                query=query_vec,
                using="dense",
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="access_level", match=MatchValue(value=access_level)
                        )
                    ]
                ),
                limit=1,
            )
            if results.points:
                top_match = results.points[0]
                if top_match.score >= self.settings.SEMANTIC_CACHE_THRESHOLD:
                    payload = top_match.payload or {}
                    linked_key = payload.get("exact_key")
                    if linked_key:
                        semantic_entry = self.cache_mgr.get(linked_key)
                        if semantic_entry:
                            return semantic_entry, "semantic"
        except Exception as e:  # noqa: BLE001
            logger.debug("Semantic cache lookup failed: %s", e)

        return None, None

    def store(
        self,
        query: str,
        access_level: str,
        answer: str,
        citations: list[dict[str, Any]],
        doc_ids: list[str],
        trace_id: str,
    ) -> str:
        """Store synthesized answer and citations in both Exact and Semantic cache tiers."""
        exact_key = compute_exact_cache_key(query, access_level)
        data = {
            "query": query,
            "access_level": access_level,
            "answer": answer,
            "citations": citations,
            "doc_ids": doc_ids,
            "trace_id": trace_id,
            "cached_at": time.time(),
        }

        # 1. Store in Exact Cache (Redis/SQLite)
        self.cache_mgr.set(
            exact_key,
            data,
            ttl_seconds=self.settings.EXACT_CACHE_TTL_SECONDS,
            doc_ids=doc_ids,
        )

        # 2. Store in Semantic Cache (Qdrant)
        query_vec = self.embedding_engine.embed_query_dense(query)
        self.vector_mgr.ensure_collections()
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, exact_key))

        try:
            self.vector_mgr.client.upsert(
                collection_name=self.settings.QDRANT_SEMANTIC_CACHE_COLLECTION,
                points=[
                    PointStruct(
                        id=point_id,
                        vector={"dense": query_vec},
                        payload={
                            "exact_key": exact_key,
                            "query": query,
                            "access_level": access_level,
                            "doc_ids": doc_ids,
                        },
                    )
                ],
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("Semantic cache store failed: %s", e)

        return exact_key

    def invalidate_by_doc(self, doc_id: str) -> int:
        """Invalidate cache entries for a specific document across both cache tiers."""
        count = self.cache_mgr.invalidate_by_doc(doc_id)
        try:
            self.vector_mgr.client.delete(
                collection_name=self.settings.QDRANT_SEMANTIC_CACHE_COLLECTION,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="doc_ids", match=MatchValue(value=doc_id)
                            )
                        ]
                    )
                ),
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("Semantic cache vector invalidation failed: %s", e)
        return count

    def clear(self) -> None:
        """Purge all entries across both cache tiers."""
        self.cache_mgr.clear()
        try:
            self.vector_mgr.client.delete(
                collection_name=self.settings.QDRANT_SEMANTIC_CACHE_COLLECTION,
                points_selector=FilterSelector(filter=Filter()),
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("Semantic cache vector clear failed: %s", e)

    async def async_lookup(
        self, query: str, access_level: str = "default"
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Asynchronously lookup cache offloading to worker pool."""
        return await asyncio.to_thread(self.lookup, query, access_level)

    async def async_store(
        self,
        query: str,
        access_level: str,
        answer: str,
        citations: list[dict[str, Any]],
        doc_ids: list[str],
        trace_id: str,
    ) -> str:
        """Asynchronously store cache offloading to worker pool."""
        return await asyncio.to_thread(
            self.store, query, access_level, answer, citations, doc_ids, trace_id
        )

    async def async_invalidate_by_doc(self, doc_id: str) -> int:
        """Asynchronously invalidate cache offloading to worker pool."""
        return await asyncio.to_thread(self.invalidate_by_doc, doc_id)
