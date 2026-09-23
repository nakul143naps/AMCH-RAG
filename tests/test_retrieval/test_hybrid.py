"""Unit and integration tests for HybridRetriever with dense, sparse, and RRF fusion."""

from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.embeddings import EmbeddingEngine
from app.retrieval.models import RetrievalQuery
from app.retrieval.retriever import HybridRetriever
from app.retrieval.vector_store import VectorStoreManager


@pytest.fixture
def test_retriever(tmp_path: Path):
    """Fixture providing an isolated in-memory VectorStore and populated HybridRetriever."""
    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    embedding_engine = EmbeddingEngine.get_instance()
    pipeline = IngestionPipeline(
        vector_mgr=vector_mgr, embedding_engine=embedding_engine
    )

    # Document 1: Semantic medical text (great for dense search)
    doc1_path = tmp_path / "cardiology.txt"
    doc1_path.write_text(
        "Cardiovascular diseases and myocardial infarction involve coronary artery blockages "
        "restricting blood flow to the cardiac muscle tissue.",
        encoding="utf-8",
    )
    pipeline.process_file(
        file_path=doc1_path,
        source_name="cardiology.txt",
        access_level="public",
        chunk_size=300,
        chunk_overlap=50,
    )

    # Document 2: Technical log with rare alphanumeric error code (great for BM25 sparse search)
    doc2_path = tmp_path / "errors.txt"
    doc2_path.write_text(
        "Critical failure: ERR-9042-CRASH occurred during distributed TLS handshake. "
        "Inspect node telemetry buffer for dropped packets.",
        encoding="utf-8",
    )
    pipeline.process_file(
        file_path=doc2_path,
        source_name="errors.txt",
        access_level="confidential",
        chunk_size=300,
        chunk_overlap=50,
    )

    retriever = HybridRetriever(
        vector_mgr=vector_mgr, embedding_engine=embedding_engine
    )
    return retriever, vector_mgr


def test_hybrid_retrieval_semantic_match(test_retriever):
    retriever, _ = test_retriever

    # "heart attack" does not appear in doc1, but "myocardial infarction" does
    results = retriever.retrieve(query="What happens during a heart attack?", limit=5)
    assert len(results) > 0
    top = results[0]
    assert "myocardial infarction" in top.content
    assert top.source == "cardiology.txt"
    assert top.score > 0.0


def test_hybrid_retrieval_exact_keyword_match(test_retriever):
    retriever, _ = test_retriever

    # Exact error code ERR-9042-CRASH
    results = retriever.retrieve(query="ERR-9042-CRASH handshake", limit=5)
    assert len(results) > 0
    top = results[0]
    assert "ERR-9042-CRASH" in top.content
    assert top.source == "errors.txt"
    assert top.score > 0.0


def test_access_level_filtering(test_retriever):
    retriever, _ = test_retriever

    # Public user should ONLY see cardiology.txt, not confidential errors.txt
    public_results = retriever.retrieve(
        query="handshake failure",
        access_levels="public",
        limit=5,
    )
    for r in public_results:
        assert r.access_level == "public"
        assert r.source != "errors.txt"

    # Confidential or multi-level access allows both
    multi_results = retriever.retrieve(
        query="failure",
        access_levels=["public", "confidential"],
        limit=5,
    )
    sources = {r.source for r in multi_results}
    assert "errors.txt" in sources


def test_metadata_source_type_filter(test_retriever):
    retriever, _ = test_retriever

    results = retriever.retrieve(
        query="infarction",
        source_types=["txt"],
        limit=5,
    )
    assert len(results) > 0
    for r in results:
        assert r.source_type == "txt"


def test_retrieval_modes_dense_and_sparse(test_retriever):
    retriever, _ = test_retriever

    # Dense only
    dense_res = retriever.retrieve(
        query="heart attack cardiac flow",
        mode="dense",
        limit=2,
    )
    assert len(dense_res) > 0
    assert "cardiac" in dense_res[0].content

    # Sparse only
    sparse_res = retriever.retrieve(
        query="ERR-9042-CRASH",
        mode="sparse",
        limit=2,
    )
    assert len(sparse_res) > 0
    assert "ERR-9042-CRASH" in sparse_res[0].content


@pytest.mark.asyncio
async def test_async_retrieval(test_retriever):
    retriever, _ = test_retriever

    query_obj = RetrievalQuery(
        query="myocardial infarction symptoms",
        limit=3,
        mode="hybrid",
    )
    results = await retriever.async_retrieve(query=query_obj)
    assert len(results) > 0
    assert "myocardial infarction" in results[0].content
