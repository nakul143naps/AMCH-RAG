"""Performance budget benchmarks and security verification per RULES.md §11 and §5."""

import re
import time
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from app.agent.guardrails.input_guardrails import InputGuardrails
from app.cache.service import TwoTierCacheService
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.reranker import RerankerService
from app.retrieval.retriever import HybridRetriever
from app.retrieval.vector_store import VectorStoreManager


@pytest.fixture
def benchmark_store(tmp_path: Path):
    """Set up populated store for performance latency benchmarks."""
    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    pipeline = IngestionPipeline(vector_mgr=vector_mgr)

    # Ingest 5 documents to simulate a populated corpus
    for i in range(5):
        doc = tmp_path / f"benchmark_doc_{i}.txt"
        doc.write_text(
            f"Benchmark document {i} discussing quantum computing algorithms and error mitigation techniques in section {i}.",
            encoding="utf-8",
        )
        pipeline.process_file(file_path=doc, source_name=f"benchmark_doc_{i}.txt", access_level="public")

    # Ingest a confidential document for security access testing
    sec_doc = tmp_path / "secret_launch.txt"
    sec_doc.write_text("CLASSIFIED: Apollo-Omega nuclear telemetry launch coordinates.", encoding="utf-8")
    pipeline.process_file(file_path=sec_doc, source_name="secret_launch.txt", access_level="confidential")

    return vector_mgr


@pytest.mark.asyncio
async def test_cache_hit_latency_budget(benchmark_store):
    """Verify cache hit round-trip latency meets budget (< 300ms, typically < 5ms)."""
    cache_service = TwoTierCacheService.get_instance()
    query = "What is the quantum computing algorithm?"

    # Seed the cache
    cache_service.store(
        query=query,
        access_level="public",
        answer="Quantum computing uses superposition and entanglement.",
        citations=[],
        doc_ids=["benchmark_doc_0.txt"],
        trace_id="bench_trace_1",
    )

    # Measure lookup time
    start = time.perf_counter()
    cached, hit_type = await cache_service.async_lookup(query=query, access_level="public")
    duration = time.perf_counter() - start

    assert cached is not None
    assert cached["answer"] == "Quantum computing uses superposition and entanglement."
    assert hit_type == "exact"
    assert duration < 0.300, f"Cache hit exceeded 300ms budget: {duration * 1000:.1f}ms"


@pytest.mark.asyncio
async def test_hybrid_retrieval_and_rerank_latency_budget(benchmark_store):
    """Verify hybrid retrieval + cross-encoder rerank latency meets budget (< 1.5s)."""
    retriever = HybridRetriever(vector_mgr=benchmark_store)
    reranker = RerankerService.get_instance()

    start = time.perf_counter()
    candidates = await retriever.async_retrieve(query="quantum computing error mitigation", limit=8)
    reranked = reranker.rerank(query="quantum computing error mitigation", chunks=candidates, top_k=4)
    duration = time.perf_counter() - start

    assert len(reranked) > 0
    assert duration < 1.500, f"Hybrid retrieval + rerank exceeded 1.5s budget: {duration:.2f}s"


@pytest.mark.asyncio
async def test_security_negative_access_level_filtering(benchmark_store):
    """Security Pass: Verify public user NEVER retrieves confidential chunks at Qdrant level."""
    retriever = HybridRetriever(vector_mgr=benchmark_store)

    # Query as a public user for secret content
    results = await retriever.async_retrieve(
        query="Apollo-Omega nuclear telemetry launch coordinates",
        limit=10,
        access_levels=["public"],
    )

    # Assert confidential document is mathematically excluded
    doc_ids = [c.source for c in results]
    assert "secret_launch.txt" not in doc_ids
    for chunk in results:
        assert chunk.access_level != "confidential"


def test_security_pii_redaction():
    """Security Pass: Verify PII scanner redacts email and phone numbers before downstream processing."""
    guardrails = InputGuardrails()
    raw_query = "Contact admin at security-chief@enterprise.corp or call 555-019-2834 regarding breach."

    result = guardrails.scan_and_sanitize(raw_query)

    assert "security-chief@enterprise.corp" not in result.sanitized_text
    assert "555-019-2834" not in result.sanitized_text
    assert "[REDACTED_EMAIL]" in result.sanitized_text
    assert "[REDACTED_PHONE]" in result.sanitized_text
    assert "pii_redacted" in result.flags


def test_security_secrets_audit():
    """Security Pass: Scan repository files for accidental exposure of live secret keys."""
    forbidden_patterns = [
        r"AIzaSy[A-Za-z0-9_-]{33}",         # Google Gemini live key pattern
        r"gsk_[A-Za-z0-9]{48}",             # Groq live key pattern
        r"sk-or-v1-[A-Za-z0-9]{64}",        # OpenRouter live key pattern
    ]

    project_root = Path(__file__).parent.parent.parent
    scanned_files = 0

    for py_file in project_root.rglob("*.py"):
        if ".venv" in py_file.parts or "node_modules" in py_file.parts:
            continue
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        scanned_files += 1
        for pattern in forbidden_patterns:
            matches = re.findall(pattern, text)
            assert len(matches) == 0, f"Potential active secret found in {py_file}: {matches}"

    assert scanned_files > 20, f"Expected to scan at least 20 Python files, scanned {scanned_files}"
