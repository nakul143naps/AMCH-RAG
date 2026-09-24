"""Tests for GET /documents and DELETE /documents/{doc_id} endpoints."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from qdrant_client import QdrantClient

from app.ingestion.pipeline import IngestionPipeline
from app.main import app
from app.retrieval.vector_store import VectorStoreManager


@pytest.fixture
def populated_vector_store(tmp_path: Path):
    """Set up an in-memory vector store with sample documents for testing."""
    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    pipeline = IngestionPipeline(vector_mgr=vector_mgr)

    # Ingest document 1
    doc1 = tmp_path / "architecture.md"
    doc1.write_text("# AMCH-RAG Architecture\nHybrid retrieval combining dense and sparse vectors.", encoding="utf-8")
    pipeline.process_file(file_path=doc1, source_name="architecture.md", access_level="public")

    # Ingest document 2
    doc2 = tmp_path / "telemetry.txt"
    doc2.write_text("Subsystem telemetry status ok.", encoding="utf-8")
    pipeline.process_file(file_path=doc2, source_name="telemetry.txt", access_level="confidential")

    return vector_mgr


@pytest.mark.asyncio
async def test_list_documents(populated_vector_store):
    """Verify GET /documents returns distinct documents with chunk counts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/documents")
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert data["total"] >= 2

        doc_names = [d["source_name"] for d in data["documents"]]
        assert "architecture.md" in doc_names
        assert "telemetry.txt" in doc_names


@pytest.mark.asyncio
async def test_delete_document_and_cache_eviction(populated_vector_store):
    """Verify DELETE /documents/{doc_id} removes chunks and evicts cache entries."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Fetch current documents to get doc_id
        list_res = await client.get("/documents")
        assert list_res.status_code == 200
        docs = list_res.json()["documents"]
        target_doc = next(d for d in docs if d["source_name"] == "telemetry.txt")
        target_doc_id = target_doc["doc_id"]

        # 2. Delete the document
        del_res = await client.delete(f"/documents/{target_doc_id}")
        assert del_res.status_code == 200
        del_data = del_res.json()
        assert del_data["status"] == "deleted"
        assert del_data["doc_id"] == target_doc_id
        assert del_data["cache_invalidated"] is True

        # 3. Verify document no longer appears in catalog
        after_res = await client.get("/documents")
        after_docs = after_res.json()["documents"]
        after_ids = [d["doc_id"] for d in after_docs]
        assert target_doc_id not in after_ids
