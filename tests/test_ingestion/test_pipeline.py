"""Integration tests for IngestionPipeline with Qdrant vector storage."""

from pathlib import Path

from qdrant_client import QdrantClient

from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.vector_store import VectorStoreManager


def test_ingestion_pipeline_end_to_end(tmp_path: Path):
    # Isolated in-memory Qdrant instance for test
    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    pipeline = IngestionPipeline(vector_mgr=vector_mgr)

    # Create test document
    doc_path = tmp_path / "agentic_rag.md"
    content = """# Agentic Multi-Modal Corrective Hybrid RAG
AMCH-RAG combines dense vector representations, BM25 sparse keyword matching, and RRF rank fusion.
It features autonomous agent loops powered by LangGraph, cross-encoder reranking, and self-correction.

## Retrieval Engine
Dense embeddings capture deep semantic context while BM25 handles precise identifiers and acronyms.
"""
    doc_path.write_text(content, encoding="utf-8")

    # Run ingestion pipeline
    processed = pipeline.process_file(
        file_path=doc_path,
        source_name="agentic_rag.md",
        access_level="public",
        chunk_size=150,
        chunk_overlap=30,
    )

    assert processed.doc_id is not None
    assert len(processed.chunks) > 0

    # Verify chunks stored in Qdrant
    stored_chunks = vector_mgr.get_chunks_by_doc_id(processed.doc_id)
    assert len(stored_chunks) == len(processed.chunks)

    # Verify payload schema adherence
    first_chunk = stored_chunks[0]
    assert first_chunk.source == "agentic_rag.md"
    assert first_chunk.source_type == "md"
    assert first_chunk.modality == "text"
    assert first_chunk.access_level == "public"
    assert first_chunk.chunk_index == 0
    assert len(first_chunk.content) > 0
