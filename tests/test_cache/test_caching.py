"""Tests for Two-Tier Cache (Exact Normalized Hash + Semantic Vector Cache)."""

import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from qdrant_client import QdrantClient

from app.cache.manager import CacheManager, SQLiteCache
from app.cache.service import (
    TwoTierCacheService,
    compute_exact_cache_key,
    normalize_query,
)
from app.ingestion.pipeline import IngestionPipeline
from app.main import app
from app.retrieval.vector_store import VectorStoreManager


def test_normalize_query():
    """Verify that query normalization removes casing, whitespace, and terminal punctuation."""
    raw1 = "  What is Myocardial Infarction?!!  "
    raw2 = "what is myocardial infarction"
    assert normalize_query(raw1) == normalize_query(raw2)
    assert compute_exact_cache_key(raw1) == compute_exact_cache_key(raw2)


def test_exact_cache_hit_under_budget(tmp_path: Path):
    """Verify exact cache hit latency is well within the 300ms performance budget (<10ms)."""
    db_path = str(tmp_path / "test_cache.db")
    cache_mgr = CacheManager()
    cache_mgr.sqlite_cache = SQLiteCache(db_path)
    cache_mgr.redis_client = None  # Force local SQLite for test isolation

    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    service = TwoTierCacheService(cache_mgr=cache_mgr, vector_mgr=vector_mgr)

    # Store entry
    query = "What is AMCH-RAG?"
    service.store(
        query=query,
        access_level="public",
        answer="AMCH-RAG is an agentic corrective hybrid RAG system.",
        citations=[{"source": "readme.md", "index": 1}],
        doc_ids=["doc-amch"],
        trace_id="test-trace-1",
    )

    # Measure lookup time
    start = time.perf_counter()
    entry, hit_type = service.lookup(query="what is amch-rag?", access_level="public")
    duration_ms = (time.perf_counter() - start) * 1000

    assert hit_type == "exact"
    assert entry is not None
    assert "AMCH-RAG is an agentic" in entry["answer"]
    assert duration_ms < 50.0  # Well within the 300ms budget


def test_semantic_cache_hit_for_paraphrased_query(tmp_path: Path):
    """Verify semantic cache hit on paraphrased question with high cosine similarity."""
    db_path = str(tmp_path / "test_cache.db")
    cache_mgr = CacheManager()
    cache_mgr.sqlite_cache = SQLiteCache(db_path)
    cache_mgr.redis_client = None

    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    service = TwoTierCacheService(cache_mgr=cache_mgr, vector_mgr=vector_mgr)

    original_query = "What are the common symptoms of acute myocardial infarction?"
    service.store(
        query=original_query,
        access_level="public",
        answer="Common symptoms include substernal chest discomfort radiating to the left arm and dyspnea.",
        citations=[{"source": "cardiology.md", "index": 1}],
        doc_ids=["doc-cardio"],
        trace_id="test-trace-2",
    )

    # Paraphrased query that won't hit exact cache
    paraphrased = "What are typical symptoms of acute myocardial infarction?"
    entry, hit_type = service.lookup(query=paraphrased, access_level="public")

    assert hit_type == "semantic"
    assert entry is not None
    assert "chest discomfort" in entry["answer"]


def test_cache_miss_on_unrelated_query(tmp_path: Path):
    """Verify cache returns None on unrelated query."""
    db_path = str(tmp_path / "test_cache.db")
    cache_mgr = CacheManager()
    cache_mgr.sqlite_cache = SQLiteCache(db_path)
    cache_mgr.redis_client = None

    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    service = TwoTierCacheService(cache_mgr=cache_mgr, vector_mgr=vector_mgr)

    service.store(
        query="What is photosynthesis?",
        access_level="public",
        answer="Process by which plants convert sunlight to energy.",
        citations=[],
        doc_ids=["doc-bio"],
        trace_id="test-trace-3",
    )

    entry, hit_type = service.lookup(
        query="How does a diesel engine operate?", access_level="public"
    )
    assert entry is None
    assert hit_type is None


def test_cache_invalidation_by_doc_id(tmp_path: Path):
    """Verify that invalidating a doc_id purges linked cache entries across both tiers."""
    db_path = str(tmp_path / "test_cache.db")
    cache_mgr = CacheManager()
    cache_mgr.sqlite_cache = SQLiteCache(db_path)
    cache_mgr.redis_client = None

    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    service = TwoTierCacheService(cache_mgr=cache_mgr, vector_mgr=vector_mgr)

    query = "How to configure Qdrant?"
    service.store(
        query=query,
        access_level="public",
        answer="Set QDRANT_URL or use local path.",
        citations=[],
        doc_ids=["doc-qdrant-config"],
        trace_id="test-trace-4",
    )

    # Verify cached
    entry_before, _ = service.lookup(query=query, access_level="public")
    assert entry_before is not None

    # Invalidate document
    count = service.invalidate_by_doc("doc-qdrant-config")
    assert count > 0

    # Verify purged
    entry_after, hit_type = service.lookup(query=query, access_level="public")
    assert entry_after is None
    assert hit_type is None


def test_cache_access_level_isolation(tmp_path: Path):
    """Verify that confidential cache entries cannot be retrieved by public queries."""
    db_path = str(tmp_path / "test_cache.db")
    cache_mgr = CacheManager()
    cache_mgr.sqlite_cache = SQLiteCache(db_path)
    cache_mgr.redis_client = None

    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    service = TwoTierCacheService(cache_mgr=cache_mgr, vector_mgr=vector_mgr)

    service.store(
        query="classified project timeline",
        access_level="confidential",
        answer="Secret launch in Q4.",
        citations=[],
        doc_ids=["doc-secret"],
        trace_id="test-trace-5",
    )

    # Public query should MISS
    entry, hit_type = service.lookup(
        query="classified project timeline", access_level="public"
    )
    assert entry is None
    assert hit_type is None

    # Confidential query should HIT
    entry_auth, hit_auth = service.lookup(
        query="classified project timeline", access_level="confidential"
    )
    assert hit_auth == "exact"
    assert entry_auth is not None


@pytest.mark.asyncio
async def test_end_to_end_post_query_caching(tmp_path: Path):
    """Verify that POST /query serves subsequent identical calls from cache."""
    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    pipeline = IngestionPipeline(vector_mgr=vector_mgr)
    doc = tmp_path / "cardio.txt"
    doc.write_text(
        "Beta blockers reduce heart rate and blood pressure.", encoding="utf-8"
    )
    pipeline.process_file(file_path=doc, source_name="cardio.txt")

    mock_generate = AsyncMock(
        return_value=("Beta blockers decrease blood pressure [1].", "gemini")
    )

    with patch("app.retrieval.service.ModelGateway.generate", mock_generate):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First request: Cache Miss -> Gateway called
            res1 = await client.post(
                "/query",
                json={"query": "How do beta blockers work?", "access_level": "default"},
            )
            assert res1.status_code == 200
            data1 = res1.json()
            assert data1["provider_used"] == "gemini"

            # Second request: Cache Hit (Exact) -> Gateway NOT called again
            res2 = await client.post(
                "/query",
                json={"query": "How do beta blockers work?", "access_level": "default"},
            )
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["provider_used"] == "cache:exact"
            assert data2["answer"] == data1["answer"]
